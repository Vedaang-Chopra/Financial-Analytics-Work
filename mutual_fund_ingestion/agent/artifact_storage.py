"""Raw Artifact Storage Abstraction - Configurable storage backend for downloaded files.

This module provides:
1. Pluggable storage backends (local filesystem, S3, GCS, Azure Blob)
2. Configurable retention policies
3. Metadata tracking without storing large files in PostgreSQL
4. Hash-based deduplication
5. Archive tiering (hot/warm/cold)
"""

from __future__ import annotations

import abc
import hashlib
import logging
import os
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, BinaryIO, Optional

from mutual_fund_ingestion.agent.db import get_session_maker

LOGGER = logging.getLogger(__name__)


@dataclass
class ArtifactMetadata:
    """Metadata for a stored artifact."""
    artifact_id: uuid.UUID
    source_url: str
    dataset_type: str
    amc_name: str | None
    scheme_name: str | None
    reporting_date: date | None
    file_type: str
    content_type: str
    size_bytes: int
    checksum_sha256: str
    storage_backend: str
    storage_path: str
    storage_tier: str = "hot"  # hot, warm, cold, archived
    fetch_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    retained: bool = True
    metadata_json: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetentionPolicy:
    """Configurable retention policy."""
    # Time-based retention
    hot_tier_days: int = 30        # Keep in fast storage
    warm_tier_days: int = 365      # Keep in cheaper storage
    cold_tier_days: int = 2555     # Keep in cold storage (7 years)
    archive_after_days: int | None = None  # None = never auto-archive

    # Size-based retention
    max_hot_tier_gb: float = 10.0
    max_warm_tier_gb: float = 100.0

    # Count-based retention
    max_artifacts_per_amc_per_day: int = 100

    # Special rules
    always_retain_failed: bool = True
    retain_parsing_failures_days: int = 90

    # Dataset-specific overrides
    dataset_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)


class StorageBackend(abc.ABC):
    """Abstract base class for storage backends."""

    @abc.abstractmethod
    def store(self, artifact_id: uuid.UUID, content: bytes, metadata: ArtifactMetadata) -> str:
        """Store artifact content and return storage path/key."""
        pass

    @abc.abstractmethod
    def retrieve(self, storage_path: str) -> bytes:
        """Retrieve artifact content."""
        pass

    @abc.abstractmethod
    def exists(self, storage_path: str) -> bool:
        """Check if artifact exists."""
        pass

    @abc.abstractmethod
    def delete(self, storage_path: str) -> bool:
        """Delete artifact."""
        pass

    @abc.abstractmethod
    def move_tier(self, storage_path: str, from_tier: str, to_tier: str) -> str:
        """Move artifact between storage tiers, return new path."""
        pass

    @abc.abstractmethod
    def get_size(self, storage_path: str) -> int:
        """Get artifact size in bytes."""
        pass

    @abc.abstractmethod
    def list_artifacts(self, prefix: str = "", tier: str = "hot") -> list[dict[str, Any]]:
        """List artifacts in a tier."""
        pass


class LocalFilesystemBackend(StorageBackend):
    """Local filesystem storage backend with tiered directories."""

    def __init__(
        self,
        base_path: Path | str,
        tier_paths: dict[str, Path] | None = None,
    ):
        self.base_path = Path(base_path)
        self.tier_paths = tier_paths or {
            "hot": self.base_path / "hot",
            "warm": self.base_path / "warm",
            "cold": self.base_path / "cold",
            "archived": self.base_path / "archived",
        }
        # Create directories
        for path in self.tier_paths.values():
            path.mkdir(parents=True, exist_ok=True)

    def _get_tier_path(self, tier: str) -> Path:
        return self.tier_paths.get(tier, self.tier_paths["hot"])

    def _generate_path(self, artifact_id: uuid.UUID, tier: str, file_type: str) -> Path:
        """Generate deterministic storage path."""
        # Use date-based partitioning for organization
        today = date.today()
        tier_path = self._get_tier_path(tier)
        return tier_path / str(today.year) / f"{today.month:02d}" / f"{artifact_id}.{file_type}"

    def store(self, artifact_id: uuid.UUID, content: bytes, metadata: ArtifactMetadata) -> str:
        tier = metadata.storage_tier
        file_type = metadata.file_type or "bin"
        path = self._generate_path(artifact_id, tier, file_type)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            f.write(content)

        # Verify
        if path.stat().st_size != metadata.size_bytes:
            raise IOError(f"Size mismatch: expected {metadata.size_bytes}, got {path.stat().st_size}")

        # Store metadata sidecar
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        import json
        with open(meta_path, "w") as f:
            json.dump({
                "artifact_id": str(artifact_id),
                "source_url": metadata.source_url,
                "dataset_type": metadata.dataset_type,
                "amc_name": metadata.amc_name,
                "scheme_name": metadata.scheme_name,
                "reporting_date": metadata.reporting_date.isoformat() if metadata.reporting_date else None,
                "file_type": metadata.file_type,
                "content_type": metadata.content_type,
                "size_bytes": metadata.size_bytes,
                "checksum_sha256": metadata.checksum_sha256,
                "storage_tier": tier,
                "fetch_timestamp": metadata.fetch_timestamp.isoformat(),
                "metadata_json": metadata.metadata_json,
            }, f, indent=2)

        return str(path)

    def retrieve(self, storage_path: str) -> bytes:
        path = Path(storage_path)
        if not path.exists():
            raise FileNotFoundError(f"Artifact not found: {storage_path}")
        with open(path, "rb") as f:
            return f.read()

    def exists(self, storage_path: str) -> bool:
        return Path(storage_path).exists()

    def delete(self, storage_path: str) -> bool:
        path = Path(storage_path)
        if path.exists():
            path.unlink()
            # Also delete metadata sidecar
            meta_path = path.with_suffix(path.suffix + ".meta.json")
            if meta_path.exists():
                meta_path.unlink()
            return True
        return False

    def move_tier(self, storage_path: str, from_tier: str, to_tier: str) -> str:
        src = Path(storage_path)
        if not src.exists():
            raise FileNotFoundError(f"Artifact not found: {storage_path}")

        # Generate new path in target tier
        # Preserve the relative path structure
        rel_parts = src.parts[-(3 if from_tier in self.tier_paths else 2):]  # year/month/filename
        dst = self._get_tier_path(to_tier) / Path(*rel_parts)
        dst.parent.mkdir(parents=True, exist_ok=True)

        shutil.move(str(src), str(dst))

        # Move metadata sidecar
        src_meta = src.with_suffix(src.suffix + ".meta.json")
        dst_meta = dst.with_suffix(dst.suffix + ".meta.json")
        if src_meta.exists():
            shutil.move(str(src_meta), str(dst_meta))

        return str(dst)

    def get_size(self, storage_path: str) -> int:
        path = Path(storage_path)
        return path.stat().st_size if path.exists() else 0

    def list_artifacts(self, prefix: str = "", tier: str = "hot") -> list[dict[str, Any]]:
        artifacts = []
        tier_path = self._get_tier_path(tier)
        for file_path in tier_path.rglob("*"):
            if file_path.is_file() and not file_path.name.endswith(".meta.json"):
                meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
                meta = {}
                if meta_path.exists():
                    import json
                    with open(meta_path) as f:
                        meta = json.load(f)

                artifacts.append({
                    "storage_path": str(file_path),
                    "size_bytes": file_path.stat().st_size,
                    "modified": datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).isoformat(),
                    "metadata": meta,
                })
        return artifacts


class S3Backend(StorageBackend):
    """AWS S3 storage backend."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "mutual-fund-artifacts/",
        region: str = "us-east-1",
        tier_prefixes: dict[str, str] | None = None,
    ):
        self.bucket = bucket
        self.prefix = prefix.rstrip("/") + "/"
        self.region = region
        self.tier_prefixes = tier_prefixes or {
            "hot": "hot/",
            "warm": "warm/",
            "cold": "cold/",
            "archived": "archived/",
        }
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client("s3", region_name=self.region)
        return self._client

    def _get_key(self, artifact_id: uuid.UUID, tier: str, file_type: str) -> str:
        today = date.today()
        tier_prefix = self.tier_prefixes.get(tier, "hot/")
        return f"{self.prefix}{tier_prefix}{today.year}/{today.month:02d}/{artifact_id}.{file_type}"

    def _get_meta_key(self, key: str) -> str:
        return key + ".meta.json"

    def store(self, artifact_id: uuid.UUID, content: bytes, metadata: ArtifactMetadata) -> str:
        import json
        key = self._get_key(artifact_id, metadata.storage_tier, metadata.file_type or "bin")

        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=metadata.content_type or "application/octet-stream",
            Metadata={
                "artifact-id": str(artifact_id),
                "source-url": metadata.source_url,
                "dataset-type": metadata.dataset_type,
                "checksum-sha256": metadata.checksum_sha256,
            },
        )

        # Store metadata as separate object
        meta_key = self._get_meta_key(key)
        self.client.put_object(
            Bucket=self.bucket,
            Key=meta_key,
            Body=json.dumps({
                "artifact_id": str(artifact_id),
                "source_url": metadata.source_url,
                "dataset_type": metadata.dataset_type,
                "amc_name": metadata.amc_name,
                "scheme_name": metadata.scheme_name,
                "reporting_date": metadata.reporting_date.isoformat() if metadata.reporting_date else None,
                "file_type": metadata.file_type,
                "content_type": metadata.content_type,
                "size_bytes": metadata.size_bytes,
                "checksum_sha256": metadata.checksum_sha256,
                "storage_tier": metadata.storage_tier,
                "fetch_timestamp": metadata.fetch_timestamp.isoformat(),
                "metadata_json": metadata.metadata_json,
            }).encode(),
            ContentType="application/json",
        )

        return f"s3://{self.bucket}/{key}"

    def retrieve(self, storage_path: str) -> bytes:
        # Parse s3://bucket/key
        if storage_path.startswith("s3://"):
            parts = storage_path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        else:
            bucket = self.bucket
            key = storage_path

        response = self.client.get_object(Bucket=bucket, Key=key)
        return response["Body"].read()

    def exists(self, storage_path: str) -> bool:
        try:
            if storage_path.startswith("s3://"):
                parts = storage_path[5:].split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
            else:
                bucket = self.bucket
                key = storage_path

            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except self.client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def delete(self, storage_path: str) -> bool:
        try:
            if storage_path.startswith("s3://"):
                parts = storage_path[5:].split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
            else:
                bucket = self.bucket
                key = storage_path

            self.client.delete_object(Bucket=bucket, Key=key)
            # Also delete metadata
            meta_key = self._get_meta_key(key)
            try:
                self.client.delete_object(Bucket=bucket, Key=meta_key)
            except:
                pass
            return True
        except:
            return False

    def move_tier(self, storage_path: str, from_tier: str, to_tier: str) -> str:
        if storage_path.startswith("s3://"):
            parts = storage_path[5:].split("/", 1)
            bucket = parts[0]
            key = parts[1] if len(parts) > 1 else ""
        else:
            bucket = self.bucket
            key = storage_path

        # Copy to new tier
        new_key = key.replace(
            self.tier_prefixes.get(from_tier, "hot/"),
            self.tier_prefixes.get(to_tier, "hot/")
        )

        self.client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": key},
            Key=new_key,
        )

        # Copy metadata
        meta_key = self._get_meta_key(key)
        new_meta_key = self._get_meta_key(new_key)
        try:
            self.client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": meta_key},
                Key=new_meta_key,
            )
        except:
            pass

        # Delete old
        self.client.delete_object(Bucket=bucket, Key=key)
        try:
            self.client.delete_object(Bucket=bucket, Key=meta_key)
        except:
            pass

        return f"s3://{bucket}/{new_key}"

    def get_size(self, storage_path: str) -> int:
        try:
            if storage_path.startswith("s3://"):
                parts = storage_path[5:].split("/", 1)
                bucket = parts[0]
                key = parts[1] if len(parts) > 1 else ""
            else:
                bucket = self.bucket
                key = storage_path

            response = self.client.head_object(Bucket=bucket, Key=key)
            return response["ContentLength"]
        except:
            return 0

    def list_artifacts(self, prefix: str = "", tier: str = "hot") -> list[dict[str, Any]]:
        tier_prefix = self.tier_prefixes.get(tier, "hot/")
        full_prefix = f"{self.prefix}{tier_prefix}{prefix}"

        artifacts = []
        paginator = self.client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=full_prefix):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".meta.json"):
                    continue
                artifacts.append({
                    "storage_path": f"s3://{self.bucket}/{obj['Key']}",
                    "size_bytes": obj["Size"],
                    "modified": obj["LastModified"].isoformat(),
                    "metadata": {},
                })
        return artifacts


class ArtifactStorageManager:
    """High-level artifact storage manager with retention policies."""

    def __init__(
        self,
        backend: StorageBackend,
        policy: RetentionPolicy | None = None,
        database_url: str | None = None,
    ):
        self.backend = backend
        self.policy = policy or RetentionPolicy()
        self.database_url = database_url
        self.session_maker = get_session_maker(database_url) if database_url else None

    def store_artifact(
        self,
        content: bytes,
        source_url: str,
        dataset_type: str,
        file_type: str,
        content_type: str,
        amc_name: str | None = None,
        scheme_name: str | None = None,
        reporting_date: date | None = None,
        run_id: uuid.UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ArtifactMetadata:
        """Store artifact with deduplication and metadata tracking."""
        artifact_id = uuid.uuid4()

        # Compute checksum
        checksum = hashlib.sha256(content).hexdigest()

        # Check for existing artifact with same checksum
        if self.session_maker:
            session = self.session_maker()
            try:
                from mutual_fund_ingestion.agent.db import RawArtifact
                existing = session.query(RawArtifact).filter(RawArtifact.checksum == checksum).first()
                if existing:
                    LOGGER.info("Duplicate artifact detected (checksum match): %s", checksum[:12])
                    return ArtifactMetadata(
                        artifact_id=existing.id,
                        source_url=source_url,
                        dataset_type=dataset_type,
                        amc_name=amc_name,
                        scheme_name=scheme_name,
                        reporting_date=reporting_date,
                        file_type=file_type,
                        content_type=content_type,
                        size_bytes=existing.size_bytes or len(content),
                        checksum_sha256=checksum,
                        storage_backend=type(self.backend).__name__,
                        storage_path=existing.local_path or "",
                        storage_tier="hot",
                        fetch_timestamp=existing.fetch_timestamp,
                        retained=existing.retained,
                    )
            finally:
                session.close()

        # Determine initial tier
        tier = self._determine_initial_tier(dataset_type, reporting_date)

        artifact_meta = ArtifactMetadata(
            artifact_id=artifact_id,
            source_url=source_url,
            dataset_type=dataset_type,
            amc_name=amc_name,
            scheme_name=scheme_name,
            reporting_date=reporting_date,
            file_type=file_type,
            content_type=content_type,
            size_bytes=len(content),
            checksum_sha256=checksum,
            storage_backend=type(self.backend).__name__,
            storage_path="",  # Will be filled by backend
            storage_tier=tier,
            fetch_timestamp=datetime.now(timezone.utc),
            metadata_json=metadata or {},
        )

        # Store in backend
        storage_path = self.backend.store(artifact_id, content, artifact_meta)
        artifact_meta.storage_path = storage_path

        # Persist metadata to database
        if self.session_maker:
            session = self.session_maker()
            try:
                from mutual_fund_ingestion.agent.db import RawArtifact
                if run_id:
                    raw_artifact = RawArtifact(
                        id=artifact_id,
                        run_id=run_id,
                        source_url=source_url,
                        artifact_type="file",
                        file_type=file_type,
                        content_type=content_type,
                        checksum=checksum,
                        size_bytes=len(content),
                        local_path=storage_path,
                        retained=True,
                    )
                    session.add(raw_artifact)
                    session.commit()
            finally:
                session.close()

        LOGGER.info("Stored artifact %s (%d bytes) at %s", artifact_id, len(content), storage_path)
        return artifact_meta

    def _determine_initial_tier(self, dataset_type: str, reporting_date: date | None) -> str:
        """Determine initial storage tier based on dataset type and date."""
        if dataset_type == "nav_history":
            return "hot"  # NAV accessed frequently
        if reporting_date:
            days_old = (date.today() - reporting_date).days
            if days_old <= self.policy.hot_tier_days:
                return "hot"
            elif days_old <= self.policy.warm_tier_days:
                return "warm"
            else:
                return "cold"
        return "hot"

    def retrieve_artifact(self, artifact_id: uuid.UUID) -> bytes:
        """Retrieve artifact content by ID."""
        if not self.session_maker:
            raise ValueError("Database required for artifact lookup")

        session = self.session_maker()
        try:
            from mutual_fund_ingestion.agent.db import RawArtifact
            artifact = session.get(RawArtifact, artifact_id)
            if not artifact or not artifact.local_path:
                raise FileNotFoundError(f"Artifact {artifact_id} not found")

            return self.backend.retrieve(artifact.local_path)
        finally:
            session.close()

    def apply_retention_policy(self) -> dict[str, int]:
        """Apply retention policy - move artifacts between tiers."""
        if not self.session_maker:
            raise ValueError("Database required for retention policy")

        stats = {"moved_to_warm": 0, "moved_to_cold": 0, "archived": 0, "deleted": 0}

        session = self.session_maker()
        try:
            from mutual_fund_ingestion.agent.db import RawArtifact
            artifacts = session.query(RawArtifact).filter(RawArtifact.retained == True).all()

            for artifact in artifacts:
                if not artifact.local_path or not artifact.fetch_timestamp:
                    continue

                days_old = (datetime.now(timezone.utc) - artifact.fetch_timestamp).days
                current_tier = "hot"  # Would need to track this

                # Determine target tier
                if days_old > self.policy.cold_tier_days:
                    target_tier = "cold"
                elif days_old > self.policy.warm_tier_days:
                    target_tier = "warm"
                else:
                    target_tier = "hot"

                if target_tier != current_tier and artifact.local_path:
                    try:
                        new_path = self.backend.move_tier(artifact.local_path, current_tier, target_tier)
                        artifact.local_path = new_path
                        if target_tier == "warm":
                            stats["moved_to_warm"] += 1
                        elif target_tier == "cold":
                            stats["moved_to_cold"] += 1
                        session.commit()
                    except Exception as e:
                        LOGGER.warning("Failed to move artifact %s to %s: %s", artifact.id, target_tier, e)

                # Check archive policy
                if self.policy.archive_after_days and days_old > self.policy.archive_after_days:
                    try:
                        self.backend.delete(artifact.local_path)
                        artifact.retained = False
                        artifact.local_path = None
                        stats["archived"] += 1
                        session.commit()
                    except Exception as e:
                        LOGGER.warning("Failed to archive artifact %s: %s", artifact.id, e)

        finally:
            session.close()

        return stats

    def get_storage_stats(self) -> dict[str, Any]:
        """Get storage statistics across all tiers."""
        stats = {
            "tiers": {},
            "total_artifacts": 0,
            "total_size_gb": 0.0,
        }

        for tier in ["hot", "warm", "cold", "archived"]:
            try:
                artifacts = self.backend.list_artifacts(tier=tier)
                tier_size = sum(a["size_bytes"] for a in artifacts)
                stats["tiers"][tier] = {
                    "count": len(artifacts),
                    "size_bytes": tier_size,
                    "size_gb": round(tier_size / (1024**3), 2),
                }
                stats["total_artifacts"] += len(artifacts)
                stats["total_size_gb"] += tier_size / (1024**3)
            except Exception as e:
                LOGGER.warning("Failed to get stats for tier %s: %s", tier, e)
                stats["tiers"][tier] = {"count": 0, "size_bytes": 0, "size_gb": 0.0}

        stats["total_size_gb"] = round(stats["total_size_gb"], 2)
        return stats

    def cleanup_temp_files(self, older_than_days: int = 7) -> int:
        """Clean up temporary download files."""
        # This would clean the temp directories used during download
        # Implementation depends on ArtifactCollector temp_dir structure
        return 0


def check_persistence_gate(session) -> set[str]:
    """Return the set of checksums whose parsed data provably reached canonical tables.

    An artifact checksum is "persisted" when at least one raw_artifact row with that
    checksum has:
      - NAV rows: nav_history.raw_artifact_id -> raw_artifacts.id, OR
      - Portfolio rows: documents.raw_artifact_id -> portfolio_snapshots.document_id
        with at least one portfolio_holdings row on that snapshot.

    Matching by checksum (not just id) also covers deduplicated downloads where rows
    were persisted under a different raw_artifacts.id with identical content.

    Implementation note: nav_history is large (tens of millions of rows) and has no
    index on raw_artifact_id, so the NAV leg is a single set-driven pass rather than
    a correlated EXISTS per artifact.
    """
    from sqlalchemy import text

    nav_ids = [
        row[0]
        for row in session.execute(
            text("SELECT DISTINCT raw_artifact_id FROM nav_history WHERE raw_artifact_id IS NOT NULL")
        )
    ]

    persisted_ids: set[Any] = set(nav_ids)
    persisted_ids.update(
        row[0]
        for row in session.execute(
            text(
                """
                SELECT DISTINCT d.raw_artifact_id
                FROM portfolio_snapshots ps
                JOIN documents d ON d.id = ps.document_id
                JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
                WHERE d.raw_artifact_id IS NOT NULL
                """
            )
        )
    )
    # Deduplicated re-downloads: rows persisted under one raw_artifacts.id while
    # sibling rows (same source_url, different id/checksum presence) hold the
    # local file. Treat every raw_artifacts.id sharing that source_url as
    # persisted too — the URL's data provably reached canonical tables.
    persisted_ids.update(
        row[0]
        for row in session.execute(
            text(
                """
                SELECT DISTINCT ra2.id
                FROM raw_artifacts ra2
                WHERE ra2.source_url IN (
                    SELECT d.source_url
                    FROM portfolio_snapshots ps
                    JOIN documents d ON d.id = ps.document_id
                    JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
                    WHERE d.raw_artifact_id IS NOT NULL AND d.source_url IS NOT NULL
                )
                """
            )
        )
    )

    if not persisted_ids:
        return set()

    checksums: set[str] = set()
    id_list = sorted(str(i) for i in persisted_ids)
    chunk_size = 500
    for start in range(0, len(id_list), chunk_size):
        chunk = id_list[start:start + chunk_size]
        rows = session.execute(
            text("SELECT DISTINCT checksum FROM raw_artifacts WHERE checksum IS NOT NULL AND id::text = ANY(:ids)"),
            {"ids": chunk},
        )
        checksums.update(row[0] for row in rows)

    # URL-level persistence: a file whose source_url's data reached canonical
    # tables under a DIFFERENT artifact row (dedup re-downloads share URLs but
    # may differ in bytes/checksum). Return (checksum -> sentinel) via a second
    # set consumed by load_retention_candidates through persisted_urls param.
    persisted_urls = set(
        row[0]
        for row in session.execute(
            text(
                """
                SELECT DISTINCT d.source_url
                FROM portfolio_snapshots ps
                JOIN documents d ON d.id = ps.document_id
                JOIN portfolio_holdings ph ON ph.snapshot_id = ps.id
                WHERE d.source_url IS NOT NULL
                """
            )
        )
    )
    return checksums, persisted_urls


def load_retention_candidates(
    session,
    *,
    persisted_checksums: set[str],
    finished_before: datetime,
    min_age: timedelta,
    persisted_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    """List local artifact files eligible for delete-after-ingest cleanup.

    A file is eligible only when ALL hold:
      1. It exists on disk (raw_artifacts.local_path, retained=True).
      2. Its checksum is recorded AND appears in ``persisted_checksums``.
      3. Its ingestion run finished before ``finished_before`` (not a live run).
      4. The on-disk file is older than ``min_age``.

    Blocked entries are returned too, each with a ``blocked_reasons`` list.
    """
    from sqlalchemy import text

    sql = text(
        """
        SELECT ra.id, ra.local_path, ra.checksum, ra.size_bytes,
               ra.source_url, ra.artifact_type, ra.retained,
               r.status AS run_status, r.finished_at AS run_finished_at
        FROM raw_artifacts ra
        JOIN ingestion_runs r ON r.id = ra.run_id
        WHERE ra.local_path IS NOT NULL
          AND ra.checksum IS NOT NULL
        """
    )
    now = datetime.now(timezone.utc)
    candidates: list[dict[str, Any]] = []
    for row in session.execute(sql).mappings():
        entry = dict(row)
        reasons: list[str] = []
        local_path = entry["local_path"]
        url_persisted = bool(persisted_urls) and entry.get("source_url") in persisted_urls
        if not entry["checksum"] and not url_persisted:
            reasons.append("no_checksum")
        elif not url_persisted and entry["checksum"] not in persisted_checksums:
            reasons.append("rows_not_in_canonical_tables")
        if entry["run_status"] == "running" or entry["run_finished_at"] is None:
            reasons.append("run_still_running_or_unfinished")
        elif entry["run_finished_at"] > finished_before:
            reasons.append("run_finished_after_cutoff")
        path = Path(local_path)
        if not path.exists():
            reasons.append("file_missing_on_disk")
        else:
            age = now - datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
            if age < min_age:
                reasons.append("file_younger_than_min_age")
            entry["disk_size_bytes"] = path.stat().st_size
        entry["blocked_reasons"] = reasons
        candidates.append(entry)
    return candidates


def create_storage_manager(
    backend_type: str = "local",
    database_url: str | None = None,
    **backend_kwargs,
) -> ArtifactStorageManager:
    """Factory function to create storage manager with configured backend."""
    if backend_type == "local":
        base_path = backend_kwargs.get("base_path", Path("data/raw/mutual_funds/artifacts"))
        backend = LocalFilesystemBackend(base_path)
    elif backend_type == "s3":
        bucket = backend_kwargs.get("bucket")
        if not bucket:
            raise ValueError("S3 backend requires 'bucket' parameter")
        backend = S3Backend(bucket, **{k: v for k, v in backend_kwargs.items() if k != "bucket"})
    else:
        raise ValueError(f"Unknown backend type: {backend_type}")

    policy = RetentionPolicy(**backend_kwargs.get("policy", {}))
    return ArtifactStorageManager(backend, policy, database_url)
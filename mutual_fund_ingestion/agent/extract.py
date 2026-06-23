"""Raw artifact collection: file download, checksum, temp file management."""
from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from utils.http import HttpSettings, build_session
from utils.url_utils import file_type_from_url, safe_name, slugify


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ArtifactCollector:
    session: requests.Session
    temp_dir: Path
    max_file_size_mb: float = 50.0
    keep_raw_files: bool = False

    @classmethod
    def from_config(cls, config: Any) -> "ArtifactCollector":
        session = build_session(HttpSettings(timeout_seconds=30))
        return cls(
            session=session,
            temp_dir=Path(config.temp_dir),
            max_file_size_mb=config.max_file_size_mb,
            keep_raw_files=config.keep_raw_files,
        )

    def download(self, url: str, run_id: str) -> dict[str, Any]:
        temp_dir = self.temp_dir / run_id
        temp_dir.mkdir(parents=True, exist_ok=True)
        try:
            response = self.session.get(url, timeout=30, stream=True, allow_redirects=True)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > self.max_file_size_mb * 1024 * 1024:
                return {"error": "file_too_large", "url": url}

            # Download to temp
            file_type = file_type_from_url(url) or "bin"
            temp_path = temp_dir / f"{slugify(url)}.{file_type}"
            with temp_path.open("wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            # Compute checksum
            hasher = hashlib.sha256()
            with temp_path.open("rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            checksum = hasher.hexdigest()

            LOGGER.info(
                "Downloaded %s: %d bytes sha256=%s",
                url, temp_path.stat().st_size, checksum[:12]
            )

            return {
                "url": url,
                "file_type": file_type,
                "content_type": content_type,
                "checksum": checksum,
                "size_bytes": temp_path.stat().st_size,
                "local_path": str(temp_path),
                "retained": self.keep_raw_files,
            }
        except requests.RequestException as exc:
            return {"error": "download_failed", "url": url, "reason": str(exc)}
        except Exception as exc:
            return {"error": "unknown", "url": url, "reason": str(exc)}

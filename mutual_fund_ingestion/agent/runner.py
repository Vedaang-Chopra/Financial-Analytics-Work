"""Ingestion runner - orchestrates the full pipeline with DB persistence."""
from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from .config import AgentConfig
from .discovery import DiscoveryEngine
from .browser import BrowserUnavailable, extract_with_browser
from .extract import ArtifactCollector
from .parser import parse_file
from .validate import (
    validate_and_filter_records,
    write_validation_result,
    write_quarantine_row,
    write_retry_task,
)
from .vlm import NullVLMClient, OllamaVLMClient
from .db import (
    get_session_maker,
    IngestionRun,
    TaskURL,
    SourcePage,
    DiscoveredLink,
    DatasetCandidate,
    RawArtifact,
    AMC,
    Scheme,
    NAVHistory,
    PortfolioSnapshot,
    PortfolioHolding,
    StagingRow,
    ValidationResult,
    QuarantineRow,
    RetryQueue,
    Document,
    Instrument,
)
from utils.http import HttpSettings, build_session
from utils.text_utils import normalize_amc_name


LOGGER = logging.getLogger(__name__)


class IngestionRunner:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.run_id = str(uuid.uuid4())
        self.started_at = datetime.now(timezone.utc)
        self.stats = {
            "pages_visited": 0,
            "links_discovered": 0,
            "files_downloaded": 0,
            "artifacts_parsed": 0,
            "rows_staged": 0,
            "rows_inserted": 0,
            "rows_quarantined": 0,
            "retry_tasks": 0,
        }
        self.errors: list[dict[str, Any]] = []

        # DB session
        self.session_maker = get_session_maker(config.database_url)
        self.session = self.session_maker()

        # HTTP session for discovery
        self.http_session = build_session(HttpSettings(timeout_seconds=30))

        # Discovery engine
        self.discovery = DiscoveryEngine(session=self.http_session, settings=HttpSettings())

        # Artifact collector
        self.collector = ArtifactCollector.from_config(config)

        # VLM client
        self.vlm = NullVLMClient() if not config.use_vlm else OllamaVLMClient(config.vlm_endpoint, config.vlm_model)

        # Track pending DB objects to batch commit
        self._pending_commit = False

    def run(self) -> dict[str, Any]:
        LOGGER.info("Starting ingestion run %s with %d task URLs", self.run_id, len(self.config.task_urls))

        try:
            # 1. Create ingestion run record
            run = IngestionRun(
                id=uuid.UUID(self.run_id),
                started_at=self.started_at,
                status="running",
                config_json={
                    "task_urls": self.config.task_urls,
                    "max_pages": self.config.max_pages,
                    "max_depth": self.config.max_depth,
                    "max_files": self.config.max_files,
                    "use_browser": self.config.use_browser,
                    "use_vlm": self.config.use_vlm,
                },
            )
            self.session.add(run)

            # 2. Create task_urls rows
            for url in self.config.task_urls:
                task_url = TaskURL(
                    run_id=uuid.UUID(self.run_id),
                    url=url,
                    status="pending",
                )
                self.session.add(task_url)

            self.session.commit()
            self._pending_commit = False

            # 3. Add task URLs to discovery queue
            self.discovery.add_urls(self.config.task_urls, None, 0)
            task_domain = self._get_task_domain()

            # 4. Main crawl loop
            while self.discovery.url_queue and self.stats["pages_visited"] < self.config.max_pages:
                url, parent, depth = self.discovery.url_queue.popleft()

                if url in self.discovery.visited_urls:
                    continue
                self.discovery.visited_urls.add(url)

                if depth > self.config.max_depth:
                    continue

                LOGGER.info("Fetching %s (depth %d)", url, depth)
                status_code, html = self.discovery.fetch(url)
                self.stats["pages_visited"] += 1

                # Create source_page record
                source_page = SourcePage(
                    run_id=uuid.UUID(self.run_id),
                    url=url,
                    canonical_url=self.discovery.get_domain(url),
                    parent_url=parent,
                    domain=self.discovery.get_domain(url),
                    status_code=status_code,
                    content_type="text/html" if html else None,
                    page_relevance="high" if html else "failed",
                )
                self.session.add(source_page)
                self.session.flush()  # Get the ID

                # Update task_url status
                task_url = self.session.execute(
                    select(TaskURL).where(TaskURL.run_id == uuid.UUID(self.run_id), TaskURL.url == url)
                ).scalar_one_or_none()
                if task_url:
                    task_url.status = "completed" if html else "failed"

                if html is None:
                    # Record error
                    self.errors.append({"url": url, "error": "fetch_failed", "status": status_code})
                    self._add_retry_task(url, "fetch", f"HTTP {status_code}", retryable=True)
                    self.stats["retry_tasks"] += 1
                    self._commit_batch()
                    continue

                # Extract links
                links = self.discovery.extract_links(html, url)
                LOGGER.info("Page %s: %d links extracted", url, len(links))

                for link in links:
                    link_url = link["url"]
                    score, dataset_hint = self.discovery.score_relevance(
                        link_url, link.get("text", ""), link.get("title", "")
                    )

                    # VLM invocation for low-confidence pages
                    requires_vlm = False
                    if self.config.use_vlm and score > 0 and score < self.config.vlm_confidence_threshold and html:
                        from .vlm import PageAnalysisPayload
                        vlm_payload = PageAnalysisPayload(
                            objective="Find financial data files (NAV, portfolio, scheme metadata, factsheets, TER, SID, KIM)",
                            current_url=link_url,
                            page_title=link.get("title", ""),
                            visible_text_excerpt=html[:4000],
                            links=links[:20],
                            buttons=[],
                            forms=[],
                            screenshot_path=None
                        )
                        vlm_decision = self.vlm.analyze_page(vlm_payload)
                        if vlm_decision and vlm_decision.page_relevance in ("high", "medium"):
                            score = vlm_decision.confidence
                            dataset_hint = vlm_decision.dataset_hints[0] if vlm_decision.dataset_hints else dataset_hint
                            requires_vlm = True
                            LOGGER.info("VLM classified %s as %s (confidence=%.2f)", link_url, dataset_hint, score)

                    # Create discovered_link record
                    discovered_link = DiscoveredLink(
                        run_id=uuid.UUID(self.run_id),
                        source_page_id=source_page.id,
                        url=link_url,
                        anchor_text=link.get("text"),
                        link_type="html" if not self.discovery.get_file_type(link_url) else "file",
                        dataset_type_hint=dataset_hint,
                        file_type_hint=self.discovery.get_file_type(link_url),
                        should_follow=score > 0.5,
                        relevance_score=score,
                        reason="high_relevance" if score > 0.5 else "low_relevance",
                    )
                    self.session.add(discovered_link)

                    if score > 0.5:
                        self.stats["links_discovered"] += 1

                        # If it's a file, create dataset candidate
                        file_type = self.discovery.get_file_type(link_url)
                        if file_type:
                            # Use classify_dataset for file URLs (more specific than score_relevance hint)
                            inferred_type = self.discovery.classify_dataset(link_url, link.get("text", ""))
                            dataset_type = inferred_type if inferred_type else (dataset_hint or "unknown")
                            dataset_candidate = DatasetCandidate(
                                run_id=uuid.UUID(self.run_id),
                                source_page_id=source_page.id,
                                url=link_url,
                                dataset_type=dataset_type,
                                file_type=file_type,
                                requires_browser=False,
                                requires_form=False,
                                requires_vlm=requires_vlm,
                                confidence=score,
                                status="discovered",
                            )
                            self.session.add(dataset_candidate)
                            self.session.flush()
                            candidates_from_page = 0

                            # Download artifact
                            self._download_and_process_artifact(dataset_candidate, source_page.id)
                            candidates_from_page += 1

                            LOGGER.info("Page %s: %d dataset candidates identified", url, candidates_from_page)

                        # Add to crawl queue
                        if link_url.startswith("http"):
                            self.discovery.url_queue.append((link_url, url, depth + 1))

                # Try browser fallback for failed pages
                if self.config.use_browser and status_code and status_code >= 400:
                    try:
                        browser_result = extract_with_browser(
                            url, self.config.temp_dir / self.run_id / "debug", headless=self.config.headless
                        )
                        # Update source_page with browser results
                        source_page.html_snapshot_path = browser_result.screenshot_path
                        source_page.screenshot_path = browser_result.screenshot_path

                        # Process browser-discovered links
                        for link in browser_result.links:
                            browser_link = DiscoveredLink(
                                run_id=uuid.UUID(self.run_id),
                                source_page_id=source_page.id,
                                url=link["url"],
                                anchor_text=link.get("text"),
                                link_type="browser",
                                relevance_score=0.8,
                                should_follow=True,
                                reason="browser_discovered",
                            )
                            self.session.add(browser_link)
                            self.discovery.url_queue.append((link["url"], url, depth + 1))
                            self.stats["links_discovered"] += 1

                        # Process browser-detected downloads
                        for download in browser_result.downloads:
                            file_type = download.get("file_type")
                            if file_type:
                                dataset_candidate = DatasetCandidate(
                                    run_id=uuid.UUID(self.run_id),
                                    source_page_id=source_page.id,
                                    url=download["url"],
                                    dataset_type="unknown",
                                    file_type=file_type,
                                    requires_browser=True,
                                    requires_form=False,
                                    requires_vlm=False,
                                    confidence=0.7,
                                    status="discovered",
                                )
                                self.session.add(dataset_candidate)
                                self.session.flush()
                                self._download_and_process_artifact(dataset_candidate, source_page.id)

                    except BrowserUnavailable:
                        LOGGER.warning("Playwright not available for browser fallback")
                        self._add_retry_task(url, "browser", "Playwright unavailable", retryable=False)

                self._commit_batch()

            # 5. Finalize run
            finished_at = datetime.now(timezone.utc)
            run.finished_at = finished_at
            run.status = "completed"
            run.pages_seen = self.stats["pages_visited"]
            run.files_seen = self.stats["files_downloaded"]
            run.rows_inserted = self.stats["rows_inserted"]
            run.rows_rejected = self.stats["rows_quarantined"]
            run.error_summary = {
                "errors": self.errors,
                "retry_tasks": self.stats["retry_tasks"],
            }

            self.session.commit()
            self._pending_commit = False

            LOGGER.info(
                "Run %s complete: pages=%d links=%d candidates=%d files=%d staged=%d inserted=%d quarantined=%d retries=%d",
                self.run_id,
                self.stats["pages_visited"],
                self.stats["links_discovered"],
                len(self.discovery.visited_urls),
                self.stats["files_downloaded"],
                self.stats["rows_staged"],
                self.stats["rows_inserted"],
                self.stats["rows_quarantined"],
                self.stats["retry_tasks"],
            )

            return {
                "run_id": self.run_id,
                "status": "completed",
                "pages_visited": self.stats["pages_visited"],
                "links_discovered": self.stats["links_discovered"],
                "files_downloaded": self.stats["files_downloaded"],
                "rows_inserted": self.stats["rows_inserted"],
                "rows_quarantined": self.stats["rows_quarantined"],
                "retry_tasks": self.stats["retry_tasks"],
                "errors": self.errors,
            }

        except Exception as exc:
            LOGGER.exception("Run %s failed: %s", self.run_id, exc)
            self.session.rollback()

            # Try to update run status
            try:
                run = self.session.get(IngestionRun, uuid.UUID(self.run_id))
                if run:
                    run.status = "failed"
                    run.finished_at = datetime.now(timezone.utc)
                    run.error_summary = {"error": str(exc), "errors": self.errors}
                    self.session.commit()
            except Exception:
                pass

            return {
                "run_id": self.run_id,
                "status": "failed",
                "error": str(exc),
                "pages_visited": self.stats["pages_visited"],
                "links_discovered": self.stats["links_discovered"],
                "files_downloaded": self.stats["files_downloaded"],
                "rows_inserted": self.stats["rows_inserted"],
                "rows_quarantined": self.stats["rows_quarantined"],
                "retry_tasks": self.stats["retry_tasks"],
                "errors": self.errors,
            }
        finally:
            self.session.close()

    def _download_and_process_artifact(self, dataset_candidate: DatasetCandidate, source_page_id: uuid.UUID) -> None:
        """Download file, parse, validate, and load to canonical tables."""
        url = dataset_candidate.url

        # Download artifact
        artifact_result = self.collector.download(url, self.run_id)

        if "error" in artifact_result:
            LOGGER.warning("Download failed for %s: %s", url, artifact_result.get("error"))
            dataset_candidate.status = "download_failed"
            self._add_retry_task(url, "download", artifact_result.get("reason", "download failed"), retryable=True)
            self.stats["retry_tasks"] += 1
            return

        self.stats["files_downloaded"] += 1
        LOGGER.info(
            "Downloaded %s: %d bytes sha256=%s",
            url,
            artifact_result.get("size_bytes", 0),
            artifact_result.get("checksum", "")[:12]
        )

        # Create raw_artifact record
        raw_artifact = RawArtifact(
            run_id=uuid.UUID(self.run_id),
            dataset_candidate_id=dataset_candidate.id,
            source_url=url,
            artifact_type="file",
            file_type=artifact_result.get("file_type"),
            content_type=artifact_result.get("content_type"),
            checksum=artifact_result.get("checksum"),
            size_bytes=artifact_result.get("size_bytes"),
            local_path=artifact_result.get("local_path"),
            retained=artifact_result.get("retained", False),
        )
        self.session.add(raw_artifact)
        self.session.flush()

        # L001: Implement raw file retention - move to raw_dir if configured
        if artifact_result.get("retained") and self.config.raw_dir:
            import shutil
            from pathlib import Path
            raw_dir = Path(self.config.raw_dir) / self.run_id
            raw_dir.mkdir(parents=True, exist_ok=True)
            src = Path(artifact_result["local_path"])
            dest = raw_dir / src.name
            shutil.copy2(src, dest)
            raw_artifact.local_path = str(dest)
            LOGGER.info("Retained raw file at %s", dest)

        dataset_candidate.status = "downloaded"

        # Read file content for parsing
        content = None
        if artifact_result.get("local_path"):
            try:
                with open(artifact_result["local_path"], "rb") as f:
                    content = f.read()
            except Exception as exc:
                LOGGER.warning("Failed to read downloaded file %s: %s", artifact_result["local_path"], exc)
                self._add_retry_task(url, "parse", f"File read error: {exc}", retryable=True)
                dataset_candidate.status = "parse_failed"
                self.stats["retry_tasks"] += 1
                return

        if content is None:
            LOGGER.warning("No content for %s", url)
            return

        # Parse the file
        metadata = {"source_url": url, "raw_artifact_id": str(raw_artifact.id)}
        LOGGER.info("Routing to parser for dataset_type=%s file_type=%s", dataset_candidate.dataset_type, dataset_candidate.file_type)
        parser_result = parse_file(
            dataset_type=dataset_candidate.dataset_type,
            file_type=dataset_candidate.file_type,
            content=content,
            metadata=metadata,
        )

        LOGGER.info(
            "Parser %s returned %d records from %s (confidence=%.2f)",
            parser_result.parser_name, len(parser_result.records),
            url, parser_result.confidence
        )
        if parser_result.errors:
            LOGGER.warning("Parser errors for %s: %s", url, "; ".join(parser_result.errors))

        if parser_result.confidence == 0.0:
            LOGGER.warning("No parser for dataset_type=%s file_type=%s", dataset_candidate.dataset_type, dataset_candidate.file_type)
            dataset_candidate.status = "no_parser"
            return

        self.stats["artifacts_parsed"] += 1

        # Stage all parsed records
        for i, record in enumerate(parser_result.records):
            staging_row = StagingRow(
                run_id=uuid.UUID(self.run_id),
                raw_artifact_id=raw_artifact.id,
                dataset_type=dataset_candidate.dataset_type,
                sheet_name=record.get("sheet_name"),
                row_number=i + 1,
                raw_row_json=record,
                parsed_fields_json=record,
                parser_name=parser_result.parser_name,
                parser_confidence=parser_result.confidence,
            )
            self.session.add(staging_row)

        self.stats["rows_staged"] += len(parser_result.records)
        self.session.flush()

        # Validate and filter
        valid_records, quarantined_records = validate_and_filter_records(parser_result, self.run_id)

        LOGGER.info(
            "Validation for %s: %d valid, %d quarantined",
            url, len(valid_records), len(quarantined_records)
        )

        # Write validation results for each record
        for i, record in enumerate(parser_result.records):
            if i < len(valid_records):
                # Valid record - write validation passed
                self._write_validation_result(
                    entity_type=dataset_candidate.dataset_type,
                    check_name="schema_validation",
                    severity="info",
                    status="passed",
                    message="Record passed validation"
                )
            else:
                # Quarantined record - write validation failed
                quarantined = quarantined_records[i - len(valid_records)] if quarantined_records else None
                if quarantined:
                    self._write_validation_result(
                        entity_type=dataset_candidate.dataset_type,
                        check_name="schema_validation",
                        severity="error",
                        status="failed",
                        message=quarantined.get("reason", "validation failed")
                    )

                    # Write quarantine row
                    quarantine_row = QuarantineRow(
                        run_id=uuid.UUID(self.run_id),
                        raw_artifact_id=raw_artifact.id,
                        dataset_type=dataset_candidate.dataset_type,
                        reason=quarantined.get("reason", "unknown"),
                        raw_data_json=quarantined.get("raw_data_json"),
                        parser_error=quarantined.get("parser_error"),
                        retryable=quarantined.get("retryable", False),
                    )
                    self.session.add(quarantine_row)
                    self.stats["rows_quarantined"] += 1

        # Upsert valid records to canonical tables
        self._upsert_canonical(valid_records, dataset_candidate.dataset_type, raw_artifact.id, url)

        dataset_candidate.status = "processed"

    def _upsert_canonical(self, records: list[dict], dataset_type: str, raw_artifact_id: uuid.UUID, source_url: str) -> None:
        """Upsert validated records to canonical tables."""
        if dataset_type == "nav_history":
            self._upsert_nav_history(records, raw_artifact_id, source_url)
        elif dataset_type == "amc_provider_list":
            self._upsert_amcs(records, raw_artifact_id, source_url)
        elif dataset_type == "scheme_master":
            self._upsert_schemes(records, raw_artifact_id, source_url)
        elif dataset_type == "portfolio_disclosure":
            self._upsert_portfolio(records, raw_artifact_id, source_url)
        # Add more dataset types as needed

    def _upsert_nav_history(self, records: list[dict], raw_artifact_id: uuid.UUID, source_url: str) -> None:
        """Upsert NAV records to nav_history table."""
        for record in records:
            scheme_code = record.get("scheme_code")
            nav_date_str = record.get("nav_date")
            nav_value = record.get("nav_value")

            if not all([scheme_code, nav_date_str, nav_value]):
                continue
             
            if not isinstance(nav_date_str, str):
                LOGGER.warning("Invalid date type %s for scheme %s", type(nav_date_str), scheme_code)
                continue
            
            try:
                nav_date = date.fromisoformat(nav_date_str)
            except ValueError:
                LOGGER.warning("Invalid date %s for scheme %s", nav_date_str, scheme_code)
                continue

            # Try to find existing scheme
            scheme = self.session.execute(
                select(Scheme).where(Scheme.scheme_code == scheme_code)
            ).scalar_one_or_none()

            stmt = insert(NAVHistory).values(
                scheme_id=scheme.id if scheme else None,
                scheme_code=scheme_code,
                nav_date=nav_date,
                nav_value=nav_value,
                source_url=source_url,
                raw_artifact_id=raw_artifact_id,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["scheme_code", "nav_date"],
                set_={
                    "nav_value": stmt.excluded.nav_value,
                    "source_url": stmt.excluded.source_url,
                    "raw_artifact_id": stmt.excluded.raw_artifact_id,
                }
            )
            self.session.execute(stmt)
            self.stats["rows_inserted"] += 1

    def _upsert_amcs(self, records: list[dict], raw_artifact_id: uuid.UUID, source_url: str) -> None:
        """Upsert AMC records to amcs table."""
        for record in records:
            name = record.get("name")
            if not name:
                continue

            normalized = normalize_amc_name(name)

            stmt = insert(AMC).values(
                name=name,
                normalized_name=normalized,
                website_url=record.get("website_url"),
                source_url=source_url,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["normalized_name"],
                set_={
                    "name": stmt.excluded.name,
                    "website_url": stmt.excluded.website_url,
                    "source_url": stmt.excluded.source_url,
                }
            )
            self.session.execute(stmt)
            self.stats["rows_inserted"] += 1

    def _upsert_schemes(self, records: list[dict], raw_artifact_id: uuid.UUID, source_url: str) -> None:
        """Upsert scheme records to schemes table."""
        for record in records:
            scheme_code = record.get("scheme_code")
            scheme_name = record.get("scheme_name") or record.get("name")
            amc_name = record.get("amc_name")
            category = record.get("category")
            sub_category = record.get("sub_category")

            if not scheme_name:
                continue

            normalized = normalize_amc_name(scheme_name)

            # Try to find AMC if amc_name provided
            amc_id = None
            if amc_name:
                amc = self.session.execute(
                    select(AMC).where(AMC.normalized_name == normalize_amc_name(amc_name))
                ).scalar_one_or_none()
                if amc:
                    amc_id = amc.id

            stmt = insert(Scheme).values(
                amc_id=amc_id,
                scheme_code=scheme_code,
                scheme_name=scheme_name,
                normalized_scheme_name=normalized,
                category=category,
                sub_category=sub_category,
            )
            conflict_elements = ["scheme_code"] if scheme_code else ["normalized_scheme_name"]
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_elements,
                set_={
                    "scheme_name": stmt.excluded.scheme_name,
                    "normalized_scheme_name": stmt.excluded.normalized_scheme_name,
                    "category": stmt.excluded.category,
                    "sub_category": stmt.excluded.sub_category,
                }
            )
            self.session.execute(stmt)
            self.stats["rows_inserted"] += 1

    def _upsert_portfolio(self, records: list[dict], raw_artifact_id: uuid.UUID, source_url: str) -> None:
        """Upsert portfolio records to portfolio_snapshots and portfolio_holdings."""
        # Group by scheme and date to create snapshots
        from collections import defaultdict
        from datetime import date

        snapshots: dict[tuple, list[dict]] = defaultdict(list)

        for record in records:
            scheme_name = record.get("scheme_name")
            reporting_date_str = record.get("reporting_date") or record.get("date")

            if not scheme_name:
                continue

            try:
                reporting_date = date.fromisoformat(reporting_date_str) if reporting_date_str else date.today()
            except ValueError:
                reporting_date = date.today()

            # Find scheme
            scheme = self.session.execute(
                select(Scheme).where(Scheme.normalized_scheme_name == normalize_amc_name(scheme_name))
            ).scalar_one_or_none()

            if not scheme:
                # Try by name
                scheme = self.session.execute(
                    select(Scheme).where(Scheme.scheme_name.ilike(f"%{scheme_name}%"))
                ).scalar_one_or_none()

            if not scheme:
                LOGGER.warning("Scheme not found for portfolio: %s", scheme_name)
                continue

            key = (scheme.id, reporting_date)
            snapshots[key].append(record)

        for (scheme_id, reporting_date), holdings in snapshots.items():
            # Create portfolio snapshot
            snapshot = PortfolioSnapshot(
                scheme_id=scheme_id,
                reporting_date=reporting_date,
                source_url=source_url,
                parser_version="portfolio_excel_v1",
                validation_status="validated",
            )
            self.session.add(snapshot)
            self.session.flush()

            # Create document record
            doc = Document(
                document_type="portfolio_disclosure",
                scheme_id=scheme_id,
                reporting_date=reporting_date,
                source_url=source_url,
                file_type="xlsx",
            )
            self.session.add(doc)
            self.session.flush()

            snapshot.document_id = doc.id

            # Create holdings
            for holding in holdings:
                security_name = holding.get("security_name")
                if not security_name:
                    continue

                isin = holding.get("isin")
                sector = holding.get("sector")

                # Find or create instrument
                instrument_id = None
                if isin:
                    instrument = self.session.execute(
                        select(Instrument).where(Instrument.isin == isin)
                    ).scalar_one_or_none()
                    if not instrument:
                        instrument = Instrument(
                            isin=isin,
                            name=security_name,
                            normalized_name=normalize_amc_name(security_name),
                            sector=sector,
                        )
                        self.session.add(instrument)
                        self.session.flush()
                    instrument_id = instrument.id
                else:
                    # Create instrument without ISIN
                    instrument = Instrument(
                        name=security_name,
                        normalized_name=normalize_amc_name(security_name),
                        sector=sector,
                    )
                    self.session.add(instrument)
                    self.session.flush()
                    instrument_id = instrument.id

                # Create holding
                portfolio_holding = PortfolioHolding(
                    snapshot_id=snapshot.id,
                    instrument_id=instrument_id,
                    security_name=security_name,
                    isin=holding.get("isin"),
                    sector=holding.get("sector"),
                    asset_class=holding.get("asset_class"),
                    quantity=holding.get("quantity"),
                    market_value=holding.get("market_value"),
                    percentage_to_nav=holding.get("percentage_to_nav"),
                )
                self.session.add(portfolio_holding)
                self.stats["rows_inserted"] += 1

            self.stats["rows_inserted"] += 1  # For snapshot

    def _write_validation_result(
        self,
        entity_type: str,
        check_name: str,
        severity: str,
        status: str,
        message: str | None,
    ) -> None:
        """Write a validation result record."""
        vr = ValidationResult(
            run_id=uuid.UUID(self.run_id),
            entity_type=entity_type,
            check_name=check_name,
            severity=severity,
            status=status,
            message=message,
        )
        self.session.add(vr)

    def _add_retry_task(self, url: str, task_type: str, failure_reason: str, retryable: bool) -> None:
        """Add a task to the retry queue."""
        LOGGER.warning("Retry queued for %s: %s", url, failure_reason)
        retry = RetryQueue(
            run_id=uuid.UUID(self.run_id),
            url=url,
            task_type=task_type,
            failure_reason=failure_reason,
            retry_count=0,
            status="pending",
            retryable=retryable,
        )
        self.session.add(retry)

    def _commit_batch(self) -> None:
        """Commit pending changes."""
        if self._pending_commit or self.session.dirty or self.session.new:
            try:
                self.session.commit()
                self._pending_commit = False
            except Exception as exc:
                LOGGER.error("Commit failed: %s", exc)
                self.session.rollback()
                raise

    def _get_task_domain(self) -> str:
        if self.config.task_urls:
            from urllib.parse import urlparse
            return urlparse(self.config.task_urls[0]).netloc.lower().removeprefix("www.")
        return ""
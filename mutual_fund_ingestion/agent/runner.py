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
from .upserts import UpsertManager
from .artifact_processor import ArtifactProcessor
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

        # Canonical upsert manager (Layer 4 logic extracted)
        self.upsert_manager = UpsertManager()
        self.upsert_manager.set_run_id(self.run_id)

        # Artifact processor (Layer 4 logic extracted)
        self.artifact_processor = ArtifactProcessor(
            run_id=self.run_id,
            stats=self.stats,
            collector=self.collector,
            upsert_manager=self.upsert_manager,
            temp_dir=config.temp_dir,
        )

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
                # Check max_files limit
                if self.stats["files_downloaded"] >= self.config.max_files:
                    LOGGER.info("Reached max_files limit (%d), stopping", self.config.max_files)
                    break

                url, parent, depth = self.discovery.url_queue.popleft()

                if url in self.discovery.visited_urls:
                    continue
                self.discovery.visited_urls.add(url)

                if depth > self.config.max_depth:
                    continue

                LOGGER.info("Fetching %s (depth %d)", url, depth)

                # Use browser for initial fetch if enabled
                html = None
                status_code = None
                if self.config.use_browser:
                    try:
                        LOGGER.info("Using browser for %s", url)
                        browser_result = extract_with_browser(
                            url, self.config.temp_dir / self.run_id / "debug", headless=self.config.headless
                        )
                        html = browser_result.html
                        status_code = 200

                        # Create source_page record
                        source_page = SourcePage(
                            run_id=uuid.UUID(self.run_id),
                            url=url,
                            canonical_url=self.discovery.get_domain(url),
                            parent_url=parent,
                            domain=self.discovery.get_domain(url),
                            status_code=status_code,
                            content_type="text/html",
                            page_relevance="high",
                            html_snapshot_path=browser_result.screenshot_path,
                            screenshot_path=browser_result.screenshot_path,
                        )
                        self.session.add(source_page)
                        self.session.flush()  # Get the ID

                        # Update task_url status
                        task_url = self.session.execute(
                            select(TaskURL).where(TaskURL.run_id == uuid.UUID(self.run_id), TaskURL.url == url)
                        ).scalar_one_or_none()
                        if task_url:
                            task_url.status = "completed"

                        # Process browser-discovered links
                        for link in browser_result.links:
                            link_url = link["url"]
                            score, dataset_hint = self.discovery.score_relevance(
                                link_url, link.get("text", ""), link.get("title", "")
                            )

                            # Create discovered_link record
                            discovered_link = DiscoveredLink(
                                run_id=uuid.UUID(self.run_id),
                                source_page_id=source_page.id,
                                url=link_url,
                                anchor_text=link.get("text"),
                                link_type="browser",
                                dataset_type_hint=dataset_hint,
                                file_type_hint=self.discovery.get_file_type(link_url),
                                should_follow=score > 0.5,
                                relevance_score=score,
                                reason="browser_discovered" if score > 0.5 else "browser_low_relevance",
                            )
                            self.session.add(discovered_link)

                            if score > 0.5:
                                self.stats["links_discovered"] += 1

                                # If it's a file, create dataset candidate
                                file_type = self.discovery.get_file_type(link_url)
                                if file_type:
                                    # Use classify_dataset for file URLs
                                    inferred_type = self.discovery.classify_dataset(link_url, link.get("text", ""))
                                    dataset_type = inferred_type if inferred_type else (dataset_hint or "unknown")
                                    dataset_candidate = DatasetCandidate(
                                        run_id=uuid.UUID(self.run_id),
                                        source_page_id=source_page.id,
                                        url=link_url,
                                        dataset_type=dataset_type,
                                        file_type=file_type,
                                        requires_browser=True,
                                        requires_form=False,
                                        requires_vlm=False,
                                        confidence=score,
                                        status="discovered",
                                    )
                                    self.session.add(dataset_candidate)
                                    self.session.flush()

                                    # Check max_files limit before downloading
                                    if self.stats["files_downloaded"] >= self.config.max_files:
                                        LOGGER.info("Reached max_files limit (%d), stopping", self.config.max_files)
                                        self._commit_batch()
                                        break

                                    # Download artifact
                                    self.artifact_processor.process(self.session, dataset_candidate, raw_dir=self.config.raw_dir)

                                # Add to crawl queue
                                if link_url.startswith("http"):
                                    self.discovery.url_queue.append((link_url, url, depth + 1))

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
                                self.artifact_processor.process(self.session, dataset_candidate, raw_dir=self.config.raw_dir)

                        self._commit_batch()
                        continue  # Skip the regular fetch below
                    except BrowserUnavailable:
                        LOGGER.warning("Playwright not available, falling back to HTTP")
                        # Fall through to HTTP fetch

                # Regular HTTP fetch (original logic)
                if html is None:
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

                    # Check if this is a direct file URL (not HTML page)
                    file_type = self.discovery.get_file_type(url)
                    if file_type and html is None:
                        # Direct file URL - process as dataset candidate immediately
                        LOGGER.info("Direct file URL detected: %s (type: %s)", url, file_type)
                        inferred_type = self.discovery.classify_dataset(url, "")
                        dataset_type = inferred_type if inferred_type else "unknown"

                        dataset_candidate = DatasetCandidate(
                            run_id=uuid.UUID(self.run_id),
                            source_page_id=source_page.id,
                            url=url,
                            dataset_type=dataset_type,
                            file_type=file_type,
                            requires_browser=False,
                            requires_form=False,
                            requires_vlm=False,
                            confidence=0.9,
                            status="discovered",
                        )
                        self.session.add(dataset_candidate)
                        self.session.flush()

                        # Download and process artifact
                        self.artifact_processor.process(self.session, dataset_candidate, raw_dir=self.config.raw_dir)
                        self.stats["files_downloaded"] += 1

                        self._commit_batch()
                        continue

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

                                # Check max_files limit before downloading
                                if self.stats["files_downloaded"] >= self.config.max_files:
                                    LOGGER.info("Reached max_files limit (%d), stopping", self.config.max_files)
                                    self._commit_batch()
                                    break

                                # Download artifact
                                self.artifact_processor.process(self.session, dataset_candidate, raw_dir=self.config.raw_dir)
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
                                    self.artifact_processor.process(self.session, dataset_candidate, raw_dir=self.config.raw_dir)

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
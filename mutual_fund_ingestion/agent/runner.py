"""Ingestion runner — orchestrates the full pipeline."""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from .config import AgentConfig
from .discovery import DiscoveryEngine
from .browser import BrowserUnavailable, extract_with_browser
from .extract import ArtifactCollector
from .parser import parse_file
from .validate import validate_and_filter_records
from .vlm import NullVLMClient, OllamaVLMClient
from utils.http import HttpSettings, build_session


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
        self.session = build_session(HttpSettings(timeout_seconds=30))
        self.discovery = DiscoveryEngine(session=self.session, settings=HttpSettings())
        self.collector = ArtifactCollector.from_config(config)
        self.vlm = NullVLMClient() if not config.use_vlm else OllamaVLMClient(config.vlm_endpoint, config.vlm_model)

    def run(self) -> dict[str, Any]:
        LOGGER.info("Starting ingestion run %s with %d task URLs", self.run_id, len(self.config.task_urls))
        self.discovery.add_urls(self.config.task_urls, None, 0)
        task_domain = self._get_task_domain()
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
            if html is None:
                self.errors.append({"url": url, "error": "fetch_failed", "status": status_code})
                continue
            links = self.discovery.extract_links(html, url)
            new_urls = []
            for link in links:
                score, dataset_hint = self.discovery.score_relevance(link["url"], link.get("text", ""), link.get("title", ""))
                if score > 0.5:
                    self.stats["links_discovered"] += 1
                    new_urls.append(link["url"])
                if link["url"].startswith("http"):
                    self.discovery.url_queue.append((link["url"], url, depth + 1))
            # Try browser if needed
            if self.config.use_browser and status_code and status_code >= 400:
                try:
                    result = extract_with_browser(url, self.config.temp_dir / self.run_id / "debug", headless=self.config.headless)
                    self.stats["pages_visited"] += 1
                    LOGGER.info("Browser render: %d links, %d downloads", len(result.links), len(result.downloads))
                except BrowserUnavailable:
                    pass
        LOGGER.info("Run %s complete: %d pages, %d links", self.run_id, self.stats["pages_visited"], self.stats["links_discovered"])
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

    def _get_task_domain(self) -> str:
        if self.config.task_urls:
            from urllib.parse import urlparse
            return urlparse(self.config.task_urls[0]).netloc.lower().removeprefix("www.")
        return ""
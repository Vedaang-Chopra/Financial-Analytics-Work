from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import requests

from .http import HttpSettings, build_session
from .models import DisclosureLink


LOGGER = logging.getLogger(__name__)


def slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "unknown"


def build_download_name(link: DisclosureLink) -> str:
    stem = Path(link.file_name).stem
    digest = hashlib.sha256(link.file_url.encode("utf-8")).hexdigest()[:10]
    parts = [slugify(link.amc_name or "unknown-amc")]
    if link.month_or_date:
        parts.append(slugify(link.month_or_date))
    parts.extend((slugify(stem), digest))
    return "_".join(parts) + f".{link.file_type.lower()}"


@dataclass(frozen=True)
class DownloadResult:
    link: DisclosureLink
    path: Path
    status: str
    reason: str | None = None


class Downloader:
    def __init__(
        self,
        output_dir: Path,
        *,
        settings: HttpSettings | None = None,
        session: requests.Session | None = None,
        delay_seconds: float = 1,
    ) -> None:
        self.output_dir = output_dir
        self.settings = settings or HttpSettings()
        self.session = session or build_session(self.settings)
        self.delay_seconds = delay_seconds

    def download(self, link: DisclosureLink, *, force: bool = False) -> DownloadResult:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        destination = self.output_dir / build_download_name(link)
        metadata_path = destination.with_suffix(destination.suffix + ".json")
        if destination.exists() and destination.stat().st_size > 0 and not force:
            LOGGER.info("Skipping existing file: %s", destination)
            return DownloadResult(link, destination, "skipped", "already downloaded")

        LOGGER.info("Downloading %s", link.file_url)
        response = self.session.get(
            link.file_url,
            timeout=self.settings.timeout_seconds,
            stream=True,
            allow_redirects=True,
        )
        temporary = destination.with_suffix(destination.suffix + ".part")
        try:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type:
                raise ValueError(f"Refusing HTML response for disclosure file: {link.file_url}")
            chunks = (chunk for chunk in response.iter_content(chunk_size=64 * 1024) if chunk)
            first_chunk = next(chunks, b"")
            prefix = first_chunk.lstrip()[:100].lower()
            if prefix.startswith((b"<html", b"<!doctype html")):
                raise ValueError(f"Refusing HTML payload for disclosure file: {link.file_url}")
            with temporary.open("wb") as handle:
                handle.write(first_chunk)
                for chunk in chunks:
                    handle.write(chunk)
            if temporary.stat().st_size == 0:
                temporary.unlink(missing_ok=True)
                raise ValueError(f"Downloaded file is empty: {link.file_url}")
            temporary.replace(destination)
            metadata = link.to_dict() | {
                "downloaded_path": str(destination),
                "content_type": response.headers.get("content-type"),
                "size_bytes": destination.stat().st_size,
            }
            metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            response.close()
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        return DownloadResult(link, destination, "downloaded")

    def download_many(
        self,
        links: Iterable[DisclosureLink],
        *,
        force: bool = False,
        limit: int | None = None,
    ) -> list[DownloadResult]:
        results: list[DownloadResult] = []
        for index, link in enumerate(links):
            if limit is not None and index >= limit:
                break
            try:
                results.append(self.download(link, force=force))
            except Exception as exc:
                LOGGER.error("Download failed for %s: %s", link.file_url, exc)
                results.append(DownloadResult(link, self.output_dir / build_download_name(link), "failed", str(exc)))
        return results

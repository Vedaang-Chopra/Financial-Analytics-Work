from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .discovery import AMFI_PORTFOLIO_URL, Discoverer, select_latest_per_amc
from .downloader import Downloader
from .http import HttpSettings
from .models import read_jsonl, write_jsonl


DEFAULT_LINKS_PATH = Path("data/raw/amfi/links/amfi_portfolio_links.jsonl")
DEFAULT_FILES_DIR = Path("data/raw/amfi/files")
DEFAULT_DEBUG_DIR = Path("data/debug/amfi")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover and download AMFI portfolio disclosures.")
    parser.add_argument("command", choices=("discover", "download", "run"))
    parser.add_argument("--source-url", default=AMFI_PORTFOLIO_URL)
    parser.add_argument("--links-path", type=Path, default=DEFAULT_LINKS_PATH)
    parser.add_argument("--files-dir", type=Path, default=DEFAULT_FILES_DIR)
    parser.add_argument("--debug-dir", type=Path, default=DEFAULT_DEBUG_DIR)
    parser.add_argument("--limit", type=positive_int)
    parser.add_argument("--limit-per-amc", type=positive_int)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--delay", type=float, default=1)
    parser.add_argument("--log-level", default="INFO")
    return parser


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return parsed


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    settings = HttpSettings(timeout_seconds=args.timeout, retries=args.retries)
    links = []

    if args.command in ("discover", "run"):
        discoverer = Discoverer(
            settings=settings,
            browser_fallback=not args.no_browser,
            debug_dir=args.debug_dir,
        )
        try:
            links = discoverer.discover(args.source_url)
        except RuntimeError as exc:
            logging.error("Discovery failed: %s", exc)
            return 2
        logging.info("Discovered %d unique disclosure files", len(links))
        if not args.dry_run:
            write_jsonl(links, args.links_path)
            logging.info("Wrote links to %s", args.links_path)

    if args.command in ("download", "run"):
        if args.command == "download":
            links = read_jsonl(args.links_path)
        if args.limit_per_amc:
            links = select_latest_per_amc(links, args.limit_per_amc)
        if args.dry_run:
            logging.info("Dry run: would download %d files", min(len(links), args.limit or len(links)))
            return 0
        downloader = Downloader(
            args.files_dir,
            settings=settings,
            delay_seconds=args.delay,
        )
        results = downloader.download_many(links, force=args.force, limit=args.limit)
        counts = {status: sum(result.status == status for result in results) for status in ("downloaded", "skipped", "failed")}
        logging.info(
            "Downloads complete: %d downloaded, %d skipped, %d failed",
            counts["downloaded"],
            counts["skipped"],
            counts["failed"],
        )
        return 1 if counts["failed"] else 0
    return 0

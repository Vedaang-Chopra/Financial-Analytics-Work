from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable


DISCOVERY_METHODS = {"static_html", "network_request", "playwright", "manual_pattern"}


@dataclass(frozen=True)
class DisclosureLink:
    source_page_url: str
    file_url: str
    file_name: str
    file_type: str
    disclosure_type: str | None = None
    amc_name: str | None = None
    month_or_date: str | None = None
    discovered_at: str = ""
    discovery_method: str = "static_html"
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.discovery_method not in DISCOVERY_METHODS:
            raise ValueError(f"Unsupported discovery method: {self.discovery_method}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def write_jsonl(links: Iterable[DisclosureLink], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for link in links:
            handle.write(json.dumps(link.to_dict(), ensure_ascii=True, sort_keys=True) + "\n")


def read_jsonl(path: Path) -> list[DisclosureLink]:
    links: list[DisclosureLink] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                links.append(DisclosureLink(**json.loads(line)))
            except (TypeError, ValueError, json.JSONDecodeError) as exc:
                raise ValueError(f"Invalid JSONL record at {path}:{line_number}: {exc}") from exc
    return links

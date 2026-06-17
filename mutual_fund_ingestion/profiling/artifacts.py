from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .models import ProviderProfile


@dataclass(frozen=True)
class ArtifactPaths:
    history: Path
    latest: Path
    report_html: Path
    summary_csv: Path
    debug_root: Path

    @classmethod
    def from_roots(cls, output_dir: Path, report_dir: Path, debug_root: Path) -> "ArtifactPaths":
        return cls(
            history=output_dir / "provider_profiles.jsonl",
            latest=output_dir / "provider_profiles.latest.json",
            report_html=report_dir / "provider_profile_report.html",
            summary_csv=report_dir / "provider_profile_summary.csv",
            debug_root=debug_root,
        )


def load_latest_profiles(path: Path) -> dict[str, ProviderProfile]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {item["amc_name"]: ProviderProfile.from_dict(item) for item in data}


def write_profile_artifacts(
    profiles: Iterable[ProviderProfile],
    paths: ArtifactPaths,
    dry_run: bool = False,
) -> None:
    profiles = list(profiles)
    if dry_run:
        return
    paths.history.parent.mkdir(parents=True, exist_ok=True)
    existing_keys: set[tuple[str, str]] = set()
    if paths.history.exists():
        for line in paths.history.read_text(encoding="utf-8").splitlines():
            if line.strip():
                item = json.loads(line)
                existing_keys.add((item["run_id"], item["amc_name"]))
    with paths.history.open("a", encoding="utf-8") as handle:
        for profile in profiles:
            key = (profile.run_id, profile.amc_name)
            if key not in existing_keys:
                handle.write(json.dumps(profile.to_dict(), ensure_ascii=True, sort_keys=True) + "\n")
                existing_keys.add(key)
    latest = load_latest_profiles(paths.latest)
    latest.update({profile.amc_name: profile for profile in profiles})
    paths.latest.write_text(
        json.dumps(
            [profile.to_dict() for profile in sorted(latest.values(), key=lambda item: item.amc_name.casefold())],
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

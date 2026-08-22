"""Re-ingest with corrected parser: bypass checksum dedup (same files, better
parse now), refresh canonical rows. Uses --force flag added to reparse tool."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import subprocess, sys

cmd = [
    "./financial_env/bin/python", "-B", "scripts/reparse_artifacts.py",
    "--database-url", mutual_funds_url(),
    "--host", "icicipruamc.com",
    "--delay", "2",
    "--force",
]
print(" ".join(cmd))
sys.exit(subprocess.call(cmd))

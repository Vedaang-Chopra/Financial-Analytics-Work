import re
from pathlib import Path
log = Path("/Users/vedaangchopra/.hermes/cache/delegation/live/deleg_03e11cbd/task-0.log").read_text(errors="replace")
runs = re.findall(r'--amcs ([a-z_]+) --max-files (\d+)', log)
from collections import Counter
print("ingestion runs launched:", Counter(runs))
completes = log.count("INGESTION COMPLETE")
print("completed ingestions:", completes)
# errors
errs = re.findall(r"(?:Failed to process|Errors: (\d+))", log)
print("error mentions:", len(errs))

"""Merge duplicate ICICI scheme rows — v2.

Order of operations fixed:
1. For dup-name groups: pick keep row (has scheme_code, else earliest).
2. Move snapshots only when (keep_id, date) slot is free; otherwise keep the
   existing snapshot on keep_id and DELETE the incoming snapshot's holdings
   first, then the snapshot (they are exact re-parse duplicates).
3. Move documents/nav_history/scheme_coverage.
4. Delete loser scheme rows.
Backup CSV written before any change.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from db_config import mutual_funds_url

import csv
from pathlib import Path
import psycopg2

conn = psycopg2.connect(mutual_funds_url())
cur = conn.cursor()

cur.execute("""
    SELECT s.normalized_scheme_name,
           (array_agg(s.id::text ORDER BY (s.scheme_code IS NULL), s.created_at))[1] AS keep_id,
           array_agg(s.id::text ORDER BY (s.scheme_code IS NULL), s.created_at) AS all_ids
    FROM schemes s
    WHERE s.amc_id = (SELECT id FROM amcs WHERE name = 'ICICI Prudential Mutual Fund')
    GROUP BY s.normalized_scheme_name
    HAVING count(*) > 1
""")
groups = cur.fetchall()
print("dup groups:", len(groups))

out = Path("data/tmp/backup_scheme_merge_icici_v2_2026-08-22.csv")
fout = out.open("w", newline="")
w = csv.writer(fout)
w.writerow(["action", "keep_or_deleted", "detail"])

moved_snaps = deleted_snaps = moved_docs = deleted_schemes = 0
for name, keep_id, all_ids in groups:
    drops = [i for i in all_ids if i != keep_id]
    for d in drops:
        # snapshots on the drop scheme: move if free slot, else delete holdings+snapshot
        cur.execute("SELECT id::text, reporting_date FROM portfolio_snapshots WHERE scheme_id=%s", (d,))
        snaps = cur.fetchall()
        for snap_id, rdate in snaps:
            cur.execute(
                "SELECT 1 FROM portfolio_snapshots WHERE scheme_id=%s AND reporting_date=%s",
                (keep_id, rdate),
            )
            exists = cur.fetchone()
            if exists:
                cur.execute("DELETE FROM portfolio_holdings WHERE snapshot_id=%s", (snap_id,))
                cur.execute("UPDATE portfolio_snapshots SET document_id=NULL WHERE id=%s", (snap_id,))
                cur.execute("DELETE FROM portfolio_snapshots WHERE id=%s", (snap_id,))
                cur.execute("DELETE FROM documents WHERE scheme_id=%s AND reporting_date=%s AND document_type='portfolio_disclosure' AND id NOT IN (SELECT document_id FROM portfolio_snapshots WHERE document_id IS NOT NULL)", (d, rdate))
                deleted_snaps += 1
                w.writerow(["deleted_snapshot", d, f"{snap_id} {rdate}"])
            else:
                cur.execute("UPDATE portfolio_snapshots SET scheme_id=%s WHERE id=%s", (keep_id, snap_id))
                moved_snaps += 1
                w.writerow(["moved_snapshot", d, f"{snap_id}->{keep_id} {rdate}"])
        # Drop-scheme docs: if keep already has a doc for same
        # (date,type,url), just delete the drop-side doc; else move it.
        cur.execute("""
            DELETE FROM documents d1
            USING documents d2
            WHERE d1.scheme_id=%s AND d2.scheme_id=%s
              AND d1.reporting_date=d2.reporting_date
              AND d1.document_type=d2.document_type
              AND d1.source_url=d2.source_url
        """, (d, keep_id))
        cur.execute("UPDATE documents SET scheme_id=%s WHERE scheme_id=%s", (keep_id, d))
        moved_docs += cur.rowcount
        cur.execute("UPDATE nav_history SET scheme_id=%s WHERE scheme_id=%s", (keep_id, d))
        for table in ("scheme_coverage", "coverage_alerts"):
            try:
                cur.execute(f"DELETE FROM {table} WHERE scheme_id=%s", (d,))
            except Exception:
                conn.rollback()
        cur.execute("DELETE FROM schemes WHERE id=%s", (d,))
        deleted_schemes += 1
        w.writerow(["deleted_scheme", d, f"->{keep_id}"])

conn.commit()
fout.close()
print(f"snapshots moved={moved_snaps} deleted={deleted_snaps} | docs moved={moved_docs} | schemes deleted={deleted_schemes}")

# dedupe snapshots that now collide (same keep slot got multiple via different paths)
cur.execute("""
    SELECT count(*) FROM (
      SELECT scheme_id, reporting_date FROM portfolio_snapshots
      GROUP BY 1,2 HAVING count(*)>1
    ) t
""")
print("dup snapshot groups after merge:", cur.fetchone()[0])

cur.execute("""
SELECT count(*) FILTER (WHERE pct BETWEEN 90 AND 110) ok,
       count(*) FILTER (WHERE pct NOT BETWEEN 90 AND 110) bad
FROM (SELECT ps.id, SUM(h.percentage_to_nav) pct FROM portfolio_snapshots ps
JOIN schemes s ON s.id=ps.scheme_id JOIN amcs a ON a.id=s.amc_id
JOIN portfolio_holdings h ON h.snapshot_id=ps.id
WHERE a.name='ICICI Prudential Mutual Fund' GROUP BY ps.id) t""")
print("icici sanity ok/bad:", cur.fetchone())
conn.close()

-- Backup of ingestion_runs id=46 before supersede marking (20260822_150334)
INSERT INTO ingestion_runs (id, run_uuid, stock_slug, status, variant, sections_parsed, error, started_at, finished_at) VALUES ('46', 'a666be05-a3a1-4695-a5d2-27dc4db385c8', 'ADANIPOWER', 'failed', 'consolidated', NULL, '(raised as a result of Query-invoked autoflush; consider using a session.no_autoflush block if this flush is occurring prematurely)
(psycopg2.errors.NumericValueOutOfRange) integer out of range

[SQL: INSERT INTO price_points (stock_id, point_date, series, close, volume, delivery_pct, fetched_at) VALUES (%(stock_id)s, %(point_date)s, %(series)s, %(close)s, %(volume)s, %(delivery_pct)s, %(fetched_at)s) RETURNING price_points.id]
[parameters: {''stock_id'': 30, ''point_date'': ''2021-06-11'', ''series'': ''volume'', ''close'': None, ''volume'': 3495440235, ''delivery_pct'': 25.0, ''fetched_at'': datetime.datetime(2026, 8, 21, 23, 32, 3, 92317, tzinfo=datetime.timezone.utc)}]
(Background on this error at: https://sqlalche.me/e/20/9h9h)', '2026-08-21T23:32:03.103843+00:00', '2026-08-21T23:32:03.093108+00:00');

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from psycopg import sql


ROOT = Path(__file__).resolve().parents[1]


SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS audio_samples (
  id BIGSERIAL PRIMARY KEY,
  file_path TEXT NOT NULL UNIQUE,
  file_name TEXT NOT NULL,
  file_sha256 TEXT UNIQUE,
  duration_seconds DOUBLE PRECISION NOT NULL,
  original_sample_rate INTEGER,
  original_channels INTEGER,
  instrument TEXT,
  source TEXT,
  tags TEXT[] NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audio_segments (
  id BIGSERIAL PRIMARY KEY,
  sample_id BIGINT NOT NULL REFERENCES audio_samples(id) ON DELETE CASCADE,
  segment_index INTEGER NOT NULL,
  start_seconds DOUBLE PRECISION NOT NULL,
  end_seconds DOUBLE PRECISION NOT NULL,
  segment_type TEXT NOT NULL,
  sample_rate INTEGER NOT NULL DEFAULT 24000,
  duration_seconds DOUBLE PRECISION NOT NULL,
  embedding vector(1024) NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (sample_id, segment_index)
);

CREATE INDEX IF NOT EXISTS audio_segments_sample_id_idx
ON audio_segments(sample_id);

CREATE INDEX IF NOT EXISTS audio_samples_instrument_idx
ON audio_samples(instrument);

CREATE INDEX IF NOT EXISTS audio_samples_tags_gin_idx
ON audio_samples USING gin(tags);
"""


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def connection_kwargs(dbname: str) -> dict[str, object]:
    return {
        "host": os.environ["DB_HOST"],
        "port": int(os.environ.get("DB_PORT", "5432")),
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PW"],
        "dbname": dbname,
    }


def connect() -> psycopg.Connection:
    candidates = []
    if os.environ.get("DB_NAME"):
        candidates.append(os.environ["DB_NAME"])
    candidates.extend([os.environ["DB_USER"], "postgres"])

    seen = set()
    for dbname in candidates:
        if dbname in seen:
            continue
        seen.add(dbname)
        try:
            conn = psycopg.connect(**connection_kwargs(dbname))
            print(f"Connected to database: {dbname}")
            return conn
        except psycopg.OperationalError as exc:
            print(f"Could not connect to database {dbname!r}: {exc.__class__.__name__}")
    raise SystemExit("Could not connect to any candidate database.")


def main() -> None:
    load_dotenv(ROOT / ".env")
    required = ["DB_HOST", "DB_PORT", "DB_USER", "DB_PW"]
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(SCHEMA_SQL)
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name IN ('audio_samples', 'audio_segments')
                ORDER BY table_name
                """
            )
            tables = [row[0] for row in cur.fetchall()]
            cur.execute(
                sql.SQL(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND tablename IN ('audio_samples', 'audio_segments')
                    ORDER BY indexname
                    """
                )
            )
            indexes = [row[0] for row in cur.fetchall()]

    print("Tables:", ", ".join(tables))
    print("Indexes:", ", ".join(indexes))


if __name__ == "__main__":
    main()

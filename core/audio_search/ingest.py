from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import psycopg
from pgvector.psycopg import register_vector

from audio_search.embedding import EmbeddedSegment, MertEmbeddingExtractor


CORE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CORE_ROOT.parent


@dataclass(frozen=True)
class SampleRecord:
    id: int
    file_path: str


@dataclass(frozen=True)
class EmbeddedSampleResult:
    sample_id: int
    file_path: str
    segment_count: int


def coerce_sample_record(record: SampleRecord | Mapping[str, object] | Sequence[object]) -> SampleRecord:
    if isinstance(record, SampleRecord):
        return record
    if isinstance(record, Mapping):
        return SampleRecord(id=int(record["id"]), file_path=str(record["file_path"]))
    if len(record) < 2:
        raise ValueError("Sample record sequence must contain at least id and file_path")
    return SampleRecord(id=int(record[0]), file_path=str(record[1]))


def resolve_sample_path(record: SampleRecord, *, project_root: Path = PROJECT_ROOT) -> Path:
    path = Path(record.file_path)
    if path.is_absolute():
        return path
    return project_root / path


def register_pgvector(conn: psycopg.Connection) -> None:
    register_vector(conn)


def save_embedded_segments(
    conn: psycopg.Connection,
    *,
    sample_id: int,
    embedded_segments: list[EmbeddedSegment],
) -> int:
    register_pgvector(conn)
    with conn.cursor() as cur:
        for item in embedded_segments:
            segment = item.segment
            cur.execute(
                """
                INSERT INTO audio_segments (
                  sample_id,
                  segment_index,
                  start_seconds,
                  end_seconds,
                  segment_type,
                  sample_rate,
                  duration_seconds,
                  embedding
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (sample_id, segment_index) DO UPDATE SET
                  start_seconds = EXCLUDED.start_seconds,
                  end_seconds = EXCLUDED.end_seconds,
                  segment_type = EXCLUDED.segment_type,
                  sample_rate = EXCLUDED.sample_rate,
                  duration_seconds = EXCLUDED.duration_seconds,
                  embedding = EXCLUDED.embedding
                """,
                (
                    sample_id,
                    segment.segment_index,
                    segment.start_seconds,
                    segment.end_seconds,
                    segment.segment_type,
                    segment.sample_rate,
                    segment.duration_seconds,
                    item.embedding,
                ),
            )

        cur.execute(
            """
            DELETE FROM audio_segments
            WHERE sample_id = %s
              AND segment_index >= %s
            """,
            (sample_id, len(embedded_segments)),
        )
    return len(embedded_segments)


def embed_and_store_sample_record(
    conn: psycopg.Connection,
    record: SampleRecord | Mapping[str, object] | Sequence[object],
    *,
    extractor: MertEmbeddingExtractor | None = None,
    project_root: Path = PROJECT_ROOT,
    local_files_only: bool = True,
) -> EmbeddedSampleResult:
    sample = coerce_sample_record(record)
    audio_path = resolve_sample_path(sample, project_root=project_root)
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file does not exist: {audio_path}")

    owns_extractor = extractor is None
    if extractor is None:
        extractor = MertEmbeddingExtractor(local_files_only=local_files_only)

    try:
        embedded_segments = extractor.embed_file(audio_path)
        segment_count = save_embedded_segments(
            conn,
            sample_id=sample.id,
            embedded_segments=embedded_segments,
        )
    finally:
        if owns_extractor:
            del extractor

    return EmbeddedSampleResult(
        sample_id=sample.id,
        file_path=sample.file_path,
        segment_count=segment_count,
    )

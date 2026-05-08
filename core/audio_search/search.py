from __future__ import annotations

from pathlib import Path

import psycopg

from audio_search.embedding import MertEmbeddingExtractor
from audio_search.ingest import register_pgvector


def find_similar_audio_paths(
    conn: psycopg.Connection,
    audio_path: str | Path,
    k: int,
    *,
    extractor: MertEmbeddingExtractor | None = None,
    local_files_only: bool = True,
    candidate_limit_per_segment: int = 200,
) -> list[str]:
    if k <= 0:
        raise ValueError("k must be greater than 0")
    if candidate_limit_per_segment <= 0:
        raise ValueError("candidate_limit_per_segment must be greater than 0")

    owns_extractor = extractor is None
    if extractor is None:
        extractor = MertEmbeddingExtractor(local_files_only=local_files_only)

    try:
        query_segments = extractor.embed_file(audio_path)
        if not query_segments:
            return []

        register_pgvector(conn)
        with conn.cursor() as cur:
            cur.execute("CREATE TEMP TABLE tmp_query_candidates (sample_id BIGINT, similarity DOUBLE PRECISION) ON COMMIT DROP")

            for item in query_segments:
                cur.execute(
                    """
                    INSERT INTO tmp_query_candidates (sample_id, similarity)
                    SELECT
                      sample_id,
                      1 - (embedding <=> %s) AS similarity
                    FROM audio_segments
                    ORDER BY embedding <=> %s
                    LIMIT %s
                    """,
                    (item.embedding, item.embedding, candidate_limit_per_segment),
                )

            cur.execute(
                """
                WITH sample_scores AS (
                  SELECT
                    sample_id,
                    max(similarity) AS best_similarity,
                    avg(similarity) AS avg_candidate_similarity
                  FROM tmp_query_candidates
                  GROUP BY sample_id
                )
                SELECT a.file_path
                FROM sample_scores s
                JOIN audio_samples a ON a.id = s.sample_id
                ORDER BY
                  (0.8 * s.best_similarity + 0.2 * s.avg_candidate_similarity) DESC,
                  a.id ASC
                LIMIT %s
                """,
                (k,),
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        if owns_extractor:
            del extractor

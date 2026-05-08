from __future__ import annotations

from pathlib import Path

import psycopg

from audio_search.embedding import MertEmbeddingExtractor
from audio_search.ingest import register_pgvector


def search_by_embedding(
    conn: psycopg.Connection,
    embedding,
    k: int,
    *,
    candidate_limit: int = 200,
) -> list[tuple[str, float, float, float]]:
    register_pgvector(conn)
    with conn.cursor() as cur:
        cur.execute(
            """
            WITH ranked_segments AS (
              SELECT
                seg.sample_id,
                seg.start_seconds,
                seg.end_seconds,
                1 - (seg.embedding <=> %s) AS similarity,
                row_number() OVER (
                  PARTITION BY seg.sample_id
                  ORDER BY seg.embedding <=> %s
                ) AS rn
              FROM audio_segments seg
              ORDER BY seg.embedding <=> %s
              LIMIT %s
            ),
            sample_scores AS (
              SELECT
                sample_id,
                max(similarity) AS best_similarity,
                avg(similarity) FILTER (WHERE rn <= 3) AS top3_avg_similarity
              FROM ranked_segments
              GROUP BY sample_id
            )
            SELECT
              samples.file_path,
              (0.8 * scores.best_similarity + 0.2 * scores.top3_avg_similarity) AS score,
              best.start_seconds,
              best.end_seconds
            FROM sample_scores scores
            JOIN audio_samples samples ON samples.id = scores.sample_id
            JOIN LATERAL (
              SELECT start_seconds, end_seconds
              FROM ranked_segments ranked
              WHERE ranked.sample_id = scores.sample_id
              ORDER BY similarity DESC
              LIMIT 1
            ) best ON true
            ORDER BY score DESC, samples.id ASC
            LIMIT %s
            """,
            (embedding, embedding, embedding, candidate_limit, k),
        )
        return [(row[0], float(row[1]), float(row[2]), float(row[3])) for row in cur.fetchall()]


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


def find_similar_audio_groups(
    conn: psycopg.Connection,
    audio_path: str | Path,
    k: int,
    *,
    extractor: MertEmbeddingExtractor | None = None,
    local_files_only: bool = True,
    candidate_limit_per_group: int = 200,
) -> list[dict[str, object]]:
    if k <= 0:
        raise ValueError("k must be greater than 0")

    owns_extractor = extractor is None
    if extractor is None:
        extractor = MertEmbeddingExtractor(local_files_only=local_files_only)

    try:
        group_embeddings = extractor.embed_query_groups(audio_path)
        results: list[dict[str, object]] = []
        for group, embedded in group_embeddings:
            matches = search_by_embedding(
                conn,
                embedded.embedding,
                k,
                candidate_limit=candidate_limit_per_group,
            )
            results.append(
                {
                    "group": group.name,
                    "onset_count": len(group.onset_times),
                    "onset_times": group.onset_times,
                    "matches": matches,
                }
            )
        return results
    finally:
        if owns_extractor:
            del extractor

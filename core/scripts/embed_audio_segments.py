from __future__ import annotations

import argparse
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from audio_search import MertEmbeddingExtractor, embed_and_store_sample_record
from create_tables import ROOT, connect, load_dotenv


def fetch_records(conn, *, limit: int | None, skip_existing: bool) -> list[tuple[int, str]]:
    where_clause = ""
    if skip_existing:
        where_clause = """
        WHERE NOT EXISTS (
          SELECT 1
          FROM audio_segments seg
          WHERE seg.sample_id = samples.id
        )
        """

    limit_clause = ""
    params: tuple[int, ...] = ()
    if limit is not None:
        limit_clause = "LIMIT %s"
        params = (limit,)

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT samples.id, samples.file_path
            FROM audio_samples samples
            {where_clause}
            ORDER BY samples.id
            {limit_clause}
            """,
            params,
        )
        return [(int(row[0]), str(row[1])) for row in cur.fetchall()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate MERT embeddings for audio_samples.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of samples to process.",
    )
    parser.add_argument(
        "--include-existing",
        action="store_true",
        help="Recompute samples that already have audio_segments rows.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Torch device override, e.g. cpu, mps, cuda.",
    )
    parser.add_argument(
        "--allow-download",
        action="store_true",
        help="Allow Hugging Face downloads instead of requiring local cache.",
    )
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    with connect() as conn:
        records = fetch_records(
            conn,
            limit=args.limit,
            skip_existing=not args.include_existing,
        )
        if not records:
            print("No audio_samples records to embed.")
            return

        extractor = MertEmbeddingExtractor(
            local_files_only=not args.allow_download,
            device=args.device,
        )

        print(f"Embedding {len(records)} samples on {extractor.device}", flush=True)
        for index, record in enumerate(records, start=1):
            result = embed_and_store_sample_record(
                conn,
                record,
                extractor=extractor,
                project_root=Path(__file__).resolve().parents[2],
                local_files_only=not args.allow_download,
            )
            conn.commit()
            print(
                f"[{index}/{len(records)}] sample_id={result.sample_id} "
                f"segments={result.segment_count} file={result.file_path}",
                flush=True,
            )


if __name__ == "__main__":
    main()

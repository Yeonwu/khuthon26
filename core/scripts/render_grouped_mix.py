from __future__ import annotations

import argparse
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from audio_search import MertEmbeddingExtractor, render_grouped_mix_preview
from create_tables import ROOT, connect, load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description="Render grouped top-5 mix preview for a query audio.")
    parser.add_argument("--audio-path", type=Path, required=True)
    parser.add_argument("--output-name", default=None)
    parser.add_argument("--device", default=None)
    parser.add_argument("--per-group", type=int, default=5)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    with connect() as conn:
        extractor = MertEmbeddingExtractor(local_files_only=True, device=args.device)
        output_path = render_grouped_mix_preview(
            conn,
            args.audio_path,
            extractor=extractor,
            per_group=args.per_group,
            output_name=args.output_name,
        )
    print(output_path)


if __name__ == "__main__":
    main()

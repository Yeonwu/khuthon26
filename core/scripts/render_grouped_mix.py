from __future__ import annotations

import argparse
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from audio_search import MertEmbeddingExtractor, render_dual_previews
from create_tables import ROOT, connect, load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description="Render two previews for a query audio.")
    parser.add_argument("--audio-path", type=Path, required=True)
    parser.add_argument("--device", default=None)
    parser.add_argument("--per-group", type=int, default=5)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    with connect() as conn:
        extractor = MertEmbeddingExtractor(local_files_only=True, device=args.device)
        generated_1, generated_2 = render_dual_previews(
            conn,
            args.audio_path,
            extractor=extractor,
            per_group=args.per_group,
        )
    print(generated_1)
    print(generated_2)


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from audio_search import MertEmbeddingExtractor, find_similar_audio_groups
from create_tables import ROOT, connect, load_dotenv


def main() -> None:
    parser = argparse.ArgumentParser(description="Run grouped query search for test_audio2.")
    parser.add_argument("--audio-path", type=Path, default=CORE_ROOT.parent / "test_audio2.mp3")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--device", default=None)
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    with connect() as conn:
        extractor = MertEmbeddingExtractor(local_files_only=True, device=args.device)
        groups = find_similar_audio_groups(
            conn,
            args.audio_path,
            args.k,
            extractor=extractor,
        )

    for group in groups:
        print(f"\n[{group['group']}] onsets={group['onset_count']}")
        onset_preview = ", ".join(f"{time:.2f}" for time in group["onset_times"][:12])
        if onset_preview:
            print(f"onset_times={onset_preview}")
        for rank, (file_path, score, start, end) in enumerate(group["matches"], start=1):
            print(f"{rank}. score={score:.4f} segment={start:.2f}-{end:.2f}s {file_path}")


if __name__ == "__main__":
    main()

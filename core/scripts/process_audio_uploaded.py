from __future__ import annotations

import argparse
import sys
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1]
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from audio_search import MertEmbeddingExtractor, render_dual_previews
from create_tables import ROOT, connect, load_dotenv


def iter_audio_files(audio_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in audio_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".mp4"}
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Process files under audio_uploaded, render previews, then delete them.")
    parser.add_argument("--audio-dir", type=Path, default=CORE_ROOT.parent / "audio_uploaded")
    parser.add_argument("--device", default=None)
    parser.add_argument("--per-group", type=int, default=5)
    args = parser.parse_args()

    audio_dir = args.audio_dir.resolve()
    if not audio_dir.exists():
        raise SystemExit(f"audio directory does not exist: {audio_dir}")

    load_dotenv(ROOT / ".env")
    audio_files = iter_audio_files(audio_dir)
    if not audio_files:
        print(f"No audio files found under {audio_dir}")
        return

    with connect() as conn:
        extractor = MertEmbeddingExtractor(local_files_only=True, device=args.device)
        for index, audio_path in enumerate(audio_files, start=1):
            try:
                generated_1, generated_2 = render_dual_previews(
                    conn,
                    audio_path,
                    extractor=extractor,
                    per_group=args.per_group,
                )
                print(f"[{index}/{len(audio_files)}] {audio_path.name}")
                print(f"  {generated_1}")
                print(f"  {generated_2}")
                audio_path.unlink()
            except Exception as exc:
                print(f"[{index}/{len(audio_files)}] FAILED {audio_path.name}: {exc}")


if __name__ == "__main__":
    main()

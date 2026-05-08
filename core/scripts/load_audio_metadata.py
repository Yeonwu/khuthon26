from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import soundfile as sf

from create_tables import ROOT, connect, load_dotenv


PROJECT_ROOT = ROOT.parent


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_audio_files(audio_dir: Path) -> list[Path]:
    return sorted(path for path in audio_dir.rglob("*.wav") if path.is_file())


def relative_to_project(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def main() -> None:
    parser = argparse.ArgumentParser(description="Load local audio file metadata into audio_samples.")
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=PROJECT_ROOT / "audio",
        help="Directory containing source WAV files.",
    )
    parser.add_argument(
        "--source",
        default="local_audio",
        help="Value to store in audio_samples.source.",
    )
    args = parser.parse_args()

    audio_dir = args.audio_dir.resolve()
    if not audio_dir.exists():
        raise SystemExit(f"Audio directory does not exist: {audio_dir}")

    load_dotenv(ROOT / ".env")
    audio_files = iter_audio_files(audio_dir)
    if not audio_files:
        raise SystemExit(f"No WAV files found under: {audio_dir}")

    inserted_or_updated = 0
    skipped_duplicate_hash = 0
    seen_hashes: set[str] = set()

    with connect() as conn:
        with conn.cursor() as cur:
            for index, path in enumerate(audio_files, start=1):
                info = sf.info(path)
                file_hash = sha256_file(path)
                if file_hash in seen_hashes:
                    skipped_duplicate_hash += 1
                    continue
                seen_hashes.add(file_hash)

                cur.execute(
                    """
                    INSERT INTO audio_samples (
                      file_path,
                      file_name,
                      file_sha256,
                      duration_seconds,
                      original_sample_rate,
                      original_channels,
                      source
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (file_path) DO UPDATE SET
                      file_name = EXCLUDED.file_name,
                      file_sha256 = EXCLUDED.file_sha256,
                      duration_seconds = EXCLUDED.duration_seconds,
                      original_sample_rate = EXCLUDED.original_sample_rate,
                      original_channels = EXCLUDED.original_channels,
                      source = EXCLUDED.source
                    """,
                    (
                        relative_to_project(path),
                        path.name,
                        file_hash,
                        float(info.duration),
                        int(info.samplerate),
                        int(info.channels),
                        args.source,
                    ),
                )
                inserted_or_updated += 1

                if index % 100 == 0:
                    print(f"Processed {index}/{len(audio_files)} files", flush=True)

            cur.execute("SELECT count(*) FROM audio_samples")
            total_rows = cur.fetchone()[0]

    print(f"Scanned WAV files: {len(audio_files)}")
    print(f"Inserted or updated: {inserted_or_updated}")
    print(f"Skipped duplicate hashes in this run: {skipped_duplicate_hash}")
    print(f"audio_samples rows: {total_rows}")


if __name__ == "__main__":
    main()

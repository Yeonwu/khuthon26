from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as AF

CORE_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = CORE_ROOT.parent
if str(CORE_ROOT) not in sys.path:
    sys.path.insert(0, str(CORE_ROOT))

from audio_search import MertEmbeddingExtractor, find_similar_audio_groups
from create_tables import ROOT, connect, load_dotenv


TARGET_SR = 44_100


def load_audio(path: Path, sample_rate: int = TARGET_SR) -> np.ndarray:
    audio, source_sr = sf.read(path, always_2d=True, dtype="float32")
    mono = audio.mean(axis=1)
    if source_sr != sample_rate:
        waveform = torch.from_numpy(mono).unsqueeze(0)
        mono = AF.resample(waveform, source_sr, sample_rate).squeeze(0).numpy()
    return mono.astype(np.float32, copy=False)


def estimate_bpm(audio: np.ndarray, sample_rate: int = TARGET_SR) -> float:
    frame_length = 1024
    hop_length = 512
    if audio.size < frame_length * 4:
        return 120.0

    frames = []
    for start in range(0, audio.size - frame_length + 1, hop_length):
        frame = audio[start : start + frame_length]
        frames.append(float(np.sqrt(np.mean(frame * frame))))
    energy = np.asarray(frames, dtype=np.float32)
    novelty = np.maximum(0.0, np.diff(energy, prepend=energy[0]))
    if float(novelty.max()) <= 0:
        return 120.0

    novelty = novelty - novelty.mean()
    autocorr = np.correlate(novelty, novelty, mode="full")[novelty.size - 1 :]
    min_bpm = 70.0
    max_bpm = 180.0
    min_lag = int(round((60.0 / max_bpm) * sample_rate / hop_length))
    max_lag = int(round((60.0 / min_bpm) * sample_rate / hop_length))
    max_lag = min(max_lag, autocorr.size - 1)
    if max_lag <= min_lag:
        return 120.0

    lag = int(np.argmax(autocorr[min_lag : max_lag + 1]) + min_lag)
    bpm = 60.0 * sample_rate / (lag * hop_length)
    while bpm < 80:
        bpm *= 2
    while bpm > 180:
        bpm /= 2
    return float(bpm)


def atempo_filter(factor: float) -> str:
    parts = []
    remaining = factor
    while remaining > 2.0:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.6f}")
    return ",".join(parts)


def stretch_with_ffmpeg(input_path: Path, output_path: Path, factor: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-filter:a",
            atempo_filter(factor),
            str(output_path),
        ],
        check=True,
    )


def fit_length(audio: np.ndarray, length: int) -> np.ndarray:
    if audio.size == length:
        return audio
    if audio.size > length:
        return audio[:length]
    repeat_count = int(np.ceil(length / max(1, audio.size)))
    return np.tile(audio, repeat_count)[:length]


def normalize(audio: np.ndarray, peak: float = 0.95) -> np.ndarray:
    max_abs = float(np.max(np.abs(audio))) if audio.size else 0.0
    if max_abs <= 0:
        return audio
    return (audio / max_abs * peak).astype(np.float32)


def pick_top3(groups: list[dict[str, object]]) -> list[tuple[str, str, float]]:
    rows: list[tuple[str, str, float]] = []
    for group in groups:
        for file_path, score, _, _ in group["matches"]:
            rows.append((str(group["group"]), str(file_path), float(score)))
    rows.sort(key=lambda row: row[2], reverse=True)

    selected = []
    seen = set()
    for row in rows:
        if row[1] in seen:
            continue
        selected.append(row)
        seen.add(row[1])
        if len(selected) == 3:
            break
    return selected


def pick_one_per_group(groups: list[dict[str, object]]) -> list[tuple[str, str, float]]:
    selected = []
    seen = set()
    for group_name in ("low_hit", "mid_hit", "high_hit"):
        group = next((item for item in groups if item["group"] == group_name), None)
        if not group:
            continue
        for file_path, score, _, _ in group["matches"]:
            if file_path in seen:
                continue
            selected.append((group_name, str(file_path), float(score)))
            seen.add(file_path)
            break
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="Mix top-3 grouped search results to test_audio2 BPM.")
    parser.add_argument("--query", type=Path, default=PROJECT_ROOT / "test_audio2.mp3")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "test_audio2_top3_bpm_mix.wav")
    parser.add_argument("-k", type=int, default=5)
    parser.add_argument("--device", default=None)
    parser.add_argument(
        "--selection",
        choices=("one-per-group", "top3"),
        default="one-per-group",
        help="How to select three source samples from grouped search results.",
    )
    args = parser.parse_args()

    query_audio = load_audio(args.query)
    target_bpm = estimate_bpm(query_audio)
    target_length = query_audio.size

    load_dotenv(ROOT / ".env")
    with connect() as conn:
        extractor = MertEmbeddingExtractor(local_files_only=True, device=args.device)
        groups = find_similar_audio_groups(conn, args.query, args.k, extractor=extractor)

    top3 = pick_one_per_group(groups) if args.selection == "one-per-group" else pick_top3(groups)
    if len(top3) < 3:
        raise SystemExit("Could not find 3 search results to mix.")

    layers = []
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        for index, (group, file_path, score) in enumerate(top3, start=1):
            source_path = PROJECT_ROOT / file_path
            source_audio = load_audio(source_path)
            source_bpm = estimate_bpm(source_audio)
            tempo_factor = target_bpm / source_bpm

            raw_path = tmp_dir / f"source_{index}.wav"
            stretched_path = tmp_dir / f"stretched_{index}.wav"
            sf.write(raw_path, normalize(source_audio), TARGET_SR)
            stretch_with_ffmpeg(raw_path, stretched_path, tempo_factor)
            stretched = load_audio(stretched_path)
            layers.append(fit_length(normalize(stretched, peak=0.75), target_length))
            print(
                f"{index}. group={group} score={score:.4f} "
                f"source_bpm={source_bpm:.2f} target_bpm={target_bpm:.2f} "
                f"factor={tempo_factor:.4f} file={file_path}",
                flush=True,
            )

    mix = np.zeros(target_length, dtype=np.float32)
    for layer in layers:
        mix += layer / len(layers)
    mix = normalize(mix)
    sf.write(args.output, mix, TARGET_SR)
    print(f"wrote={args.output}")


if __name__ == "__main__":
    main()

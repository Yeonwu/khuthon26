from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as AF

from audio_search.embedding import MertEmbeddingExtractor
from audio_search.search import find_similar_audio_groups


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_SR = 44_100


@dataclass(frozen=True)
class RankedMatch:
    group: str
    file_path: str
    score: float


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
        return audio.astype(np.float32, copy=False)
    return (audio / max_abs * peak).astype(np.float32)


def pick_top_k_per_group(
    groups: list[dict[str, object]],
    *,
    per_group: int = 5,
) -> list[RankedMatch]:
    selected: list[RankedMatch] = []
    seen: set[str] = set()
    for group_name in ("low_hit", "mid_hit", "high_hit"):
        group = next((item for item in groups if item["group"] == group_name), None)
        if not group:
            continue
        taken = 0
        for file_path, score, _, _ in group["matches"]:
            if str(file_path) in seen:
                continue
            selected.append(RankedMatch(group=group_name, file_path=str(file_path), score=float(score)))
            seen.add(str(file_path))
            taken += 1
            if taken >= per_group:
                break
    return selected


def render_grouped_mix_preview(
    conn,
    query_path: str | Path,
    *,
    extractor: MertEmbeddingExtractor | None = None,
    local_files_only: bool = True,
    device: str | None = None,
    per_group: int = 5,
    output_dir: Path | None = None,
    output_name: str | None = None,
) -> Path:
    owns_extractor = extractor is None
    if extractor is None:
        extractor = MertEmbeddingExtractor(local_files_only=local_files_only, device=device)

    try:
        query_audio = load_audio(Path(query_path))
        target_bpm = estimate_bpm(query_audio)
        target_length = query_audio.size

        groups = find_similar_audio_groups(
            conn,
            query_path,
            per_group,
            extractor=extractor,
            local_files_only=local_files_only,
        )
        selected = pick_top_k_per_group(groups, per_group=per_group)
        if len(selected) < 3:
            raise ValueError("Not enough matches to render a grouped mix preview")

        output_root = output_dir or (PROJECT_ROOT / "audio_generated")
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / (output_name or f"{Path(query_path).stem}_grouped_mix.wav")

        group_stems: list[np.ndarray] = []
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            for group_name in ("low_hit", "high_hit"):
                group_matches = [match for match in selected if match.group == group_name]
                if not group_matches:
                    continue

                group_layers: list[np.ndarray] = []
                for index, match in enumerate(group_matches, start=1):
                    source_path = Path(match.file_path)
                    if not source_path.is_absolute():
                        source_path = PROJECT_ROOT / source_path
                    source_audio = load_audio(source_path)
                    source_bpm = estimate_bpm(source_audio)
                    tempo_factor = target_bpm / source_bpm if source_bpm > 0 else 1.0

                    stretched_path = tmp_dir / f"{group_name}_{index}.wav"
                    stretch_with_ffmpeg(source_path, stretched_path, tempo_factor)
                    stretched = load_audio(stretched_path)
                    group_layers.append(fit_length(normalize(stretched, peak=0.75), target_length))

                if not group_layers:
                    continue

                group_mix = np.zeros(target_length, dtype=np.float32)
                for layer in group_layers:
                    group_mix += layer / len(group_layers)
                group_stems.append(normalize(group_mix, peak=0.9))

        if not group_stems:
            raise ValueError("No group stems were rendered")

        final_mix = np.zeros(target_length, dtype=np.float32)
        for stem in group_stems:
            final_mix += stem / len(group_stems)
        sf.write(output_path, normalize(final_mix), TARGET_SR)
        return output_path
    finally:
        if owns_extractor:
            del extractor

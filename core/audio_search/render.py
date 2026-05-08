from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as AF

from audio_search.embedding import MertEmbeddingExtractor, load_audio_array
from audio_search.search import find_similar_audio_groups


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TARGET_SR = 44_100
MIN_BPM = 70.0
MAX_BPM = 180.0


@dataclass(frozen=True)
class RankedMatch:
    group: str
    file_path: str
    score: float


def load_audio(path: Path, sample_rate: int = TARGET_SR) -> np.ndarray:
    return load_audio_array(path, sample_rate).astype(np.float32, copy=False)


def _frame_energy(audio: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    if audio.size < frame_length:
        return np.asarray([], dtype=np.float32)

    energies = []
    for start in range(0, audio.size - frame_length + 1, hop_length):
        frame = audio[start : start + frame_length]
        energies.append(float(np.sqrt(np.mean(frame * frame))))
    return np.asarray(energies, dtype=np.float32)


def _peak_pick(envelope: np.ndarray, *, min_spacing: int, threshold: float) -> np.ndarray:
    if envelope.size < 3:
        return np.asarray([], dtype=np.int64)

    peaks: list[int] = []
    last_peak = -min_spacing
    for index in range(1, envelope.size - 1):
        if envelope[index] < threshold:
            continue
        if envelope[index] < envelope[index - 1] or envelope[index] < envelope[index + 1]:
            continue
        if peaks and index - last_peak < min_spacing:
            if envelope[index] > envelope[peaks[-1]]:
                peaks[-1] = index
                last_peak = index
            continue
        peaks.append(index)
        last_peak = index
    return np.asarray(peaks, dtype=np.int64)


def _tempo_from_peaks(peaks: np.ndarray, *, sample_rate: int, hop_length: int) -> float | None:
    if peaks.size < 2:
        return None

    intervals = np.diff(peaks)
    if intervals.size == 0:
        return None

    bpms = 60.0 * sample_rate / (intervals * hop_length)
    valid = bpms[(bpms >= MIN_BPM) & (bpms <= MAX_BPM)]
    if valid.size == 0:
        return None

    return float(np.median(valid))


def _tempo_from_autocorr(envelope: np.ndarray, *, sample_rate: int, hop_length: int) -> float | None:
    if envelope.size < 8:
        return None

    centered = envelope - float(envelope.mean())
    if float(np.max(np.abs(centered))) <= 0:
        return None

    autocorr = np.correlate(centered, centered, mode="full")[centered.size - 1 :]
    min_lag = int(round((60.0 / MAX_BPM) * sample_rate / hop_length))
    max_lag = int(round((60.0 / MIN_BPM) * sample_rate / hop_length))
    max_lag = min(max_lag, autocorr.size - 1)
    if max_lag <= min_lag:
        return None

    window = autocorr[min_lag : max_lag + 1]
    if window.size == 0:
        return None

    lag = int(np.argmax(window) + min_lag)
    if lag <= 0:
        return None
    bpm = 60.0 * sample_rate / (lag * hop_length)
    if bpm < MIN_BPM or bpm > MAX_BPM:
        return None
    return float(bpm)


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
    min_lag = int(round((60.0 / MAX_BPM) * sample_rate / hop_length))
    max_lag = int(round((60.0 / MIN_BPM) * sample_rate / hop_length))
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


def pick_top_k_per_groups(
    groups: list[dict[str, object]],
    *,
    per_group: int = 5,
    group_names: tuple[str, ...] = ("low_hit", "high_hit"),
) -> list[RankedMatch]:
    selected: list[RankedMatch] = []
    seen: set[str] = set()
    for group_name in group_names:
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


def pick_best_overall_match(groups: list[dict[str, object]]) -> RankedMatch:
    best: RankedMatch | None = None
    for group in groups:
        group_name = str(group["group"])
        for file_path, score, _, _ in group["matches"]:
            candidate = RankedMatch(group=group_name, file_path=str(file_path), score=float(score))
            if best is None or candidate.score > best.score:
                best = candidate
    if best is None:
        raise ValueError("No search matches were found")
    return best


def render_source_preview(
    *,
    source_path: str | Path,
    output_path: Path,
    sample_rate: int = TARGET_SR,
) -> Path:
    audio = load_audio(Path(source_path), sample_rate=sample_rate)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(output_path, normalize(audio), sample_rate)
    return output_path


def render_matched_source_preview(
    *,
    source_path: str | Path,
    output_path: Path,
    target_bpm: float,
    target_length: int,
    sample_rate: int = TARGET_SR,
) -> Path:
    source_path = Path(source_path)
    source_audio = load_audio(source_path, sample_rate=sample_rate)
    source_bpm = estimate_bpm(source_audio, sample_rate=sample_rate)
    tempo_factor = target_bpm / source_bpm if source_bpm > 0 else 1.0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp_dir_name:
        tmp_dir = Path(tmp_dir_name)
        raw_path = tmp_dir / "source.wav"
        stretched_path = tmp_dir / "stretched.wav"
        sf.write(raw_path, normalize(source_audio), sample_rate)
        stretch_with_ffmpeg(raw_path, stretched_path, tempo_factor)
        stretched = load_audio(stretched_path, sample_rate=sample_rate)
        preview = fit_length(normalize(stretched), target_length)
        sf.write(output_path, preview, sample_rate)
    return output_path


def render_best_match_preview(
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
            max(1, per_group),
            extractor=extractor,
            local_files_only=local_files_only,
        )
        match = pick_best_overall_match(groups)
        output_root = output_dir or (PROJECT_ROOT / "audio_generated")
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / (output_name or f"{Path(query_path).stem}_generated_1.wav")
        source_path = Path(match.file_path)
        if not source_path.is_absolute():
            source_path = PROJECT_ROOT / source_path
        return render_matched_source_preview(
            source_path=source_path,
            output_path=output_path,
            target_bpm=target_bpm,
            target_length=target_length,
        )
    finally:
        if owns_extractor:
            del extractor


def render_grouped_mix_preview(
    conn,
    query_path: str | Path,
    *,
    extractor: MertEmbeddingExtractor | None = None,
    local_files_only: bool = True,
    device: str | None = None,
    per_group: int = 5,
    group_names: tuple[str, ...] = ("low_hit", "high_hit"),
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
        selected = pick_top_k_per_groups(groups, per_group=per_group, group_names=group_names)
        if not selected:
            raise ValueError("Not enough matches to render a grouped mix preview")

        output_root = output_dir or (PROJECT_ROOT / "audio_generated")
        output_root.mkdir(parents=True, exist_ok=True)
        output_path = output_root / (output_name or f"{Path(query_path).stem}_grouped_mix.wav")

        group_stems: list[np.ndarray] = []
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            for group_name in group_names:
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


def render_dual_previews(
    conn,
    query_path: str | Path,
    *,
    extractor: MertEmbeddingExtractor | None = None,
    local_files_only: bool = True,
    device: str | None = None,
    per_group: int = 5,
    output_dir: Path | None = None,
) -> tuple[Path, Path]:
    output_root = output_dir or (PROJECT_ROOT / "audio_generated")
    output_root.mkdir(parents=True, exist_ok=True)
    base_name = Path(query_path).stem
    generated_1 = render_best_match_preview(
        conn,
        query_path,
        extractor=extractor,
        local_files_only=local_files_only,
        device=device,
        per_group=per_group,
        output_dir=output_root,
        output_name=f"{base_name}_generated_1.wav",
    )
    generated_2 = render_grouped_mix_preview(
        conn,
        query_path,
        extractor=extractor,
        local_files_only=local_files_only,
        device=device,
        per_group=per_group,
        group_names=("low_hit", "high_hit"),
        output_dir=output_root,
        output_name=f"{base_name}_generated_2.wav",
    )
    return generated_1, generated_2

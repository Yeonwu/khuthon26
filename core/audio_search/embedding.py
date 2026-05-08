from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass

import numpy as np
import soundfile as sf
import torch
import torchaudio.functional as AF
from transformers import AutoModel, Wav2Vec2FeatureExtractor


MODEL_ID = "m-a-p/MERT-v1-330M"
TARGET_SAMPLE_RATE = 24_000
MIN_SEGMENT_SECONDS = 4.0
MAX_SEGMENT_SECONDS = 5.0
SILENCE_TOP_DB = 45


@dataclass(frozen=True)
class AudioSegment:
    audio: np.ndarray
    start_seconds: float
    end_seconds: float
    segment_index: int
    segment_type: str
    sample_rate: int = TARGET_SAMPLE_RATE

    @property
    def duration_seconds(self) -> float:
        return len(self.audio) / self.sample_rate


@dataclass(frozen=True)
class EmbeddedSegment:
    segment: AudioSegment
    embedding: np.ndarray


@dataclass(frozen=True)
class QueryGroup:
    name: str
    segment: AudioSegment
    onset_times: tuple[float, ...]


def preprocess_audio(
    path: str | Path,
    *,
    target_sample_rate: int = TARGET_SAMPLE_RATE,
    silence_top_db: int = SILENCE_TOP_DB,
    peak_normalize: bool = True,
) -> np.ndarray:
    """Load audio as mono, resample, trim leading/trailing silence, and normalize."""
    audio, source_sample_rate = sf.read(path, always_2d=True, dtype="float32")
    audio = audio.mean(axis=1)
    if source_sample_rate != target_sample_rate:
        waveform = torch.from_numpy(audio).unsqueeze(0)
        audio = AF.resample(
            waveform,
            orig_freq=source_sample_rate,
            new_freq=target_sample_rate,
        ).squeeze(0).numpy()
    audio = np.asarray(audio, dtype=np.float32)

    if audio.size == 0:
        raise ValueError(f"Audio is empty: {path}")

    audio = trim_silence(audio, top_db=silence_top_db)

    if peak_normalize:
        peak = float(np.max(np.abs(audio)))
        if peak > 0:
            audio = audio / peak

    return audio.astype(np.float32, copy=False)


def trim_silence(
    audio: np.ndarray,
    *,
    top_db: int = SILENCE_TOP_DB,
    frame_length: int = 2048,
    hop_length: int = 512,
) -> np.ndarray:
    if audio.size < frame_length:
        return audio

    frames = []
    for start in range(0, audio.size - frame_length + 1, hop_length):
        frame = audio[start : start + frame_length]
        frames.append(float(np.sqrt(np.mean(frame * frame))))
    if not frames:
        return audio

    rms = np.asarray(frames, dtype=np.float32)
    max_rms = float(rms.max())
    if max_rms <= 0:
        return audio

    threshold = max_rms * (10 ** (-top_db / 20))
    active = np.flatnonzero(rms >= threshold)
    if active.size == 0:
        return audio

    start_frame = int(active[0])
    end_frame = int(active[-1])
    start_sample = max(0, start_frame * hop_length)
    end_sample = min(audio.size, end_frame * hop_length + frame_length)
    return audio[start_sample:end_sample]


def segment_audio(
    audio: np.ndarray,
    *,
    sample_rate: int = TARGET_SAMPLE_RATE,
    min_segment_seconds: float = MIN_SEGMENT_SECONDS,
    max_segment_seconds: float = MAX_SEGMENT_SECONDS,
) -> list[AudioSegment]:
    """Create search segments without writing files.

    Short loops are repeated to at least min_segment_seconds. Longer loops are
    split into max_segment_seconds windows. The returned timestamps refer to
    the original audio timeline where possible.
    """
    if audio.ndim != 1:
        raise ValueError("segment_audio expects mono audio")
    if audio.size == 0:
        raise ValueError("segment_audio received empty audio")

    min_frames = int(round(min_segment_seconds * sample_rate))
    max_frames = int(round(max_segment_seconds * sample_rate))
    duration_seconds = len(audio) / sample_rate

    if len(audio) < min_frames:
        repeat_count = int(np.ceil(min_frames / len(audio)))
        repeated = np.tile(audio, repeat_count)[:min_frames].astype(np.float32, copy=False)
        return [
            AudioSegment(
                audio=repeated,
                start_seconds=0.0,
                end_seconds=duration_seconds,
                segment_index=0,
                segment_type="repeated_short_loop",
                sample_rate=sample_rate,
            )
        ]

    segments: list[AudioSegment] = []
    starts = list(range(0, len(audio), max_frames))
    if starts:
        last_start = starts[-1]
        last_length = len(audio) - last_start
        if last_length < min_frames:
            replacement_start = max(0, len(audio) - max_frames)
            if len(starts) == 1:
                starts[-1] = replacement_start
            elif replacement_start <= starts[-2]:
                starts.pop()
            else:
                starts[-1] = replacement_start

    for segment_index, start_frame in enumerate(starts):
        end_frame = min(start_frame + max_frames, len(audio))
        chunk = audio[start_frame:end_frame]
        if chunk.size == 0:
            continue
        segments.append(
            AudioSegment(
                audio=chunk.astype(np.float32, copy=False),
                start_seconds=start_frame / sample_rate,
                end_seconds=end_frame / sample_rate,
                segment_index=segment_index,
                segment_type="fixed_window",
                sample_rate=sample_rate,
            )
        )

    return segments


def detect_onsets(
    audio: np.ndarray,
    *,
    sample_rate: int = TARGET_SAMPLE_RATE,
    frame_length: int = 1024,
    hop_length: int = 256,
    min_spacing_seconds: float = 0.08,
    threshold_ratio: float = 0.35,
) -> np.ndarray:
    if audio.size < frame_length:
        return np.asarray([0], dtype=np.int64)

    energies = []
    for start in range(0, audio.size - frame_length + 1, hop_length):
        frame = audio[start : start + frame_length]
        energies.append(float(np.sqrt(np.mean(frame * frame))))
    energy = np.asarray(energies, dtype=np.float32)
    novelty = np.maximum(0.0, np.diff(energy, prepend=energy[0]))
    if novelty.size == 0 or float(novelty.max()) <= 0:
        return np.asarray([0], dtype=np.int64)

    threshold = max(float(novelty.mean() + novelty.std()), float(novelty.max() * threshold_ratio))
    min_spacing = max(1, int(round(min_spacing_seconds * sample_rate / hop_length)))
    candidates = np.flatnonzero(novelty >= threshold)

    peaks: list[int] = []
    last_peak = -min_spacing
    for index in candidates:
        left = max(0, index - 1)
        right = min(novelty.size, index + 2)
        if novelty[index] < novelty[left:right].max():
            continue
        if index - last_peak < min_spacing:
            if peaks and novelty[index] > novelty[peaks[-1]]:
                peaks[-1] = int(index)
                last_peak = int(index)
            continue
        peaks.append(int(index))
        last_peak = int(index)

    if not peaks:
        return np.asarray([0], dtype=np.int64)
    return np.asarray([peak * hop_length for peak in peaks], dtype=np.int64)


def classify_event(audio: np.ndarray, *, sample_rate: int = TARGET_SAMPLE_RATE) -> str:
    if audio.size == 0:
        return "mid_hit"

    spectrum = np.abs(np.fft.rfft(audio * np.hanning(audio.size)))
    freqs = np.fft.rfftfreq(audio.size, d=1 / sample_rate)
    total = float(np.sum(spectrum) + 1e-8)
    low_ratio = float(np.sum(spectrum[freqs < 250]) / total)
    high_ratio = float(np.sum(spectrum[freqs >= 3500]) / total)

    if low_ratio >= 0.32:
        return "low_hit"
    if high_ratio >= 0.38:
        return "high_hit"
    return "mid_hit"


def make_query_groups(
    audio: np.ndarray,
    *,
    sample_rate: int = TARGET_SAMPLE_RATE,
    min_segment_seconds: float = MIN_SEGMENT_SECONDS,
    pre_onset_seconds: float = 0.03,
    post_onset_seconds: float = 0.55,
) -> list[QueryGroup]:
    onset_frames = detect_onsets(audio, sample_rate=sample_rate)
    pre_frames = int(round(pre_onset_seconds * sample_rate))
    post_frames = int(round(post_onset_seconds * sample_rate))
    min_frames = int(round(min_segment_seconds * sample_rate))

    grouped_events: dict[str, list[np.ndarray]] = {
        "low_hit": [],
        "mid_hit": [],
        "high_hit": [],
    }
    grouped_times: dict[str, list[float]] = {
        "low_hit": [],
        "mid_hit": [],
        "high_hit": [],
    }

    for onset_frame in onset_frames:
        start = max(0, int(onset_frame) - pre_frames)
        end = min(audio.size, int(onset_frame) + post_frames)
        event = audio[start:end]
        if event.size == 0:
            continue
        group = classify_event(event, sample_rate=sample_rate)
        grouped_events[group].append(event.astype(np.float32, copy=False))
        grouped_times[group].append(int(onset_frame) / sample_rate)

    query_groups: list[QueryGroup] = []
    for index, name in enumerate(("low_hit", "mid_hit", "high_hit")):
        events = grouped_events[name]
        if not events:
            continue
        group_audio = np.concatenate(events)
        if group_audio.size < min_frames:
            repeat_count = int(np.ceil(min_frames / group_audio.size))
            group_audio = np.tile(group_audio, repeat_count)[:min_frames]
        peak = float(np.max(np.abs(group_audio)))
        if peak > 0:
            group_audio = group_audio / peak
        segment = AudioSegment(
            audio=group_audio.astype(np.float32, copy=False),
            start_seconds=0.0,
            end_seconds=len(group_audio) / sample_rate,
            segment_index=index,
            segment_type=f"query_group_{name}",
            sample_rate=sample_rate,
        )
        query_groups.append(
            QueryGroup(
                name=name,
                segment=segment,
                onset_times=tuple(grouped_times[name]),
            )
        )

    return query_groups


def select_device(preferred_device: str | None = None) -> torch.device:
    if preferred_device:
        return torch.device(preferred_device)
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


class MertEmbeddingExtractor:
    def __init__(
        self,
        *,
        model_id: str = MODEL_ID,
        device: str | None = None,
        local_files_only: bool = False,
    ) -> None:
        self.model_id = model_id
        self.device = select_device(device)
        self.processor = Wav2Vec2FeatureExtractor.from_pretrained(
            model_id,
            trust_remote_code=True,
            local_files_only=local_files_only,
        )
        self.model = AutoModel.from_pretrained(
            model_id,
            trust_remote_code=True,
            local_files_only=local_files_only,
        ).to(self.device)
        self.model.eval()

    @property
    def sample_rate(self) -> int:
        return int(self.processor.sampling_rate)

    def embed_segment(self, segment: AudioSegment) -> EmbeddedSegment:
        inputs = self.processor(
            segment.audio,
            sampling_rate=segment.sample_rate,
            return_tensors="pt",
        )
        inputs = {name: value.to(self.device) for name, value in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs, output_hidden_states=True)

        hidden_states = torch.stack(outputs.hidden_states).squeeze(1)
        embedding = hidden_states.mean(dim=(0, 1)).detach().cpu().numpy()
        return EmbeddedSegment(segment=segment, embedding=embedding.astype(np.float32))

    def embed_segments(self, segments: list[AudioSegment]) -> list[EmbeddedSegment]:
        return [self.embed_segment(segment) for segment in segments]

    def embed_file(self, path: str | Path) -> list[EmbeddedSegment]:
        audio = preprocess_audio(path, target_sample_rate=self.sample_rate)
        segments = segment_audio(audio, sample_rate=self.sample_rate)
        return self.embed_segments(segments)

    def embed_query_groups(self, path: str | Path) -> list[tuple[QueryGroup, EmbeddedSegment]]:
        audio = preprocess_audio(path, target_sample_rate=self.sample_rate)
        groups = make_query_groups(audio, sample_rate=self.sample_rate)
        return [(group, self.embed_segment(group.segment)) for group in groups]

from __future__ import annotations

import argparse
import math

import torch
from transformers import AutoModel, Wav2Vec2FeatureExtractor


MODEL_ID = "m-a-p/MERT-v1-330M"


def select_device() -> torch.device:
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def make_sine_wave(sample_rate: int, seconds: float = 2.0) -> torch.Tensor:
    frame_count = int(sample_rate * seconds)
    time = torch.arange(frame_count, dtype=torch.float32) / sample_rate
    return 0.2 * torch.sin(2 * math.pi * 440.0 * time)


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke test m-a-p/MERT-v1-330M locally.")
    parser.add_argument(
        "--model-id",
        default=MODEL_ID,
        help="Hugging Face model id to load.",
    )
    parser.add_argument(
        "--seconds",
        type=float,
        default=2.0,
        help="Synthetic audio duration in seconds.",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="Use only files that already exist in the Hugging Face cache.",
    )
    args = parser.parse_args()

    device = select_device()
    print(f"Loading processor: {args.model_id}", flush=True)
    processor = Wav2Vec2FeatureExtractor.from_pretrained(
        args.model_id,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )

    print(f"Loading model on {device}: {args.model_id}", flush=True)
    model = AutoModel.from_pretrained(
        args.model_id,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    ).to(device)
    model.eval()

    sample_rate = int(processor.sampling_rate)
    audio = make_sine_wave(sample_rate=sample_rate, seconds=args.seconds)
    inputs = processor(audio.numpy(), sampling_rate=sample_rate, return_tensors="pt")
    inputs = {name: value.to(device) for name, value in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs, output_hidden_states=True)

    hidden_states = torch.stack(outputs.hidden_states).squeeze(1)
    time_reduced = hidden_states.mean(dim=-2)

    print(f"Processor sampling rate: {sample_rate}")
    print(f"Hidden states shape: {tuple(hidden_states.shape)}")
    print(f"Time-reduced shape: {tuple(time_reduced.shape)}")


if __name__ == "__main__":
    main()

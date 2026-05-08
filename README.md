# khuthon26

Local setup for running the Hugging Face model
[`m-a-p/MERT-v1-330M`](https://huggingface.co/m-a-p/MERT-v1-330M).

## Setup

Create and activate the conda environment:

```bash
conda env create -f environment.yml
conda activate khuthon26
```

If the environment already exists and you want to sync it with this file:

```bash
conda env update -n khuthon26 -f environment.yml --prune
```

## Smoke Test

Run a short synthetic-audio inference test:

```bash
python scripts/run_mert_smoke.py
```

The first run downloads the model into the Hugging Face cache. Expected output
includes a processor sampling rate of `24000`, hidden states with 25 layers, and
a feature dimension of `1024`.

After the first successful download, you can force cache-only execution:

```bash
python scripts/run_mert_smoke.py --local-files-only
```

## Core Usage

Project code lives under `core/`.

```bash
cd core
conda activate khuthon26
```

Use MERT embeddings from Python without writing files:

```python
from audio_search import MertEmbeddingExtractor

extractor = MertEmbeddingExtractor(local_files_only=True)
segments = extractor.embed_file("../audio/P1-001-050.wav")

for item in segments:
    print(item.segment.start_seconds, item.segment.end_seconds, item.embedding.shape)
```

## Database And API

Create the tables:

```bash
cd core
conda run -n khuthon26 python scripts/create_tables.py
```

Load local WAV metadata into `audio_samples`:

```bash
cd core
conda run -n khuthon26 python scripts/load_audio_metadata.py
```

Run the recommendation API:

```bash
cd core
conda run -n khuthon26 uvicorn api.server:app --host 127.0.0.1 --port 8001
```

The API accepts `multipart/form-data` at `POST /api/v1/recommendations` with:

```text
file=<audio_file>
top_k=<number>
```

It returns relative audio paths in this shape:

```json
[
  {
    "file_url": "audio/sample.wav"
  }
]
```

Render a grouped mix preview for a specific query file:

```bash
cd core
conda run -n khuthon26 python scripts/render_grouped_mix.py --audio-path ../test_audio2.mp3
```

This writes two files under `audio_generated/`:

- `<input>_generated_1.wav` from the previous all-group ranking
- `<input>_generated_2.wav` from the current low/high grouped mix

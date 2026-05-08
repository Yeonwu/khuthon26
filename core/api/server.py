from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles

from audio_search import MertEmbeddingExtractor, find_similar_audio_paths
from scripts.create_tables import ROOT, connect, load_dotenv


app = FastAPI(title="Khuthon26 Audio Recommendations API")

# Mount static directories
app.mount("/audio", StaticFiles(directory=str(ROOT.parent / "audio")), name="audio")
app.mount("/audio_generated", StaticFiles(directory=str(ROOT.parent / "audio_generated")), name="audio_generated")

extractor: MertEmbeddingExtractor | None = None


def ensure_env_loaded() -> None:
    load_dotenv(ROOT / ".env")


def get_extractor() -> MertEmbeddingExtractor:
    global extractor
    if extractor is None:
        ensure_env_loaded()
        extractor = MertEmbeddingExtractor(local_files_only=True)
    return extractor


@app.on_event("shutdown")
def shutdown() -> None:
    global extractor
    extractor = None


@app.post("/api/v1/recommendations")
def create_recommendations(
    file: UploadFile = File(...),
    top_k: int = Form(...),
) -> list[dict[str, str]]:
    if top_k <= 0:
        raise HTTPException(status_code=400, detail="top_k must be greater than 0")

    suffix = Path(file.filename or "").suffix
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            shutil.copyfileobj(file.file, temp_file)

        ensure_env_loaded()
        with connect() as conn:
            paths = find_similar_audio_paths(
                conn,
                temp_path,
                top_k,
                extractor=get_extractor(),
                local_files_only=True,
            )
        return [{"file_url": path} for path in paths]
    finally:
        file.file.close()
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

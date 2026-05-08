from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from audio_search import MertEmbeddingExtractor, find_similar_audio_paths, render_dual_previews
from scripts.create_tables import ROOT, connect, load_dotenv


PROJECT_ROOT = ROOT.parent
AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac", ".mp4"}
UPLOAD_DIR = PROJECT_ROOT / "audio_uploaded"
GENERATED_DIR = PROJECT_ROOT / "audio_generated"
HISTORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audio_uploads (
  id BIGSERIAL PRIMARY KEY,
  original_filename TEXT NOT NULL,
  stored_filename TEXT NOT NULL UNIQUE,
  file_path TEXT NOT NULL,
  file_size BIGINT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded',
  error_message TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audio_generations (
  id BIGSERIAL PRIMARY KEY,
  upload_id BIGINT NOT NULL REFERENCES audio_uploads(id) ON DELETE CASCADE,
  filename TEXT NOT NULL,
  file_path TEXT NOT NULL UNIQUE,
  file_size BIGINT NOT NULL,
  generation_type TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audio_uploads_created_at_idx
ON audio_uploads(created_at DESC);

CREATE INDEX IF NOT EXISTS audio_generations_upload_id_idx
ON audio_generations(upload_id);
"""

app = FastAPI(title="Khuthon26 Audio Recommendations API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static directories
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
GENERATED_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=str(PROJECT_ROOT / "audio")), name="audio")
app.mount("/audio_generated", StaticFiles(directory=str(GENERATED_DIR)), name="audio_generated")

extractor: MertEmbeddingExtractor | None = None
processing_lock = threading.Lock()


def ensure_env_loaded() -> None:
    load_dotenv(ROOT / ".env")


def get_extractor() -> MertEmbeddingExtractor:
    global extractor
    if extractor is None:
        ensure_env_loaded()
        extractor = MertEmbeddingExtractor(local_files_only=True)
    return extractor


def safe_filename(filename: str) -> str:
    cleaned = Path(filename).name.strip().replace("/", "_").replace("\\", "_")
    cleaned = "".join(char if char.isalnum() or char in "._- " else "_" for char in cleaned)
    return "_".join(cleaned.split()) or "upload"


def iter_generated_audio() -> list[Path]:
    return sorted(
        (
            path
            for path in GENERATED_DIR.rglob("*")
            if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def ensure_history_schema(conn) -> None:
    with conn.cursor() as cur:
        cur.execute(HISTORY_SCHEMA_SQL)


def insert_upload_record(destination: Path, original_name: str) -> int:
    ensure_env_loaded()
    with connect() as conn:
        ensure_history_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audio_uploads (
                  original_filename,
                  stored_filename,
                  file_path,
                  file_size,
                  status
                )
                VALUES (%s, %s, %s, %s, 'processing')
                RETURNING id
                """,
                (
                    original_name,
                    destination.name,
                    str(destination.relative_to(PROJECT_ROOT)),
                    destination.stat().st_size,
                ),
            )
            row = cur.fetchone()
            if row is None:
                raise RuntimeError("failed to insert upload record")
            return int(row[0])


def update_upload_status(upload_id: int, status: str, error_message: str | None = None) -> None:
    ensure_env_loaded()
    with connect() as conn:
        ensure_history_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE audio_uploads
                SET status = %s,
                    error_message = %s,
                    updated_at = now()
                WHERE id = %s
                """,
                (status, error_message, upload_id),
            )


def insert_generation_record(upload_id: int, path: Path, generation_type: str) -> None:
    ensure_env_loaded()
    with connect() as conn:
        ensure_history_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audio_generations (
                  upload_id,
                  filename,
                  file_path,
                  file_size,
                  generation_type
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (file_path) DO UPDATE
                SET file_size = EXCLUDED.file_size,
                    generation_type = EXCLUDED.generation_type
                """,
                (
                    upload_id,
                    path.name,
                    str(path.relative_to(PROJECT_ROOT)),
                    path.stat().st_size,
                    generation_type,
                ),
            )


def process_uploaded_audio(upload_id: int, audio_path: Path, per_group: int = 5) -> None:
    with processing_lock:
        try:
            ensure_env_loaded()
            with connect() as conn:
                ensure_history_schema(conn)
                generated_1, generated_2 = render_dual_previews(
                    conn,
                    audio_path,
                    extractor=get_extractor(),
                    local_files_only=True,
                    per_group=per_group,
                    output_dir=GENERATED_DIR,
                )
            insert_generation_record(upload_id, generated_1, "best_match")
            insert_generation_record(upload_id, generated_2, "grouped_mix")
            update_upload_status(upload_id, "completed")
            print(f"generated {generated_1}", file=sys.stderr)
            print(f"generated {generated_2}", file=sys.stderr)
            audio_path.unlink(missing_ok=True)
        except Exception as exc:
            update_upload_status(upload_id, "failed", str(exc))
            print(f"failed to process uploaded audio {audio_path}: {exc}", file=sys.stderr)


@app.on_event("shutdown")
def shutdown() -> None:
    global extractor
    extractor = None


@app.post("/api/v1/upload")
def upload_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
) -> dict[str, str | int | bool]:
    original_name = file.filename or "upload"
    suffix = Path(original_name).suffix.lower()
    if suffix not in AUDIO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="unsupported audio file type")

    filename = f"{int(time.time() * 1000)}_{safe_filename(original_name)}"
    destination = UPLOAD_DIR / filename

    try:
        with destination.open("xb") as handle:
            shutil.copyfileobj(file.file, handle)
    finally:
        file.file.close()

    upload_id = insert_upload_record(destination, original_name)
    background_tasks.add_task(process_uploaded_audio, upload_id, destination)

    return {
        "id": upload_id,
        "filename": filename,
        "path": str(destination.relative_to(PROJECT_ROOT)),
        "size": destination.stat().st_size,
        "processing": True,
    }


@app.get("/api/v1/uploads")
def list_uploads() -> list[dict[str, object]]:
    ensure_env_loaded()
    with connect() as conn:
        ensure_history_schema(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  u.id,
                  u.original_filename,
                  u.stored_filename,
                  u.file_path,
                  u.file_size,
                  u.status,
                  u.error_message,
                  u.created_at,
                  u.updated_at,
                  COALESCE(
                    json_agg(
                      json_build_object(
                        'id', g.id,
                        'filename', g.filename,
                        'url', '/' || g.file_path,
                        'size', g.file_size,
                        'generation_type', g.generation_type,
                        'created_at', g.created_at
                      )
                      ORDER BY g.created_at
                    ) FILTER (WHERE g.id IS NOT NULL),
                    '[]'::json
                  ) AS generations
                FROM audio_uploads u
                LEFT JOIN audio_generations g ON g.upload_id = u.id
                GROUP BY u.id
                ORDER BY u.created_at DESC
                """
            )
            rows = cur.fetchall()

    return [
        {
            "id": row[0],
            "original_filename": row[1],
            "stored_filename": row[2],
            "path": row[3],
            "size": row[4],
            "status": row[5],
            "error_message": row[6],
            "created_at": row[7],
            "updated_at": row[8],
            "generations": row[9],
        }
        for row in rows
    ]


@app.get("/api/v1/generated")
def list_generated_audio() -> list[dict[str, str | int | float]]:
    items = []
    for path in iter_generated_audio():
        stat = path.stat()
        relative = path.relative_to(GENERATED_DIR).as_posix()
        items.append(
            {
                "filename": path.name,
                "url": f"/audio_generated/{relative}",
                "size": stat.st_size,
                "modified": stat.st_mtime,
            }
        )
    return items


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

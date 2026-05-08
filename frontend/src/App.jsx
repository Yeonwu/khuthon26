import React, { useEffect, useMemo, useRef, useState } from 'react';

const API_URL = (import.meta.env.VITE_API_URL || '').replace(/\/$/, '');

function resolveUrl(path) {
  if (!path) return '';
  if (path.startsWith('http://') || path.startsWith('https://')) return path;
  return `${API_URL}/${path.replace(/^\//, '')}`;
}

function formatBytes(value) {
  if (!Number.isFinite(value)) return '';
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

async function downloadFile(url, filename) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`download failed: ${response.status}`);

  const blob = await response.blob();
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename || 'audio.wav';
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
}

function PlaybackSurface({ url, filename }) {
  const audioRef = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

  function togglePlayback() {
    const audio = audioRef.current;
    if (!audio) return;

    if (audio.paused) {
      audio.play();
    } else {
      audio.pause();
    }
  }

  return (
    <>
      <audio
        ref={audioRef}
        src={url}
        preload="metadata"
        onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)}
        onTimeUpdate={(event) => setCurrentTime(event.currentTarget.currentTime)}
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onEnded={() => setPlaying(false)}
      />
      <button
        type="button"
        className={`queue-title-area play-surface ${playing ? 'is-playing' : ''}`}
        onClick={togglePlayback}
        aria-label={`${filename} ${playing ? 'pause' : 'play'}`}
      >
        <span style={{ width: `${progress}%` }} />
        <strong>{filename}</strong>
      </button>
    </>
  );
}

export default function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploads, setUploads] = useState([]);
  const [localTasks, setLocalTasks] = useState([]);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const formRef = useRef(null);
  const stageRef = useRef(null);

  const canUpload = useMemo(() => Boolean(file && !uploading), [file, uploading]);

  async function refreshUploads() {
    try {
      const response = await fetch(`${API_URL}/api/v1/uploads`);
      if (!response.ok) throw new Error(`uploads failed: ${response.status}`);
      const data = await response.json();
      setUploads(data);
      setLocalTasks((tasks) =>
        tasks.filter(
          (task) =>
            !data.some(
              (upload) =>
                upload.original_filename === task.original_filename &&
                upload.size === task.size
            )
        )
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function uploadFile(event) {
    event.preventDefault();
    if (!file) return;

    setUploading(true);
    setError('');
    const taskId = `local-${Date.now()}`;
    const taskFile = file;
    setLocalTasks((tasks) => [
      {
        id: taskId,
        original_filename: taskFile.name,
        size: taskFile.size,
        status: 'processing',
        generations: [],
        isLocal: true,
      },
      ...tasks,
    ]);
    setFile(null);
    formRef.current?.reset();

    const formData = new FormData();
    formData.append('file', taskFile);

    try {
      const response = await fetch(`${API_URL}/api/v1/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `upload failed: ${response.status}`);
      await refreshUploads();
    } catch (err) {
      setLocalTasks((tasks) =>
        tasks.map((task) =>
          task.id === taskId
            ? { ...task, status: 'failed', error_message: err instanceof Error ? err.message : String(err) }
            : task
        )
      );
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  }

  async function handleDownload(url, filename) {
    setError('');
    try {
      await downloadFile(url, filename);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  useEffect(() => {
    refreshUploads();
    const timer = window.setInterval(refreshUploads, 3000);
    return () => window.clearInterval(timer);
  }, []);

  function handlePointerMove(event) {
    const stage = stageRef.current;
    if (!stage) return;

    const rect = stage.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;
    stage.style.setProperty('--tilt-x', `${(-y * 10).toFixed(2)}deg`);
    stage.style.setProperty('--tilt-y', `${(x * 14).toFixed(2)}deg`);
    stage.style.setProperty('--pointer-x', `${((x + 0.5) * 100).toFixed(2)}%`);
    stage.style.setProperty('--pointer-y', `${((y + 0.5) * 100).toFixed(2)}%`);
  }

  function handlePointerLeave() {
    const stage = stageRef.current;
    if (!stage) return;
    stage.style.setProperty('--tilt-x', '0deg');
    stage.style.setProperty('--tilt-y', '0deg');
  }

  function renderQueue() {
    const queueItems = [...localTasks, ...uploads];
    if (queueItems.length === 0) {
      return null;
    }

    return (
      <ul className="upload-list">
        {queueItems.map((upload) => {
          const generations = Array.isArray(upload.generations)
            ? upload.generations.filter((item) => item.generation_type !== 'grouped_mix')
            : [];
          const isGenerating = upload.status === 'processing' || generations.length === 0;
          return (
            <li className={`search-card upload-card status-${upload.status} ${upload.isLocal ? 'is-entering' : ''}`} key={upload.id}>
              {upload.error_message && <p className="error">{upload.error_message}</p>}

              {isGenerating ? (
                <>
                  <div className="queue-card-top">
                    <div className="queue-title-area">
                      <div className="queue-progress" aria-hidden="true">
                        {Array.from({ length: 18 }).map((_, index) => (
                          <span key={index} style={{ '--i': index }} />
                        ))}
                      </div>
                      <h3>{upload.original_filename}</h3>
                      <span>{formatBytes(upload.size)}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="result-strip">
                  {generations.slice(0, 1).map((item) => {
                    const audioUrl = resolveUrl(item.url);
                    return (
                      <div className="queue-card-top" key={item.id}>
                        <PlaybackSurface url={audioUrl} filename={upload.original_filename} />
                        <button
                          type="button"
                          className="download-button"
                          onClick={() => handleDownload(audioUrl, item.filename)}
                        >
                          download
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    );
  }

  return (
    <main className="app-shell">
      <section
        className="hero-stage"
        ref={stageRef}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
      >
        <div className="hero-grid">
          <div className="hero-copy">
            <h1>DigGak</h1>

            <form
              ref={formRef}
              className={`search-card upload-console ${dragging ? 'is-dragging' : ''}`}
              onSubmit={uploadFile}
              onDragEnter={() => setDragging(true)}
              onDragLeave={() => setDragging(false)}
              onDrop={() => setDragging(false)}
            >
              <input
                id="audio-file"
                type="file"
                accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg,.flac,.mp4"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
              <label htmlFor="audio-file">
                <strong className={file ? 'file-name' : 'upload-title'}>
                  {file ? file.name : 'Search By Audio'}
                </strong>
                {file && <span>{formatBytes(file.size)}</span>}
              </label>
              <button type="submit" disabled={!canUpload}>
                {uploading ? 'uploading' : 'generate'}
              </button>
            </form>

            {error && <p className="error">Error: {error}</p>}
            {renderQueue()}
          </div>

          <div className="visual-deck" aria-hidden="true">
            <div className="deck-plane deck-plane-a" />
            <div className="deck-plane deck-plane-b" />
            <div className="wave-stack">
              {Array.from({ length: 18 }).map((_, index) => (
                <span key={index} style={{ '--i': index }} />
              ))}
            </div>
            <div className="scan-ring scan-ring-a" />
            <div className="scan-ring scan-ring-b" />
          </div>
        </div>
      </section>
    </main>
  );
}

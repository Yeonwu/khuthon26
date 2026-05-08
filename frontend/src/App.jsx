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

export default function App() {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);
  const [uploads, setUploads] = useState([]);
  const [error, setError] = useState('');
  const formRef = useRef(null);

  const canUpload = useMemo(() => Boolean(file && !uploading), [file, uploading]);

  async function refreshUploads() {
    try {
      const response = await fetch(`${API_URL}/api/v1/uploads`);
      if (!response.ok) throw new Error(`uploads failed: ${response.status}`);
      const data = await response.json();
      setUploads(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function uploadFile(event) {
    event.preventDefault();
    if (!file) return;

    setUploading(true);
    setError('');
    setUploadResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch(`${API_URL}/api/v1/upload`, {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `upload failed: ${response.status}`);
      setUploadResult(data);
      setFile(null);
      formRef.current?.reset();
      await refreshUploads();
    } catch (err) {
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

  return (
    <main>
      <h1>Audio Upload</h1>

      <form ref={formRef} onSubmit={uploadFile}>
        <input
          type="file"
          accept="audio/*,.mp3,.wav,.m4a,.aac,.ogg,.flac,.mp4"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
        />
        <button type="submit" disabled={!canUpload}>
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
      </form>

      {uploadResult && (
        <p>
          Uploaded: {uploadResult.path} ({formatBytes(uploadResult.size)})
          {uploadResult.processing ? ' - processing...' : ''}
        </p>
      )}

      {error && <p className="error">Error: {error}</p>}

      <section>
        <div className="section-header">
          <h2>Uploads</h2>
          <button type="button" onClick={refreshUploads}>
            Refresh
          </button>
        </div>

        {uploads.length === 0 ? (
          <p>No uploads yet.</p>
        ) : (
          <ul>
            {uploads.map((upload) => {
              const generations = Array.isArray(upload.generations) ? upload.generations : [];
              return (
                <li key={upload.id}>
                  <div>
                    <strong>{upload.original_filename}</strong>
                    <span>{upload.status}</span>
                  </div>
                  <p>
                    Uploaded file: {upload.path} ({formatBytes(upload.size)})
                  </p>
                  {upload.error_message && <p className="error">{upload.error_message}</p>}

                  {generations.length === 0 ? (
                    <p>No generated files for this upload yet.</p>
                  ) : (
                    <div className="generation-list">
                      {generations.map((item) => {
                        const audioUrl = resolveUrl(item.url);
                        return (
                          <div className="generation-item" key={item.id}>
                            <div>
                              <strong>{item.generation_type}</strong>
                              <span>
                                {item.filename} ({formatBytes(item.size)})
                              </span>
                            </div>
                            <audio controls src={audioUrl} />
                            <button type="button" onClick={() => handleDownload(audioUrl, item.filename)}>
                              Download
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
        )}
      </section>
    </main>
  );
}

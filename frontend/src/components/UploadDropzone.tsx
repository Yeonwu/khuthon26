'use client';

import { useState, useRef, useCallback } from 'react';
import { Button } from '@/components/ui/button';

interface UploadDropzoneProps {
  onFileAccepted: (file: File) => void;
  onFileRejected?: (error: string) => void;
}

const ALLOWED_EXTENSIONS = ['.mp3', '.wav', '.m4a'];
const MAX_FILE_SIZE = 20 * 1024 * 1024;

function validateFile(file: File): string | null {
  if (file.size === 0) {
    return '빈 파일입니다';
  }

  if (file.size > MAX_FILE_SIZE) {
    return '파일 크기가 20MB를 초과합니다';
  }

  const extension = '.' + file.name.split('.').pop()?.toLowerCase();
  if (!ALLOWED_EXTENSIONS.includes(extension)) {
    return '지원하지 않는 파일 형식입니다';
  }

  return null;
}

export function UploadDropzone({ onFileAccepted, onFileRejected }: UploadDropzoneProps) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    (file: File) => {
      const error = validateFile(file);
      if (error) {
        onFileRejected?.(error);
        return;
      }

      setUploadedFileName(file.name);
      onFileAccepted(file);
    },
    [onFileAccepted, onFileRejected]
  );

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);

      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile]
  );

  const handleClick = useCallback(() => {
    inputRef.current?.click();
  }, []);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLDivElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        handleClick();
      }
    },
    [handleClick]
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
      // Reset input so the same file can be selected again (re-upload replaces previous)
      e.target.value = '';
    },
    [handleFile]
  );

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label="오디오 파일 업로드"
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      className={[
        'flex flex-col items-center justify-center gap-3',
        'rounded-lg border border-dashed p-8',
        'cursor-pointer transition-colors outline-none',
        'focus-visible:ring-2 focus-visible:ring-primary-focus focus-visible:ring-offset-2 focus-visible:ring-offset-canvas',
        isDragOver
          ? 'bg-surface-2 border-primary'
          : 'bg-surface-1 border-hairline',
      ].join(' ')}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".mp3,.wav,.m4a,audio/*"
        onChange={handleInputChange}
        className="hidden"
      />

      {uploadedFileName ? (
        <p className="text-ink font-medium">{uploadedFileName}</p>
      ) : (
        <Button variant="secondary" type="button">
          오디오 파일을 업로드하세요
        </Button>
      )}

      <p className="text-sm text-ink-muted">
        {uploadedFileName
          ? '다시 업로드하려면 클릭하거나 파일을 끌어다 놓으세요'
          : 'MP3, WAV, M4A 형식 (최대 20MB)'}
      </p>
    </div>
  );
}

import { render, screen, fireEvent } from '@testing-library/react';
import { UploadDropzone } from '@/components/UploadDropzone';

describe('UploadDropzone', () => {
  it('calls onFileAccepted when a valid file is dropped', () => {
    const onFileAccepted = jest.fn();
    const onFileRejected = jest.fn();
    render(<UploadDropzone onFileAccepted={onFileAccepted} onFileRejected={onFileRejected} />);

    const dropzone = screen.getByRole('button', { name: /오디오 파일 업로드/i });
    const file = new File(['audio content'], 'test.mp3', { type: 'audio/mpeg' });

    fireEvent.dragOver(dropzone);
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(onFileAccepted).toHaveBeenCalledTimes(1);
    expect(onFileAccepted).toHaveBeenCalledWith(file);
    expect(onFileRejected).not.toHaveBeenCalled();
  });

  it('calls onFileAccepted when a valid file is selected via input', () => {
    const onFileAccepted = jest.fn();
    const onFileRejected = jest.fn();
    render(<UploadDropzone onFileAccepted={onFileAccepted} onFileRejected={onFileRejected} />);

    const input = screen.getByLabelText(/오디오 파일 업로드/i).querySelector('input') as HTMLInputElement;
    const file = new File(['audio content'], 'test.wav', { type: 'audio/wav' });

    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileAccepted).toHaveBeenCalledTimes(1);
    expect(onFileAccepted).toHaveBeenCalledWith(file);
    expect(onFileRejected).not.toHaveBeenCalled();
  });

  it('calls onFileRejected with Korean message when an unsupported file format is dropped', () => {
    const onFileAccepted = jest.fn();
    const onFileRejected = jest.fn();
    render(<UploadDropzone onFileAccepted={onFileAccepted} onFileRejected={onFileRejected} />);

    const dropzone = screen.getByRole('button', { name: /오디오 파일 업로드/i });
    const file = new File(['text content'], 'test.txt', { type: 'text/plain' });

    fireEvent.dragOver(dropzone);
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(onFileAccepted).not.toHaveBeenCalled();
    expect(onFileRejected).toHaveBeenCalledTimes(1);
    expect(onFileRejected).toHaveBeenCalledWith('지원하지 않는 파일 형식입니다');
  });

  it('calls onFileRejected when a file larger than 20MB is dropped', () => {
    const onFileAccepted = jest.fn();
    const onFileRejected = jest.fn();
    render(<UploadDropzone onFileAccepted={onFileAccepted} onFileRejected={onFileRejected} />);

    const dropzone = screen.getByRole('button', { name: /오디오 파일 업로드/i });
    const largeContent = new Uint8Array(21 * 1024 * 1024);
    const file = new File([largeContent], 'large.mp3', { type: 'audio/mpeg' });

    fireEvent.dragOver(dropzone);
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    expect(onFileAccepted).not.toHaveBeenCalled();
    expect(onFileRejected).toHaveBeenCalledTimes(1);
    expect(onFileRejected).toHaveBeenCalledWith('파일 크기가 20MB를 초과합니다');
  });
});

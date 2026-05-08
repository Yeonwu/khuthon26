const AUDIO_FILE_URL = process.env.AUDIO_FILE_URL || '';
const API_URL = process.env.API_URL || '';

export function resolveAudioUrl(fileUrl: string): string {
  if (fileUrl.startsWith('http://') || fileUrl.startsWith('https://')) {
    return fileUrl;
  }
  return AUDIO_FILE_URL + fileUrl;
}

export function getApiUrl(): string {
  return API_URL.trim();
}

export function isMockMode(): boolean {
  const url = getApiUrl();
  return url === '';
}
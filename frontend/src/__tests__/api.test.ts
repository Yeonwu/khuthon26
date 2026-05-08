import { resolveAudioUrl, isMockMode } from '@/lib/api';

describe('resolveAudioUrl', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('prepends AUDIO_FILE_URL to a relative path', () => {
    process.env.AUDIO_FILE_URL = 'https://cdn.example.com';
    // Re-import to pick up the new env value
    const { resolveAudioUrl: resolve } = require('@/lib/api');
    expect(resolve('/audio/file.mp3')).toBe('https://cdn.example.com/audio/file.mp3');
  });

  it('returns an absolute path as-is', () => {
    process.env.AUDIO_FILE_URL = 'https://cdn.example.com';
    const { resolveAudioUrl: resolve } = require('@/lib/api');
    expect(resolve('https://other.example.com/audio/file.mp3')).toBe(
      'https://other.example.com/audio/file.mp3'
    );
  });
});

describe('isMockMode', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    jest.resetModules();
    process.env = { ...originalEnv };
  });

  afterAll(() => {
    process.env = originalEnv;
  });

  it('returns true when API_URL is an empty string', () => {
    process.env.API_URL = '';
    const { isMockMode: check } = require('@/lib/api');
    expect(check()).toBe(true);
  });

  it('returns false when API_URL is a valid URL', () => {
    process.env.API_URL = 'https://api.example.com';
    const { isMockMode: check } = require('@/lib/api');
    expect(check()).toBe(false);
  });
});

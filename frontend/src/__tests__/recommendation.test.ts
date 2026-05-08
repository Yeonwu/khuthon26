import { requestRecommendation } from '@/services/recommendation';
import { ApiError } from '@/lib/errors';

describe('requestRecommendation', () => {
  let fetchMock: jest.Mock;

  beforeEach(() => {
    fetchMock = jest.fn();
    global.fetch = fetchMock;
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('creates FormData with correct fields', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    const file = new File(['audio'], 'test.mp3', { type: 'audio/mpeg' });
    await requestRecommendation({ file, start_second: 10, end_second: 30 });

    const fetchCall = fetchMock.mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const formData = requestInit.body as FormData;

    expect(formData.get('file')).toBeInstanceOf(File);
    expect(formData.get('start_second')).toBe('10');
    expect(formData.get('end_second')).toBe('30');
  });

  it('sends start_second as a string', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    const file = new File(['audio'], 'test.mp3', { type: 'audio/mpeg' });
    await requestRecommendation({ file, start_second: 10, end_second: 30 });

    const fetchCall = fetchMock.mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const formData = requestInit.body as FormData;

    expect(typeof formData.get('start_second')).toBe('string');
  });

  it('sends end_second as a string', async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [],
    } as Response);

    const file = new File(['audio'], 'test.mp3', { type: 'audio/mpeg' });
    await requestRecommendation({ file, start_second: 10, end_second: 30 });

    const fetchCall = fetchMock.mock.calls[0];
    const requestInit = fetchCall[1] as RequestInit;
    const formData = requestInit.body as FormData;

    expect(typeof formData.get('end_second')).toBe('string');
  });

  it('returns parsed response on success', async () => {
    const mockResponse = [
      {
        description: '판소리 기반 느린 장단',
        file_url: '/mock/audio/sample1.mp3',
      },
    ];

    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => mockResponse,
    } as Response);

    const file = new File(['audio'], 'test.mp3', { type: 'audio/mpeg' });
    const response = await requestRecommendation({ file, start_second: 10, end_second: 30 });

    expect(response).toEqual(mockResponse);
  });

  it('throws ApiError on 500 response', async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ error: 'Internal Server Error' }),
    } as Response);

    const file = new File(['audio'], 'test.mp3', { type: 'audio/mpeg' });

    await expect(requestRecommendation({ file, start_second: 10, end_second: 30 })).rejects.toThrow(
      ApiError
    );
  });
});

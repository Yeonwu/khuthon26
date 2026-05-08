import { http, HttpResponse } from 'msw';

export const handlers = [
  http.post('/api/v1/recommendations', async ({ request }) => {
    const formData = await request.formData();
    const startSecond = formData.get('start_second');
    const endSecond = formData.get('end_second');

    const start = startSecond !== null ? Number(startSecond) : 0;
    const end = endSecond !== null ? Number(endSecond) : 0;

    if (start >= end) {
      return HttpResponse.json(
        { error: 'start_second must be less than end_second' },
        { status: 400 }
      );
    }

    const file = formData.get('file');
    if (file instanceof File && file.size > 20 * 1024 * 1024) {
      return HttpResponse.json(
        { error: 'File size exceeds 20MB limit' },
        { status: 413 }
      );
    }

    const delay = Math.floor(Math.random() * 1000) + 1000;
    await new Promise((resolve) => setTimeout(resolve, delay));

    return HttpResponse.json([
      {
        description: '판소리 기반 느린 장단',
        file_url: '/mock/audio/sample1.mp3',
      },
      {
        description: '국악 타악기 중심 리듬',
        file_url: '/mock/audio/sample2.mp3',
      },
    ]);
  }),
];
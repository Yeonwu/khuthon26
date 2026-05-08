import { isMockMode } from '@/lib/api';

export async function initMockServer(): Promise<boolean> {
  if (isMockMode() && typeof window !== 'undefined') {
    const { worker } = await import('@/mocks/browser');
    await worker.start();
    console.info('[MSW] Mock server activated');
  }
  return true;
}

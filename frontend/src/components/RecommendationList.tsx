'use client';

import { RecommendationCard } from './RecommendationCard';
import { Skeleton } from './ui/skeleton';
import { RecommendationItem } from '@/types/recommendation';

interface RecommendationListProps {
  items: RecommendationItem[];
  isLoading: boolean;
  error: Error | null;
}

export function RecommendationList({ items, isLoading, error }: RecommendationListProps) {
  if (isLoading) {
    return (
      <div className="grid grid-cols-3 gap-6">
        <Skeleton className="h-[200px] rounded-lg bg-surface-2" />
        <Skeleton className="h-[200px] rounded-lg bg-surface-2" />
        <Skeleton className="h-[200px] rounded-lg bg-surface-2" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-surface-2 border border-hairline rounded-lg p-6">
        <p className="text-ink">오류: {error.message}</p>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-ink-muted">유사한 샘플을 찾을 수 없습니다</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 gap-6">
      {items.map((item, index) => (
        <RecommendationCard key={index} item={item} />
      ))}
    </div>
  );
}

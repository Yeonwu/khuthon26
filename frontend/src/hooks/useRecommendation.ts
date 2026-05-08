import { useMutation } from '@tanstack/react-query';
import { requestRecommendation } from '@/services/recommendation';
import { RecommendationRequest } from '@/types/recommendation';

export function useRecommendationMutation() {
  return useMutation({
    mutationFn: requestRecommendation,
    retry: false,
  });
}
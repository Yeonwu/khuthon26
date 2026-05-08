import { RecommendationRequest, RecommendationResponse, recommendationResponseSchema } from '@/types/recommendation';
import { ApiError } from '@/lib/errors';
import { getApiUrl } from '@/lib/api';

export async function requestRecommendation(
  params: RecommendationRequest
): Promise<RecommendationResponse> {
  const formData = new FormData();
  formData.append('file', params.file);
  formData.append('start_second', String(params.start_second));
  formData.append('end_second', String(params.end_second));

  const response = await fetch(`${getApiUrl()}/api/v1/recommendations`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    throw new ApiError(response.status);
  }

  const data = await response.json();
  return recommendationResponseSchema.parse(data);
}
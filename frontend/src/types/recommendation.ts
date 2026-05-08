import { z } from 'zod';

export interface RecommendationItem {
  description: string;
  file_url: string;
}

export interface RecommendationRequest {
  file: File;
  start_second: number;
  end_second: number;
}

export type RecommendationResponse = RecommendationItem[];

export const recommendationItemSchema = z.object({
  description: z.string(),
  file_url: z.string(),
});

export const recommendationResponseSchema = z.array(recommendationItemSchema);

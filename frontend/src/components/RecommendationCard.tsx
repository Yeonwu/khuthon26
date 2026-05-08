'use client';

import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { RecommendationItem } from '@/types/recommendation';
import { resolveAudioUrl } from '@/lib/api';

interface RecommendationCardProps {
  item: RecommendationItem;
}

export function RecommendationCard({ item }: RecommendationCardProps) {
  const [audioError, setAudioError] = useState(false);
  const audioUrl = resolveAudioUrl(item.file_url);

  const handleDownload = () => {
    try {
      const a = document.createElement('a');
      a.href = audioUrl;
      a.download = '';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (error) {
      window.open(audioUrl, '_blank');
    }
  };

  return (
    <Card>
      <CardContent className="flex flex-col gap-4">
        <p className="text-body text-ink">{item.description}</p>
        
        <div className="flex flex-col gap-2">
          {audioError ? (
            <p className="text-sm text-red-500">오디오를 불러올 수 없습니다</p>
          ) : (
            <audio 
              controls 
              src={audioUrl} 
              onError={() => setAudioError(true)} 
              className="w-full" 
            />
          )}
        </div>

        <Button variant="secondary" onClick={handleDownload} className="w-full">
          다운로드
        </Button>
      </CardContent>
    </Card>
  );
}

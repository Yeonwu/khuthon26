'use client'

import { useEffect, useState } from 'react'

import { UploadDropzone } from '@/components/UploadDropzone'
import AudioWaveformSelector from '@/components/AudioWaveformSelector'
import { RecommendationList } from '@/components/RecommendationList'
import { Button } from '@/components/ui/button'
import { useRecommendationMutation } from '@/hooks/useRecommendation'
import { initMockServer } from '@/lib/mock-init'
import { isMockMode } from '@/lib/api'
import type { SegmentRange } from '@/types/audio'

export default function HomePage() {
  const [uploadedFile, setUploadedFile] = useState<File | null>(null)
  const [selectedRange, setSelectedRange] = useState<SegmentRange | null>(null)
  const [durationError, setDurationError] = useState<string | null>(null)
  const [showResults, setShowResults] = useState(false)

  const recommendationMutation = useRecommendationMutation()

  useEffect(() => {
    void initMockServer()
  }, [])

  const handleFileAccepted = (file: File) => {
    setUploadedFile(file)
    setSelectedRange(null)
    setDurationError(null)
    setShowResults(false)
  }

  const handleRangeChange = (range: SegmentRange) => {
    setSelectedRange(range)
  }

  const handleDurationError = (message: string) => {
    setDurationError(message)
    setSelectedRange(null)
  }

  const handleSubmit = () => {
    if (!uploadedFile || !selectedRange || durationError) {
      return
    }

    recommendationMutation.mutate({
      file: uploadedFile,
      start_second: selectedRange.start_second,
      end_second: selectedRange.end_second,
    })
    setShowResults(true)
  }

  const isSubmitDisabled =
    !uploadedFile || !selectedRange || !!durationError || recommendationMutation.isPending

  return (
    <main className="min-h-screen bg-canvas">
      <div className="relative mx-auto max-w-5xl p-8">
        {isMockMode() && (
          <span className="absolute right-8 top-8 rounded bg-primary px-2 py-1 text-xs text-primary-foreground">
            MOCK
          </span>
        )}
        <div className="rounded-xl bg-surface-1 p-12">
          <div className="flex flex-col gap-6">
            <h1 className="text-headline text-ink">국악 유사 샘플 추천</h1>
            <UploadDropzone onFileAccepted={handleFileAccepted} />
            {durationError && <p className="text-sm text-red-500">{durationError}</p>}
            {uploadedFile && (
              <AudioWaveformSelector
                file={uploadedFile}
                onRangeChange={handleRangeChange}
                onDurationError={handleDurationError}
              />
            )}
            <Button type="button" onClick={handleSubmit} disabled={isSubmitDisabled}>
              추천 받기
            </Button>
            {showResults && (
              <RecommendationList
                items={recommendationMutation.data ?? []}
                isLoading={recommendationMutation.isPending}
                error={(recommendationMutation.error as Error | null) ?? null}
              />
            )}
          </div>
        </div>
      </div>
    </main>
  )
}

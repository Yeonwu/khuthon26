'use client'

import { useEffect, useRef, useState } from 'react'

import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'

import { Button } from '@/components/ui/button'
import type { SegmentRange } from '@/types/audio'

interface AudioWaveformSelectorInnerProps {
  file: File | null
  onRangeChange: (range: SegmentRange) => void
  onDurationError: (message: string) => void
}

export default function AudioWaveformSelectorInner({
  file,
  onRangeChange,
  onDurationError,
}: AudioWaveformSelectorInnerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const waveSurferRef = useRef<WaveSurfer | null>(null)
  const activeRegionRef = useRef<{
    start: number
    end: number
    remove: () => void
    play: () => void
  } | null>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [selectedRange, setSelectedRange] = useState<SegmentRange | null>(null)

  useEffect(() => {
    if (!file || !containerRef.current) {
      return
    }

    const objectUrl = URL.createObjectURL(file)
    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: '#8a8f98',
      progressColor: '#5e6ad2',
      cursorColor: '#5e6ad2',
      height: 128,
      url: objectUrl,
    })

    waveSurferRef.current = ws

    const regions = ws.registerPlugin(RegionsPlugin.create())
    regions.enableDragSelection({
      color: 'rgba(94, 106, 210, 0.3)',
      minLength: 3,
      maxLength: 30,
    })

    const stopPlayback = () => {
      if (ws.isPlaying()) {
        ws.pause()
        setIsPlaying(false)
      }
    }

    const updateRange = (region: { start: number; end: number }) => {
      const nextRange = {
        start_second: Number(region.start.toFixed(2)),
        end_second: Number(region.end.toFixed(2)),
      }
      setSelectedRange(nextRange)
      onRangeChange(nextRange)
    }

    regions.on('region-created', (region) => {
      if (activeRegionRef.current && activeRegionRef.current !== region) {
        activeRegionRef.current.remove()
      }
      activeRegionRef.current = region
      updateRange(region)
    })

    regions.on('region-updated', (region) => {
      activeRegionRef.current = region
      updateRange(region)
    })

    regions.on('region-update', stopPlayback)

    ws.on('play', () => setIsPlaying(true))
    ws.on('pause', () => setIsPlaying(false))
    ws.on('finish', () => setIsPlaying(false))

    ws.on('ready', () => {
      const duration = ws.getDuration()
      if (duration > 30) {
        onDurationError('오디오 길이가 30초를 초과합니다')
      }
      if (duration < 3) {
        onDurationError('오디오 길이가 3초보다 짧습니다')
      }
    })

    ws.on('error', () => {
      onDurationError('오디오 파일을 불러올 수 없습니다')
    })

    return () => {
      ws.destroy()
      URL.revokeObjectURL(objectUrl)
      waveSurferRef.current = null
      activeRegionRef.current = null
      setIsPlaying(false)
      setSelectedRange(null)
    }
  }, [file, onDurationError, onRangeChange])

  const rangeLabel = selectedRange
    ? `${selectedRange.start_second}s - ${selectedRange.end_second}s`
    : '0s - 0s'

  return (
    <div className="flex flex-col gap-4">
      <div ref={containerRef} className="rounded-lg border border-hairline bg-surface-1 p-3" />
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          onClick={() => waveSurferRef.current?.playPause()}
          disabled={!waveSurferRef.current}
        >
          {isPlaying ? '일시정지' : '재생'}
        </Button>
        <Button
          type="button"
          variant="outline"
          onClick={() => activeRegionRef.current?.play()}
          disabled={!activeRegionRef.current}
        >
          구간 미리듣기
        </Button>
        <span className="text-sm text-ink-muted">{rangeLabel}</span>
      </div>
    </div>
  )
}

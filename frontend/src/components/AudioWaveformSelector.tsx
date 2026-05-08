'use client'

import dynamic from 'next/dynamic'
import type { ComponentProps } from 'react'

const AudioWaveformSelectorInner = dynamic(
  () => import('./AudioWaveformSelectorInner'),
  { ssr: false }
)

export default function AudioWaveformSelector(props: ComponentProps<typeof AudioWaveformSelectorInner>) {
  return <AudioWaveformSelectorInner {...props} />
}

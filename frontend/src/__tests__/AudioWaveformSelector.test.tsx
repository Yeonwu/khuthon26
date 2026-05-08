import { render } from '@testing-library/react';
import AudioWaveformSelectorInner from '@/components/AudioWaveformSelectorInner';

jest.mock('wavesurfer.js', () => ({
  __esModule: true,
  default: {
    create: jest.fn(() => ({
      registerPlugin: jest.fn(() => ({
        enableDragSelection: jest.fn(),
        on: jest.fn(),
      })),
      on: jest.fn(),
      destroy: jest.fn(),
      getDuration: jest.fn(() => 10),
      isPlaying: jest.fn(() => false),
      playPause: jest.fn(),
      pause: jest.fn(),
    })),
  },
}));

jest.mock('wavesurfer.js/dist/plugins/regions.esm.js', () => ({
  __esModule: true,
  default: {
    create: jest.fn(() => ({
      enableDragSelection: jest.fn(),
      on: jest.fn(),
    })),
  },
}));

beforeAll(() => {
  global.URL.createObjectURL = jest.fn(() => 'blob:mock-url');
  global.URL.revokeObjectURL = jest.fn();
});

describe('AudioWaveformSelectorInner', () => {
  const mockOnRangeChange = jest.fn();
  const mockOnDurationError = jest.fn();

  it('renders waveform container', () => {
    const file = new File(['audio'], 'test.mp3', { type: 'audio/mpeg' });
    const { container } = render(
      <AudioWaveformSelectorInner
        file={file}
        onRangeChange={mockOnRangeChange}
        onDurationError={mockOnDurationError}
      />
    );
    expect(container.querySelector('[class*="rounded-lg"]')).toBeInTheDocument();
  });
});

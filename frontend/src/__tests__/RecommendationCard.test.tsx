import { render, screen, fireEvent } from '@testing-library/react';
import { RecommendationCard } from '@/components/RecommendationCard';

describe('RecommendationCard', () => {
  const mockItem = {
    description: '판소리 기반 느린 장단',
    file_url: '/mock/audio/sample1.mp3',
  };

  it('renders description text', () => {
    render(<RecommendationCard item={mockItem} />);
    expect(screen.getByText(mockItem.description)).toBeInTheDocument();
  });

  it('renders audio element with correct src', () => {
    render(<RecommendationCard item={mockItem} />);
    const audio = document.querySelector('audio');
    expect(audio).toBeInTheDocument();
    expect(audio).toHaveAttribute('src', '/mock/audio/sample1.mp3');
  });

  it('renders download button', () => {
    render(<RecommendationCard item={mockItem} />);
    expect(screen.getByRole('button', { name: /다운로드/i })).toBeInTheDocument();
  });
});

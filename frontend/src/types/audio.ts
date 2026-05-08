export interface AudioFileValidation {
  isValid: boolean;
  error?: string;
}

export interface SegmentRange {
  start_second: number;
  end_second: number;
}

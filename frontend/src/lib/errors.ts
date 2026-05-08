export class ApiError extends Error {
  public readonly statusCode: number;

  constructor(statusCode: number) {
    super(getErrorMessage(statusCode));
    this.statusCode = statusCode;
    this.name = 'ApiError';
  }
}

function getErrorMessage(statusCode: number): string {
  switch (statusCode) {
    case 400:
      return '잘못된 요청입니다';
    case 413:
      return '파일 크기가 너무 큽니다';
    case 500:
      return '서버 오류가 발생했습니다';
    default:
      return '알 수 없는 오류가 발생했습니다';
  }
}
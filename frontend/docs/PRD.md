# PRD - Korean Traditional Music Similar Sample Recommendation Frontend

# 1. Overview

사용자가 음악 파일을 업로드하고
waveform 기반으로 특정 구간을 선택하면,
백엔드 추천 서버를 호출하여
유사한 국악 샘플 목록을 추천받고
이를 UI에 카드 형태로 표시하는 웹 애플리케이션을 구현한다.

본 프로젝트는 Frontend only 프로젝트이며,
Next.js 기반으로 구현한다.

---

# 2. Goals

## Primary Goal

- 사용자가 오디오 파일을 업로드할 수 있다.
- Drag & Drop 업로드를 지원한다.
- waveform 기반 구간 선택을 지원한다.
- 선택한 구간의 시작/종료 시간을 recommendation API로 전달한다.
- 추천 결과를 카드 형태로 렌더링한다.
- 각 추천 결과는:
  - description
  - audio player
  - download button
  을 제공해야 한다.

---

# 3. Non Goals

다음은 구현하지 않는다.

- 사용자 인증
- 로그인
- DB 저장
- 업로드 히스토리
- 자체 오디오 분석
- 브라우저 내 오디오 trimming/export
- ffmpeg.wasm 기반 처리
- SSR 기반 추천 처리

---

# 4. Tech Stack Requirements

## Framework

- Next.js
- App Router 사용
- TypeScript 필수

## Runtime

- Node.js 24 compatible version 사용

## UI

- DESIGN.md 디자인 명세를 반드시 준수
- shadcn/ui 사용
- TailwindCSS 사용

## State / Data

- TanStack Query (React Query) 사용

## Audio UI

권장 라이브러리:

```txt
wavesurfer.js
```

## Testing

- Jest 사용
- React Testing Library 사용
- cmux browser skills 기반 UI 검증 수행

---

# 5. Environment Variables

다음 환경변수를 사용한다.

```env
API_URL=
AUDIO_FILE_URL=
```

## API_URL

추천 API 서버 base url

예시:

```env
API_URL=https://api.example.com
```

## AUDIO_FILE_URL

정적 오디오 파일 base url

필요 시 recommendation 응답의 file_url과 조합하여 사용 가능

---

# 6. Functional Requirements

# 6.1 Audio Upload

사용자는 다음 방식으로 오디오 파일을 업로드할 수 있어야 한다.

- 클릭 업로드
- Drag & Drop 업로드

## Supported Formats

다음 포맷을 지원해야 한다.

- mp3
- wav
- m4a

## File Size

권장 제한:

- 최대 20MB

제한 초과 시 사용자에게 에러를 표시한다.

---

# 6.2 Waveform Rendering

업로드 완료 후
waveform UI를 렌더링해야 한다.

사용자는 waveform 기반으로
추천에 사용할 오디오 구간을 선택할 수 있어야 한다.

## Required Features

- waveform 표시
- audio playback
- drag 기반 range selection
- selected range highlight
- selected range preview playback

---

# 6.3 Segment Selection

사용자는 추천에 사용할 오디오 구간을 선택할 수 있어야 한다.

선택된 값:

```txt
start_second
end_second
```

## Validation

다음을 검증한다.

- start_second < end_second
- 최소 길이 존재
- 전체 duration 초과 금지

## Recommended Limits

- 최소 3초
- 최대 30초

---

# 6.4 Recommendation Request

선택된 구간 정보를 포함하여
recommendation API를 호출한다.

Frontend는 원본 오디오 파일 전체를 업로드한다.

브라우저에서 오디오를 잘라서 업로드하지 않는다.

---

## Request

```http
POST /api/v1/recommendations
Content-Type: multipart/form-data
```

## Form Data

```txt
file=<audio_file>
start_second=<number>
end_second=<number>
```

## Example

```ts
const formData = new FormData();

formData.append("file", file);
formData.append("start_second", "12.5");
formData.append("end_second", "24.8");
```

field name은 반드시 아래를 사용한다.

```txt
file
start_second
end_second
```

---

# 6.5 Recommendation Response

응답 형태:

```json
[
  {
    "description": "판소리 느낌의 느린 장단",
    "file_url": "https://example.com/audio/sample.mp3"
  }
]
```

## Notes

- 배열 길이는 고정되지 않는다.
- description은 한글 문자열이다.
- file_url은 정적 오디오 파일 URL이다.

---

# 6.6 Recommendation Result UI

추천 결과는 카드 UI로 렌더링한다.

각 카드에는 다음 요소가 포함되어야 한다.

- description 텍스트
- audio player
- download button

---

# 6.7 Download Button

download button 클릭 시:

- file_url 다운로드
또는
- 새 탭 열기

를 수행한다.

---

# 7. UX Requirements

# 7.1 Loading State

추천 요청 중:

- loading indicator 표시
- 중복 업로드 방지
- submit button disabled 처리

---

# 7.2 Error State

status code 기반 에러 처리 수행

예시:

- 400
- 413
- 500

사용자 친화적 메시지 표시

---

# 7.3 Empty State

추천 결과가 비어있는 경우:

- empty state 표시

---

# 8. Accessibility Requirements

다음을 준수한다.

- keyboard accessible
- aria-label 제공
- drag/drop 영역 focus 가능
- waveform control accessible
- screen reader friendly

---

# 9. Directory Expectations

권장 디렉토리 구조:

```txt
src/
  app/
  components/
  features/
    recommendation/
  hooks/
  lib/
  services/
  types/
```

---

# 10. API Layer Requirements

API 호출 로직은 반드시 분리한다.

예시:

```txt
services/recommendation.ts
```

다음 금지:

- UI 컴포넌트 내부 직접 fetch 구현

---

# 11. State Management Requirements

서버 상태 관리는 React Query 사용.

필수 사항:

- mutation 사용
- loading/error state 관리
- retry 정책 명시

---

# 12. Component Requirements

최소 다음 컴포넌트를 분리한다.

# UploadDropzone

책임:

- drag & drop
- file validation
- upload trigger

---

# AudioWaveformSelector

책임:

- waveform 렌더링
- audio playback
- range selection
- selected range state 관리
- preview playback

---

# RecommendationList

책임:

- recommendation 목록 렌더링

---

# RecommendationCard

책임:

- description 렌더링
- audio player
- download button

---

# 13. Validation Requirements

다음을 검증해야 한다.

- 지원하지 않는 파일 형식
- 파일 크기 초과
- 빈 파일
- invalid segment range
- API 실패 응답

---

# 14. Testing Requirements

# 14.1 Unit Tests

Jest + React Testing Library 기반 테스트 작성.

최소 테스트:

## UploadDropzone

- drag/drop 동작
- 파일 선택
- validation 동작

## AudioWaveformSelector

- waveform 렌더링
- range selection
- selected range 변경

## Recommendation API

- multipart/form-data 요청 생성
- start_second 포함 여부
- end_second 포함 여부
- 성공 응답 처리
- 실패 응답 처리

## RecommendationCard

- description 렌더링
- audio 표시
- download link 연결

---

# 14.2 Browser Validation

cmux browser skills를 사용하여 UI 검증 수행.

검증 항목:

- drag & drop 동작
- waveform 표시
- 구간 선택 가능
- 선택 구간 재생 가능
- 업로드 후 결과 표시
- loading state 표시
- error state 표시
- download button 동작

---

# 15. Acceptance Criteria

다음 조건 충족 시 완료로 간주한다.

- 사용자가 mp3/wav/m4a 파일 업로드 가능
- drag & drop 동작
- waveform 렌더링 가능
- drag 기반 구간 선택 가능
- 선택 구간 재생 가능
- multipart/form-data 사용
- field name이 정확히 사용됨
- start_second 전송
- end_second 전송
- recommendation API 정상 호출
- 응답 결과 카드 렌더링
- audio 재생 가능
- download button 동작
- loading/error state 존재
- Jest 테스트 작성
- cmux browser validation 수행
- DESIGN.md 준수
- TypeScript 에러 없음
- ESLint 에러 없음
- Next.js production build 성공

---

# 16. Implementation Constraints

다음을 반드시 준수한다.

- any 타입 남용 금지
- API 호출 로직 분리
- 하드코딩 금지
- DESIGN.md 무시 금지
- 불필요한 전역 상태 사용 금지
- ffmpeg.wasm 사용 금지
- 브라우저 내 오디오 export 구현 금지

---

# 17. Expected Deliverables

최종 결과물:

- 동작 가능한 Next.js frontend
- waveform 기반 구간 선택 UI
- React Query 적용
- shadcn/ui 적용
- drag & drop upload UI
- recommendation result card UI
- 테스트 코드
- production build 가능 상태


# 18. Local Development Fallback Requirements

로컬 개발 및 테스트 환경에서
`API_URL` 환경변수가 존재하지 않는 경우,
Frontend는 mock server를 사용하여 동작해야 한다.

목적:

- backend 미구현 상태에서도 frontend 개발 가능
- UI/UX 독립 검증 가능
- 테스트 환경 안정화

---

# Mock Server Requirements

## Activation Condition

다음 조건에서 mock server 활성화:

```txt
API_URL is undefined
```

또는

```txt
API_URL is empty
```

---

## Mock Response

recommendation API mock 응답은 실제 응답 구조와 동일해야 한다.

예시:

```json
[
  {
    "description": "판소리 기반 느린 장단",
    "file_url": "/mock/audio/sample1.mp3"
  },
  {
    "description": "국악 타악기 중심 리듬",
    "file_url": "/mock/audio/sample2.mp3"
  }
]
```

---

# Mocking Strategy

권장 방식:

```txt
MSW (Mock Service Worker)
```

다음 목적을 만족해야 한다.

- browser 환경 mocking
- test 환경 mocking
- Jest 연동 가능
- 실제 API contract 유지

---

# Mock Audio Assets

mock server 사용 시
테스트용 오디오 파일을 제공해야 한다.

권장 위치:

```txt
public/mock/audio/
```

---

# Development Requirements

개발 서버 실행 시:

- API_URL 존재:
  - 실제 API 사용

- API_URL 미존재:
  - mock server 자동 사용

Frontend 코드에서
mock 여부를 쉽게 확인할 수 있어야 한다.

예시:

```txt
console info
development badge
```

---

# Testing Requirements

Jest 및 browser validation 환경에서
mock server를 기본 활성화한다.

다음 검증 가능해야 한다.

- recommendation 성공 응답
- empty response
- error response
- loading state

---

# Acceptance Criteria 추가

다음 조건 충족 필요:

- API_URL 없을 경우 mock server 자동 활성화
- mock response가 실제 API 구조와 동일
- mock audio playback 가능
- Jest 환경에서 mock 사용 가능
- browser validation 환경에서 mock 사용 가능
```

# 디각 - 오디오 레퍼런스 기반 국악 샘플 탐색 도구

![디각 서비스 스크린샷](assets/screenshot.png)

Khuthon 2026 우수상 수상작

## 소개 페이지

발표용으로 제작한 인터랙티브 소개 페이지를 함께 제공합니다.

- [디각 소개 페이지 열기](assets/presentation.html)
- 마지막 페이지에서 원본 커버 음원과 국악 샘플 적용 결과를 15초 클립으로 비교 청음할 수 있습니다.
- 키보드 `←` / `→` 또는 `Space`로 슬라이드를 넘길 수 있습니다.

## 프로젝트 소개

디각은 작곡가가 가지고 있는 오디오 샘플을 기준으로, 소리의 질감과 음악적 특성이 유사한 국악 샘플을 찾아주는 서비스입니다.

일반적인 샘플 검색 서비스는 키워드와 메타데이터 중심으로 동작합니다. 이 방식은 빠르게 검색할 수 있다는 장점이 있지만, 작곡가가 원하는 느낌을 텍스트로 정확히 설명해야 한다는 한계가 있습니다. 특히 국악 샘플은 소리북, 진도장구, 징바라처럼 전통악기와 장단에 대한 배경지식이 있어야 검색어를 고를 수 있어 진입장벽이 더 큽니다.

디각은 사용자가 원하는 분위기의 기존 악기 샘플을 업로드하면, 미리 벡터화해 둔 국악 샘플 데이터베이스와 비교해 유사한 국악 샘플을 추천합니다. 사용자는 국악 용어를 몰라도 익숙한 소리로 원하는 국악 샘플을 탐색할 수 있습니다.

## 왜 필요한가

작곡 과정에는 원하는 소리를 찾아 곡에 맞게 조합하는 샘플 디깅 과정이 있습니다. 기존 샘플 플랫폼은 검색어와 태그가 잘 맞을 때는 효율적이지만, 작곡가가 머릿속에 떠올린 질감, 분위기, groove를 텍스트로 정확히 표현해야 한다는 부담이 있습니다.

국악 샘플에서는 이 문제가 더 커집니다. 전통악기의 이름, 분류, 지역, 시대를 알아야 검색을 시작할 수 있기 때문입니다. 디각은 텍스트 검색 대신 레퍼런스 오디오 자체를 입력으로 사용해, 국악 배경지식이 부족한 창작자도 원하는 사운드에 가까운 국악 샘플을 찾을 수 있게 합니다.

## 어떻게 해결했나

1. 국립국악원 디지털 음원 등 국악 샘플을 전처리합니다.
2. 각 샘플을 MERT 모델로 임베딩하고 PostgreSQL pgvector에 저장합니다.
3. 사용자가 업로드한 오디오도 같은 방식으로 임베딩합니다.
4. 입력 샘플과 국악 샘플 임베딩 간 유사도를 계산합니다.
5. 가장 가까운 국악 샘플을 추천하고, 결과 오디오를 생성합니다.

## 데모 음원

소개 페이지 마지막 슬라이드에서 다음 3개 데모를 비교 청음할 수 있습니다.

| 데모 | 비교 내용 | 연결된 15초 클립 |
| --- | --- | --- |
| Just the Two of Us | cowbell과 유사한 소리북 계열 사운드 매칭 | `assets/audio-preview/just-the-two-of-us-raw-15s.wav`, `assets/audio-preview/just-the-two-of-us-gugak-15s.wav` |
| Updown Funk | 퍼커션과 유사한 꽹과리 계열 사운드 추가 | `assets/audio-preview/updown-funk-raw-15s.wav`, `assets/audio-preview/updown-funk-gugak-15s.wav` |
| Happy | handclap 계열 사운드를 국악 타악 질감으로 확장 | `assets/audio-preview/happy-raw-15s.wav`, `assets/audio-preview/happy-gugak-15s.wav` |

## 저작권 고려

데이터베이스에 저장한 국악 샘플은 국립국악원 디지털 음원 중 공공누리 제1유형이 적용된 음원을 기준으로 사용했습니다. 출처를 표기하면 자유롭게 이용할 수 있어, 작곡가가 2차 창작에 활용할 수 있는 방향을 고려했습니다.

커버 음원 데모는 프로젝트 설명과 비교 청음을 위해 짧은 프리뷰 클립으로만 제공합니다.

## 팀

- 팀명: 쿠카프
- 팀원: 오연우, 이성빈, 정대균

## 기술 스택

- Frontend: React, Vite
- Backend: FastAPI
- Audio Embedding: MERT(`m-a-p/MERT-v1-330M`)
- Database: PostgreSQL, pgvector
- Audio Processing: PyTorch, torchaudio, librosa, soundfile, ffmpeg

## 레포 구조

```text
.
├── assets/                 # README 이미지, 소개 페이지, 데모 음원
│   └── audio-preview/      # README/소개 페이지용 15초 청음 클립
├── core/                   # 백엔드 API, 오디오 검색, 임베딩, DB 스크립트
├── frontend/               # React/Vite 프론트엔드
├── design_guide/           # 디자인 토큰과 스타일 가이드
└── scripts/                # 데이터 수집 보조 스크립트
```

## 실행 방법

### 1. 백엔드 환경 구성

```bash
cd core
conda env create -f environment.yml
conda activate khuthon26
```

이미 환경이 있다면 다음 명령으로 동기화합니다.

```bash
cd core
conda env update -n khuthon26 -f environment.yml --prune
```

### 2. 환경 변수 설정

`core/.env` 파일에 PostgreSQL 접속 정보를 설정합니다.

```env
DB_HOST=db_host
DB_PORT=db_port
DB_USER=db_user
DB_PW=password
DB_NAME=db_name
```

### 3. 데이터베이스 준비

```bash
cd core
conda run -n khuthon26 python scripts/create_tables.py
conda run -n khuthon26 python scripts/load_audio_metadata.py
conda run -n khuthon26 python scripts/embed_audio_segments.py
```

### 4. API 서버 실행

```bash
cd core
conda run -n khuthon26 uvicorn api.server:app --host 127.0.0.1 --port 8001
```

### 5. 프론트엔드 실행

```bash
cd frontend
npm install
VITE_API_URL=http://127.0.0.1:8001 npm run dev
```

기본 개발 서버 주소는 `http://localhost:5174`입니다.

## API

### 오디오 업로드

```http
POST /api/v1/upload
```

`multipart/form-data`로 오디오 파일을 업로드하면 백그라운드에서 유사 샘플 검색과 결과 렌더링을 수행합니다.

### 업로드 목록 조회

```http
GET /api/v1/uploads
```

업로드된 작업의 처리 상태와 생성된 결과 오디오를 반환합니다.

### 추천 결과 직접 조회

```http
POST /api/v1/recommendations
```

`file`과 `top_k`를 전달하면 유사한 원본 샘플 경로를 반환합니다.

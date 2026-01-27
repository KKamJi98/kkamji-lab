# Container Image Mirror Tool

crane 기반 컨테이너 이미지 ECR 미러링 도구

## 개요

외부 레지스트리(docker.io, quay.io, ghcr.io, public.ecr.aws 등)의 이미지를 Private ECR로 미러링합니다.

**특징:**

- **crane 기반**: docker보다 가볍고 빠른 레지스트리 전용 도구
- **플랫폼 선택**: `linux/amd64`, `linux/arm64`만 선택적 복사 (s390x, ppc64le 제외)
- **병렬 처리**: `--parallel N` 옵션으로 빠른 미러링
- **외부 설정**: 이미지 목록/설정을 YAML/env 파일로 분리
- **digest 보존**: 원본과 동일한 digest 유지

## 사전 요구사항

```bash
# 필수 도구 설치
brew install crane yq awscli

# AWS CLI 설정
aws configure
```

## 파일 구조

```
mirror-container-images/
├── mirror-images.sh       # 메인 스크립트
├── images.yaml            # 이미지 목록 (편집 필요)
├── config.env.example     # 설정 예시
├── config.env             # 실제 설정 (gitignore)
├── .gitignore
├── README.md
└── results/               # 실행 결과 (gitignore)
    ├── images_YYYYMMDD_HHMMSS.csv
    ├── images_YYYYMMDD_HHMMSS.md
    └── mirror_YYYYMMDD_HHMMSS.log
```

## 설정

### 1. ECR 설정 (`config.env`)

```bash
cp config.env.example config.env
# config.env 파일 편집
```

```bash
# config.env
ECR_ACCOUNT="123456789012"    # 실제 AWS 계정 ID
ECR_REGION="ap-northeast-2"
PLATFORMS="linux/amd64,linux/arm64"
MAX_RETRIES=5
DELAY_BETWEEN=5
PARALLEL_JOBS=4
```

### 2. 이미지 목록 (`images.yaml`)

```yaml
images:
  - chart: grafana
    source: docker.io/grafana/grafana:11.4.0
    dest: grafana/grafana:11.4.0

  - chart: nginx
    source: docker.io/library/nginx:1.25-alpine
    dest: nginx:1.25-alpine
```

## 사용법

### 기본 실행

```bash
# 전체 실행 (로그인 → 미러링 → 검증)
./mirror-images.sh

# Dry-run (실행 전 확인)
./mirror-images.sh --dry-run
```

### 병렬 처리

```bash
# 4개 이미지 병렬 미러링
./mirror-images.sh --parallel 4
```

### 검증만 실행

```bash
# 미러링 없이 digest 비교만
./mirror-images.sh --verify
```

### 전체 옵션

| 옵션            | 설명                                      |
| --------------- | ----------------------------------------- |
| `--dry-run`     | 실제 실행 없이 명령어만 출력              |
| `--skip-login`  | ECR 로그인 단계 건너뛰기                  |
| `--verify`      | 미러링 없이 검증만 실행                   |
| `--parallel N`  | N개 이미지 병렬 처리                      |
| `--force`       | 이미 존재하는 이미지도 덮어쓰기           |
| `--config FILE` | 설정 파일 지정 (기본: config.env)         |
| `--images FILE` | 이미지 목록 파일 지정 (기본: images.yaml) |
| `-h, --help`    | 도움말 출력                               |

## 실행 흐름

```
1. 설정/이미지 목록 로드
   └─ config.env, images.yaml

2. ECR 로그인
   └─ crane auth login (aws ecr get-login-password)

3. 이미지 미러링
   ├─ 리포지토리 자동 생성
   ├─ 멀티플랫폼: crane index filter (지정 플랫폼만 복사)
   ├─ 단일플랫폼: crane copy (그대로 복사)
   ├─ Rate limit 대응: 재시도 + exponential backoff
   └─ 이미 존재하는 이미지는 스킵 (--force로 덮어쓰기)

4. 검증
   └─ 원본과 ECR의 플랫폼별 digest 비교

5. 결과 파일 생성
   ├─ results/images_YYYYMMDD_HHMMSS.csv
   ├─ results/images_YYYYMMDD_HHMMSS.md
   └─ results/mirror_YYYYMMDD_HHMMSS.log
```

## 검증 출력 예시

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[INFO] [1/3] grafana
  Source: docker.io/grafana/grafana:11.4.0
  ECR:    123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/grafana/grafana:11.4.0

  PLATFORM     SOURCE               ECR                  MATCH
  ──────────────────────────────────────────────────────────
  linux/amd64  sha256:abc123...     sha256:abc123...     ✓
  linux/arm64  sha256:def456...     sha256:def456...     ✓
[INFO]   결과: 모든 플랫폼 digest 일치 ✓
```

## docker buildx vs crane 비교

| 항목        | docker buildx         | crane                     |
| ----------- | --------------------- | ------------------------- |
| 설치 크기   | ~500MB+ (Docker 전체) | ~15MB                     |
| 속도        | 보통                  | 빠름                      |
| 로컬 pull   | 필요 없음             | 필요 없음                 |
| 멀티 플랫폼 | `imagetools create`   | `index filter --platform` |
| 의존성      | Docker daemon         | 없음                      |

## Rate Limit 대응

ECR API rate limit 발생 시:

- **자동 재시도**: 최대 5회 (exponential backoff: 10s → 20s → 40s → 60s)
- **이미지 간 대기**: 기본 5초

설정 조정:

```bash
# config.env
MAX_RETRIES=7
INITIAL_DELAY=15
DELAY_BETWEEN=10
```

## 트러블슈팅

### crane 설치 확인

```bash
crane version
# 0.20.0 이상 권장
```

### ECR 로그인 수동 실행

```bash
aws ecr get-login-password --region ap-northeast-2 | \
  crane auth login 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com -u AWS --password-stdin
```

### 특정 이미지 수동 복사

```bash
# 멀티플랫폼 이미지 (amd64/arm64만 선택)
crane index filter docker.io/grafana/grafana:11.4.0 \
  --platform=linux/amd64 --platform=linux/arm64 \
  -t 123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/grafana/grafana:11.4.0

# 단일플랫폼 이미지
crane copy docker.io/library/nginx:1.25-alpine \
  123456789012.dkr.ecr.ap-northeast-2.amazonaws.com/nginx:1.25-alpine
```

### digest 불일치

- 원본 이미지가 업데이트되었을 수 있음
- `--force` 옵션으로 재미러링 필요

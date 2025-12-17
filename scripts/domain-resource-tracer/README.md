# Domain Resource Tracer (drt)

AWS 도메인 기반 리소스 추적 도구

## 설치

### 전역 설치 (권장)

```bash
# 현재 디렉토리에서 전역 도구로 설치
uv tool install .

# 이후 어디서든 사용 가능
drt trace "api.*"
```

### 업데이트 / 재설치

```bash
# 코드 변경 후 재설치 (빌드 캐시 사용)
uv tool install . --force

# 빌드 캐시 무시하고 완전히 새로 빌드
uv sync && uv tool install . --force --reinstall
```

> **Note**: `--force`만 사용하면 빌드 캐시가 남아있어 코드 변경이 반영되지 않을 수 있습니다.
> 코드 수정 후에는 `uv sync`로 로컬 빌드를 갱신한 뒤 `--reinstall` 옵션을 함께 사용하세요.

### 제거

```bash
uv tool uninstall domain-resource-tracer
```

### 로컬 개발용

```bash
uv sync
uv run drt trace "api.*"
```

## 사용법

```bash
# 도메인 패턴으로 리소스 체인 추적
drt trace "api\.example\.com"
drt trace ".*\.example\.com"
drt trace "prod-.*"

# JSON 출력
drt trace "api.*" --json

# 상세 출력
drt trace "api.*" --verbose

# Route53 Hosted Zone 목록
drt list-zones

# 특정 Zone의 레코드 조회
drt list-records Z1234567890 --pattern "api.*"
```

## 추적 흐름

```text
Domain → Route53 → CloudFront/ALB/NLB → Origin/Target Group → EC2/S3
```

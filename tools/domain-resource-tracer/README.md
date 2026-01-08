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

### 정방향 추적 (Domain → Resource)

```bash
# 도메인 패턴으로 리소스 체인 추적
drt trace "api\.example\.com"
drt trace ".*\.example\.com"
drt trace "prod-.*"

# JSON 출력
drt trace "api.*" --json

# 상세 출력
drt trace "api.*" --verbose
```

### 역방향 추적 (Resource → Domain)

```bash
# LB DNS로 역추적
drt reverse-trace "k8s-xxx.elb.ap-northeast-2.amazonaws.com"

# EC2 Instance ID로 역추적
drt reverse-trace "i-1234567890abcdef0"

# EC2 Private IP로 역추적
drt reverse-trace "10.0.1.100"

# EC2 Private DNS로 역추적 (EKS 노드명)
drt reverse-trace "ip-10-0-1-100.ap-northeast-2.compute.internal"

# EC2 Name 태그로 역추적
drt reverse-trace "my-web-server"

# 옵션
drt reverse-trace "..." --json      # JSON 출력
drt reverse-trace "..." --verbose   # 상세 출력
drt reverse-trace "..." --region ap-northeast-2  # 리전 지정
```

### 기타 명령어

```bash
# Route53 Hosted Zone 목록
drt list-zones

# 특정 Zone의 레코드 조회
drt list-records Z1234567890 --pattern "api.*"
```

## 추적 흐름

### 정방향 추적

```text
Domain Pattern (정규표현식)
    ↓
Route53 검색
    ↓
CloudFront / ALB / NLB
    ↓
Origin / Target Group
    ↓
EC2 / S3
```

### 역방향 추적

```text
EC2 (Instance ID / IP / Private DNS / Name)
    ↓
Target Group (ENI IP로 매칭, Pod IP 포함)
    ↓
Load Balancer
    ↓
Route53 레코드 + CloudFront Distribution
```

## 지원하는 입력 형식 (reverse-trace)

| 형식 | 예시 | 설명 |
|------|-----|------|
| LB DNS | `*.elb.amazonaws.com` | ALB/NLB DNS |
| EC2 Instance ID | `i-1234567890abcdef0` | EC2 인스턴스 ID |
| EC2 IP | `10.0.1.100` | Private/Public IP |
| EC2 Private DNS | `ip-10-0-1-100.*.compute.internal` | EKS 노드명 |
| EC2 Name | `my-web-server` | Name 태그 (와일드카드 지원) |

## EKS 환경 지원

- **ENI Secondary IP 매칭**: VPC CNI가 Pod에 할당한 IP도 추적
- **Private DNS 지원**: `kubectl get nodes` 출력의 노드명으로 직접 검색
- **IP Target Type**: Target Group이 IP 타입인 경우에도 EC2 → Pod 연결 추적

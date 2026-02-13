# EKS Token Cache

EKS 토큰 캐싱을 통해 kubectl 명령어 실행 속도를 개선하는 도구입니다.

## 배경

`kubectl`은 EKS 클러스터 접근 시 매번 `aws eks get-token`을 호출합니다. 이 과정에서:
- AWS STS API 호출로 인한 지연 (0.5~2초)
- 반복 실행 시 불필요한 API 호출

토큰 유효시간은 15분이므로, 캐싱을 통해 성능을 크게 개선할 수 있습니다.

## 구성 파일

| 파일 | 설명 |
|------|------|
| `eks-token-cache.sh` | 토큰 캐싱 스크립트 (kubeconfig exec에서 호출) |
| `eks-token-cache-manager.sh` | 캐시 적용 관리 도구 |

## 설치

```bash
# 1. ~/.kube에 symlink 생성
ln -s $(pwd)/eks-token-cache.sh ~/.kube/eks-token-cache.sh
ln -s $(pwd)/eks-token-cache-manager.sh ~/.kube/eks-token-cache-manager.sh

# 2. 실행 권한 확인
chmod +x ~/.kube/eks-token-cache*.sh
```

### 의존성

- `jq`: JSON 파싱 (토큰 캐시 스크립트)
- `yq`: YAML 편집 (manager 스크립트의 apply/revert 기능, dry-run 제외)
- `aws-cli`: EKS 토큰 발급
- `kubectl`: kubeconfig 읽기/수정

```bash
# macOS
brew install jq awscli yq
```

## 사용법

### 캐시 관리자

```bash
# 상태 확인: 모든 EKS context의 캐시 적용 여부 확인
~/.kube/eks-token-cache-manager.sh status

# 선택 적용: 대화형으로 미적용 context 선택
~/.kube/eks-token-cache-manager.sh apply

# 일괄 적용: 모든 미적용 context에 적용
~/.kube/eks-token-cache-manager.sh apply-all

# 사전 점검: 실제 변경 없이 적용 예정 내용 확인
~/.kube/eks-token-cache-manager.sh apply --dry-run
~/.kube/eks-token-cache-manager.sh --dry-run apply-all

# 해제: 원본 aws eks get-token으로 복원
~/.kube/eks-token-cache-manager.sh revert
```

### 디버그 모드

```bash
# 토큰 캐시 동작 확인
EKS_TOKEN_DEBUG=1 kubectl get nodes

# 출력 예시:
# [DEBUG] Token expires in 796s (cluster: dev-cluster)
# [DEBUG] Using cached token
```

### 수동 적용 (개별 context)

kubeconfig의 user exec 설정을 직접 수정:

```yaml
users:
- name: arn:aws:eks:ap-northeast-2:123456789:cluster/my-cluster
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: /Users/ethan/.kube/eks-token-cache.sh
      args:
        - my-cluster        # cluster name
        - ap-northeast-2    # region
        - my-profile        # AWS profile (선택)
```

## 캐시 동작 원리

토큰 내부 `expirationTimestamp` 기반으로 캐시 유효성을 판단합니다 (이전 v1에서는 파일 mtime 기반이었으나, 현재는 실제 토큰 만료 시간 기준으로 정확한 판단).

```
캐시 유효성 = 토큰.expirationTimestamp > (현재시간 + 60초)
```

### AWS 세션 변경 자동 감지 (credential fingerprint)

AWS 세션이 변경되면(re-login 등) 이전 세션의 토큰이 캐시에 남아 Unauthorized 에러가 발생할 수 있습니다. 이를 방지하기 위해 credential fingerprint 메커니즘을 사용합니다:

1. **토큰 저장 시**: AWS 자격증명 파일(`~/.aws/cli/cache/session.db`, `~/.aws/login/cache/*.json`)의 mtime을 조합한 fingerprint를 `.meta` 사이드카 파일에 저장
2. **캐시 읽기 시**: 현재 fingerprint와 저장된 fingerprint를 비교하여 불일치 시 캐시 무효화
3. **하위 호환성**: `.meta` 파일이 없는 기존 캐시도 정상 동작 (fingerprint 검증 스킵)

성능 영향: 캐시 hit 경로에 `stat` 호출 2~3회 추가 (~1ms), 무시 가능 수준.

### 캐시 파일 위치

```
~/.kube/cache/eks-tokens/
├── dev-cluster_ap-northeast-2_acme.json        # 토큰 (cluster_region_profile)
├── dev-cluster_ap-northeast-2_acme.json.meta   # credential fingerprint
├── dev-cluster_ap-northeast-2_acme.json.error  # 에러 네거티브 캐시
├── prod-cluster_ap-northeast-2_acme.json
└── my-cluster_ap-northeast-2.json              # profile 없는 경우
```

### 원본 exec 백업 (자동)

`apply`는 기존 `user.exec`를 백업하고, `revert`는 백업을 기준으로 정확히 복원합니다.

```
~/.kube/cache/eks-token-cache/backups/
└── <user>.json
```

> 백업에는 `kubeconfig` 파일 경로와 `user.exec` 전체가 저장됩니다.
> 백업이 없으면 사용자 확인 후 현재 설정을 기준으로 복원하며, 추가 옵션은 복원되지 않을 수 있습니다.

## 설정

### 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `EKS_TOKEN_DEBUG` | 디버그 로그 출력 | `0` (비활성) |
| `EKS_TOKEN_ERROR_TTL` | 에러 네거티브 캐시 유효 시간 (초) | `30` |
| `EKS_TOKEN_CACHE_SCRIPT` | 캐시 스크립트 경로 (manager용) | `~/.kube/eks-token-cache.sh` |
| `EKS_TOKEN_CACHE_DIR` | 토큰 캐시 디렉토리 (aws hook용) | `~/.kube/cache/eks-tokens` |

### 스크립트 상수

| 상수 | 설명 | 기본값 |
|------|------|--------|
| `SAFETY_MARGIN` | 만료 전 갱신 여유 시간 | `60`초 |

### 에러 중복 억제 (네거티브 캐시)

kubectl은 API 디스커버리 과정에서 exec credential plugin을 5~6회 반복 호출합니다. AWS 세션 만료 시 매 호출마다 동일한 에러가 출력되는 문제를 방지하기 위해 에러 네거티브 캐시를 사용합니다.

| 시나리오 | 동작 |
|----------|------|
| 첫 실패 | AWS CLI stderr 캡처 → 에러 분류 → `.error` 캐시 저장 → 상세 에러 출력 |
| 30초 내 재시도 | 에러 캐시 hit → 간략 한줄 출력 → exit 1 (AWS CLI 호출 없음) |
| `aws sso login` 후 재시도 | credential fingerprint 변경 감지 → 에러 캐시 삭제 → 정상 재시도 |
| TTL 만료 후 재시도 | 에러 캐시 무효 → AWS CLI 재시도 |

에러 유형별 자동 분류:
- `session_expired`: 세션 만료 → `aws sso login --profile <profile>` 안내
- `no_credentials`: 자격증명 없음 → `aws sso login` 또는 `aws configure` 안내
- `access_denied`: 권한 부족 → IAM 권한 확인 안내
- `cluster_not_found`: 클러스터 미존재 → 클러스터명/리전 확인 안내
- `network_error`: 네트워크 오류 → 연결 확인 안내

## 문제 해결

### Unauthorized 에러

```bash
# 1. 캐시 파일 확인
ls -la ~/.kube/cache/eks-tokens/

# 2. 토큰 만료 시간 확인
jq -r '.status.expirationTimestamp' ~/.kube/cache/eks-tokens/*.json

# 3. 디버그 모드로 확인
EKS_TOKEN_DEBUG=1 kubectl get nodes

# 4. 캐시 삭제 후 재시도
rm ~/.kube/cache/eks-tokens/my-cluster_*.json
kubectl get nodes
```

### AWS 세션 변경 후 Unauthorized

캐시는 credential fingerprint로 세션 변경을 자동 감지하지만, shell hook도 함께 사용하면 더 확실합니다.

**자동 감지 (v2)**: `eks-token-cache.sh`가 `.meta` 파일의 fingerprint를 비교하여 세션 변경 시 자동으로 캐시를 무효화합니다.

**shell hook (보조)**: `aws login` 또는 `aws sso login` 성공 시 캐시를 즉시 삭제합니다.

```bash
# ~/.zsh_functions 또는 ~/.bashrc에 추가

# aws wrapper - login 후 EKS 토큰 캐시 자동 삭제
aws() {
  local EKS_TOKEN_CACHE_DIR="${HOME}/.kube/cache/eks-tokens"

  command aws "$@"
  local exit_code=$?

  # login 성공 시 캐시 삭제 (aws login, aws sso login 모두 감지)
  if (( exit_code == 0 )); then
    if [[ "$1" == "login" ]] || [[ "$1" == "sso" && "$2" == "login" ]]; then
      if [[ -d "$EKS_TOKEN_CACHE_DIR" ]]; then
        local count=$(find "$EKS_TOKEN_CACHE_DIR" -name "*.json" 2>/dev/null | wc -l | tr -d ' ')
        if (( count > 0 )); then
          rm -f "${EKS_TOKEN_CACHE_DIR}"/*.json "${EKS_TOKEN_CACHE_DIR}"/*.meta "${EKS_TOKEN_CACHE_DIR}"/*.error 2>/dev/null
          echo "[aws-login-hook] EKS 토큰 캐시 삭제됨 (${count}개)" >&2
        fi
      fi
    fi
  fi

  return $exit_code
}
```

적용 후 새 shell을 열거나 `source ~/.zsh_functions` 실행

### AWS 인증 에러

```bash
# AWS 세션 확인
aws sts get-caller-identity

# 특정 프로파일 확인
aws --profile my-profile sts get-caller-identity
```

### 캐시가 적용되지 않음

```bash
# kubeconfig exec 설정 확인
kubectl config view --minify -o jsonpath='{.users[0].user.exec}'

# 올바른 설정:
# command: /Users/ethan/.kube/eks-token-cache.sh
# args: [cluster-name, region, profile(optional)]
```

## 멀티 KUBECONFIG 사용 시

`KUBECONFIG`가 여러 파일로 구성된 경우, manager는 **user가 포함된 실제 파일**을 찾아 수정합니다.
복원(`revert`)도 동일한 파일을 대상으로 수행합니다.

## 성능 비교

| 시나리오 | 캐시 없음 | 캐시 있음 |
|----------|-----------|-----------|
| 첫 실행 | ~1.5초 | ~1.5초 |
| 반복 실행 | ~1.5초 | ~0.1초 |
| 10회 연속 | ~15초 | ~1.6초 |

## 라이선스

MIT

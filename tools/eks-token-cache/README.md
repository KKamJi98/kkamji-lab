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
- `yq`: YAML 편집 (manager 스크립트의 apply/revert 기능)
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

# 해제: 원본 aws eks get-token으로 복원
~/.kube/eks-token-cache-manager.sh revert
```

### 디버그 모드

```bash
# 토큰 캐시 동작 확인
EKS_TOKEN_DEBUG=1 kubectl get nodes

# 출력 예시:
# [DEBUG] Token expires in 796s (cluster: staging-32)
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

### v1 (기존 방식) - 파일 mtime 기반
```
캐시 유효성 = (현재시간 - 파일수정시간) < 10분
문제: 파일 touch/복사 시 만료된 토큰 사용 가능
```

### v2 (현재 방식) - 토큰 만료시간 기반
```
캐시 유효성 = 토큰.expirationTimestamp > (현재시간 + 60초)
장점: 실제 토큰 만료 시간 기준으로 정확한 판단
```

### 캐시 파일 위치

```
~/.kube/cache/eks-tokens/
├── staging-32_ap-northeast-2_company.json    # cluster_region_profile 형식
├── prod-32_ap-northeast-2_company.json
└── my-cluster_ap-northeast-2.json            # profile 없는 경우
```

### 원본 exec 백업 (자동)

`apply`는 기존 `user.exec`를 백업하고, `revert`는 백업을 기준으로 정확히 복원합니다.

```
~/.kube/cache/eks-token-cache/backups/
└── <user>.json
```

> 백업에는 `kubeconfig` 파일 경로와 `user.exec` 전체가 저장됩니다.
> 백업이 없으면 현재 설정을 기준으로 복원하며, 추가 옵션은 복원되지 않을 수 있습니다.

## 설정

### 환경변수

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `EKS_TOKEN_DEBUG` | 디버그 로그 출력 | `0` (비활성) |

### 스크립트 상수

| 상수 | 설명 | 기본값 |
|------|------|--------|
| `SAFETY_MARGIN` | 만료 전 갱신 여유 시간 | `60`초 |

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

# Helm 차트 Values 파일

`helm install` 또는 `helm upgrade` 명령어로 Cilium 및 관련 구성 요소를 설치할 때 사용하는 `values.yaml` 파일들을 관리합니다.

---

## 1. 디렉토리 구조

```
helm/
├── cilium/                    # Cilium CNI 설정
│   ├── cilium-values-lab.yaml     # 실습 환경용 (고정 IP)
│   └── cilium-values-kkamji.yaml  # 유연한 환경용 (자동 탐지)
│
└── monitoring/                # 모니터링 도구 설정 (예정)
    └── README.md              # 모니터링 가이드
```

---

## 2. Helm이란?

**Helm**은 Kubernetes의 패키지 관리자입니다. 복잡한 애플리케이션을 차트(Chart)라는 단위로 패키징하여 쉽게 설치, 업그레이드, 롤백할 수 있습니다.

### 2.1. 주요 개념

| 개념 | 설명 |
|------|------|
| **Chart** | Kubernetes 리소스를 정의한 패키지 |
| **Release** | 클러스터에 설치된 Chart 인스턴스 |
| **Repository** | Chart를 저장하고 공유하는 서버 |
| **Values** | Chart의 설정을 커스터마이징하는 파일 |

---

## 3. 사용 방법

### 3.1. Helm 리포지토리 추가

```bash
# Cilium 리포지토리
helm repo add cilium https://helm.cilium.io/

# Prometheus 커뮤니티 리포지토리 (모니터링용)
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# 리포지토리 업데이트
helm repo update
```

### 3.2. Chart 설치

```bash
# values 파일을 사용하여 설치
helm install <release-name> <chart> -f <values-file> -n <namespace>

# 예시: Cilium 설치
helm install cilium cilium/cilium \
  --namespace kube-system \
  -f cilium/cilium-values-lab.yaml
```

### 3.3. 설치 확인 및 관리

```bash
# 설치된 Release 목록
helm list -A

# Release 상태 확인
helm status cilium -n kube-system

# 사용된 values 확인
helm get values cilium -n kube-system

# 업그레이드
helm upgrade cilium cilium/cilium \
  --namespace kube-system \
  -f cilium/cilium-values-lab.yaml

# 제거
helm uninstall cilium -n kube-system
```

---

## 4. Values 파일 커스터마이징

### 4.1. 기본 values 확인

```bash
# Chart의 기본 values 확인
helm show values cilium/cilium > default-values.yaml

# 특정 버전의 values 확인
helm show values cilium/cilium --version 1.14.0
```

### 4.2. Values 오버라이드

Helm은 여러 values 파일을 병합할 수 있습니다:

```bash
# 여러 values 파일 사용 (뒤에 오는 파일이 우선)
helm install cilium cilium/cilium \
  -f base-values.yaml \
  -f environment-specific.yaml \
  --set key=value
```

### 4.3. 우선순위

1. `--set` 플래그로 전달된 값 (최우선)
2. 나중에 지정된 `-f` 파일
3. 먼저 지정된 `-f` 파일
4. Chart의 기본 values.yaml

---

## 5. 디렉토리별 상세

### 5.1. `cilium/`

Cilium CNI 설치를 위한 values 파일들입니다.

| 파일 | 용도 | 특징 |
|------|------|------|
| `cilium-values-lab.yaml` | 실습 환경 | k8sServiceHost 고정 (192.168.10.100) |
| `cilium-values-kkamji.yaml` | 범용 환경 | k8sServiceHost 자동 탐지 |

**공통 활성화 기능:**

- Hubble (네트워크 관측성)
- Prometheus 메트릭
- Native Routing
- kube-proxy 대체

자세한 내용은 [`cilium/README.md`](./cilium/README.md)를 참고하세요.

### 5.2. `monitoring/`

향후 추가될 모니터링 관련 values 파일 공간입니다.

예정된 구성 요소:

- Prometheus (메트릭 수집)
- Grafana (시각화)
- Alertmanager (알림)

---

## 6. 버전 관리

### 6.1. Chart 버전 고정

프로덕션 환경에서는 Chart 버전을 고정하는 것이 좋습니다:

```bash
# 특정 버전으로 설치
helm install cilium cilium/cilium \
  --version 1.14.5 \
  -f cilium/cilium-values-lab.yaml \
  -n kube-system
```

### 6.2. 버전 확인

```bash
# 설치된 Chart 버전 확인
helm list -A

# 사용 가능한 Chart 버전 확인
helm search repo cilium/cilium --versions
```

---

## 7. 트러블슈팅

### 7.1. Chart 설치 실패

```bash
# 상세 로그와 함께 설치 시도
helm install cilium cilium/cilium \
  -f cilium/cilium-values-lab.yaml \
  -n kube-system \
  --debug

# dry-run으로 생성될 매니페스트 확인
helm install cilium cilium/cilium \
  -f cilium/cilium-values-lab.yaml \
  -n kube-system \
  --dry-run
```

### 7.2. Values 문법 오류

```bash
# YAML 문법 검증
helm lint cilium/cilium -f cilium/cilium-values-lab.yaml
```

### 7.3. 업그레이드 충돌

```bash
# 강제 업그레이드 (주의 필요)
helm upgrade cilium cilium/cilium \
  -f cilium/cilium-values-lab.yaml \
  -n kube-system \
  --force
```

---

## 8. 참고 자료

- [Helm 공식 문서](https://helm.sh/docs/)
- [Cilium Helm Chart](https://artifacthub.io/packages/helm/cilium/cilium)
- [Helm Best Practices](https://helm.sh/docs/chart_best_practices/)

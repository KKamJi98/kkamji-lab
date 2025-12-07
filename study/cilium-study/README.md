# Cilium Study - Season 1

`CloudNet@` 커뮤니티의 Gasida님이 진행하신 Cilium 스터디 1기 학습 자료입니다.

Vagrant와 VirtualBox를 사용하여 Kubernetes 클러스터를 자동으로 구축하고, eBPF 기반의 고성능 CNI인 Cilium을 실습합니다.

---

## 1. Cilium이란?

**Cilium**은 eBPF(extended Berkeley Packet Filter)를 기반으로 한 오픈소스 네트워킹, 보안, 관측성 솔루션입니다. Linux 커널에서 직접 네트워크 패킷을 처리하여 기존 `kube-proxy`보다 뛰어난 성능을 제공합니다.

### 1.1. 주요 특징

| 기능 | 설명 |
|------|------|
| **eBPF 기반 데이터플레인** | 커널 레벨에서 패킷 처리, iptables 대비 높은 성능 |
| **kube-proxy 대체** | 완전한 kube-proxy replacement 모드 지원 |
| **네트워크 정책** | L3/L4/L7 레벨의 세밀한 네트워크 정책 적용 |
| **Hubble** | 네트워크 흐름 관측성 및 서비스 맵 시각화 |
| **서비스 메시** | 사이드카 없는 서비스 메시 구현 가능 |
| **멀티 클러스터** | Cluster Mesh를 통한 멀티 클러스터 네트워킹 |

---

## 2. 프로젝트 구조

```
.
├── helm/                      # Helm 차트 values 파일
│   ├── cilium/               # Cilium 설치 설정
│   │   ├── cilium-values-lab.yaml    # 실습용 (고정 IP)
│   │   └── cilium-values-kkamji.yaml # 유연한 설정 (자동 탐지)
│   └── monitoring/           # 모니터링 도구 설정 (예정)
│
├── install-flannel/          # Flannel CNI 대안 설치
│   └── flannel-values.yaml   # Flannel Helm values
│
├── scripts/                  # 유틸리티 스크립트
│   ├── check-cilium-kernel-cfg.sh  # 커널 설정 검사
│   ├── setup_cilium_kernel.sh      # 커널 모듈 자동 로드
│   ├── rollout-restart-all.sh      # 전체 워크로드 재시작
│   └── setup-kubecontext.sh        # 로컬 kubectl 설정
│
├── tests/                    # 테스트용 샘플 애플리케이션
│   └── README.md             # 배포 예제 코드
│
└── vagrant/                  # Kubernetes 클러스터 환경
    ├── vagrant-original/     # CLI 기반 kubeadm 구성
    └── vagrant-advanced/     # YAML 기반 선언적 구성 (권장)
```

---

## 3. 실습 환경 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        Host Machine                              │
│  (VirtualBox + Vagrant)                                         │
│                                                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   cilium-m1     │  │   cilium-w1     │  │   cilium-w2     │ │
│  │  (Master Node)  │  │  (Worker Node)  │  │  (Worker Node)  │ │
│  │                 │  │                 │  │                 │ │
│  │  192.168.10.100 │  │  192.168.10.101 │  │  192.168.10.102 │ │
│  │                 │  │                 │  │                 │ │
│  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌───────────┐  │ │
│  │  │  Cilium   │  │  │  │  Cilium   │  │  │  │  Cilium   │  │ │
│  │  │  Agent    │  │  │  │  Agent    │  │  │  │  Agent    │  │ │
│  │  └───────────┘  │  │  └───────────┘  │  │  └───────────┘  │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
│                                                                  │
│  Pod CIDR: 10.10.0.0/16                                         │
│  Service CIDR: 10.200.0.0/16                                    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. 시작하기

### 4.1. 사전 요구사항

```bash
# macOS
brew install vagrant
brew install --cask virtualbox

# Ubuntu/Debian
sudo apt install vagrant virtualbox
```

### 4.2. 클러스터 구축 (권장: vagrant-advanced)

```bash
# 고급 설정 환경으로 이동 (kube-proxy 비활성화 포함)
cd vagrant/vagrant-advanced

# VM 생성 및 Kubernetes 클러스터 구축
vagrant up

# Master 노드 접속
vagrant ssh cilium-m1

# 클러스터 상태 확인
kubectl get nodes

# kube-proxy가 비활성화된 것 확인
kubectl get ds -n kube-system kube-proxy
# 결과: No resources found
```

### 4.3. Cilium 설치

```bash
# Cilium Helm 리포지토리 추가
helm repo add cilium https://helm.cilium.io/
helm repo update

# Cilium 설치 (values 파일 사용)
helm install cilium cilium/cilium \
  --namespace kube-system \
  -f /vagrant/helm/cilium/cilium-values-lab.yaml

# 설치 상태 확인
kubectl get pods -n kube-system -l k8s-app=cilium

# Cilium CLI로 상태 확인 (선택)
cilium status
```

### 4.4. 로컬에서 kubectl 사용 (선택)

```bash
# 로컬 머신에서 실행
cd scripts
./setup-kubecontext.sh

# 컨텍스트 전환
kubectl config use-context cilium-cluster
```

---

## 5. 디렉토리 상세 설명

### 5.1. `vagrant/`

두 가지 클러스터 구성 방식을 제공합니다:

| 환경 | 특징 | 권장 용도 |
|------|------|----------|
| `vagrant-original/` | kubeadm CLI 옵션 기반 | 기본 구성 학습 |
| `vagrant-advanced/` | kubeadm YAML 설정 기반 | Cilium 실습 (kube-proxy 제외) |

### 5.2. `helm/cilium/`

| 파일 | k8sServiceHost | 특징 |
|------|----------------|------|
| `cilium-values-lab.yaml` | `192.168.10.100` (고정) | 실습 환경 최적화 |
| `cilium-values-kkamji.yaml` | `auto` (자동 탐지) | 다양한 환경 호환 |

**공통 활성화 기능:**

- Hubble (네트워크 관측성)
- Prometheus 메트릭 노출
- Native Routing 모드
- kube-proxy 대체 (strict 모드)
- Host Firewall

### 5.3. `scripts/`

| 스크립트 | 용도 |
|----------|------|
| `check-cilium-kernel-cfg.sh` | Cilium 커널 요구사항 검사 |
| `setup_cilium_kernel.sh` | 누락된 커널 모듈 자동 로드 |
| `rollout-restart-all.sh` | 전체 워크로드 롤아웃 재시작 |
| `setup-kubecontext.sh` | 로컬 kubeconfig 설정 |

### 5.4. `install-flannel/`

Cilium 대신 Flannel CNI를 사용하고자 할 때 참고하세요.

```bash
helm repo add flannel https://flannel-io.github.io/flannel/
helm install flannel flannel/flannel \
  --namespace kube-flannel --create-namespace \
  -f flannel-values.yaml
```

---

## 6. 주요 학습 주제

### 6.1. Week 1-2: 기본 환경 구축

- Vagrant를 활용한 멀티 노드 클러스터 구축
- kubeadm의 InitConfiguration/JoinConfiguration 이해
- Cilium 설치 및 기본 동작 확인

### 6.2. Week 3-4: Cilium 네트워킹 심화

- eBPF 데이터플레인 동작 원리
- kube-proxy 대체 모드 분석
- Native Routing vs Tunneling 비교

### 6.3. Week 5-6: 네트워크 정책 및 보안

- L3/L4 네트워크 정책 작성
- L7 정책 (HTTP, gRPC)
- DNS 기반 정책

### 6.4. Week 7-8: 관측성 및 고급 기능

- Hubble을 통한 네트워크 플로우 관측
- Grafana 대시보드 구성
- Cluster Mesh 구성 (멀티 클러스터)

---

## 7. 트러블슈팅

### 7.1. Cilium Pod가 시작되지 않는 경우

```bash
# 커널 설정 확인
./scripts/check-cilium-kernel-cfg.sh

# 필요한 커널 모듈 로드
./scripts/setup_cilium_kernel.sh
```

### 7.2. CNI 변경 후 Pod 네트워크 문제

```bash
# 모든 워크로드 재시작
./scripts/rollout-restart-all.sh
```

### 7.3. 노드 상태가 NotReady인 경우

```bash
# Cilium 상태 확인
kubectl get pods -n kube-system -l k8s-app=cilium
kubectl logs -n kube-system -l k8s-app=cilium

# BPF 파일시스템 마운트 확인
mount | grep bpf
```

---

## 8. 참고 자료

- [Cilium 공식 문서](https://docs.cilium.io/)
- [Cilium GitHub](https://github.com/cilium/cilium)
- [eBPF.io](https://ebpf.io/)
- [CloudNet@ Cilium 스터디 노션](https://www.notion.so/CloudNet-Blog-c9dfa44a27ff431dafdd2edacc8a1863)

---

## 9. 감사의 말

`CloudNet@` 커뮤니티의 **Gasida**님께 Cilium 스터디 자료와 실습 가이드를 제공해 주신 것에 감사드립니다.

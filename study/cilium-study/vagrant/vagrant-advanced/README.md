# vagrant-advanced: 선언적 구성을 이용한 Kubernetes 클러스터

`kubeadm`의 YAML 설정 파일을 사용하여 Kubernetes 클러스터를 자동으로 구성하는 고급 환경입니다.

이 방식은 더 체계적이고 재현 가능하며, **Cilium CNI 사용에 최적화**되어 있습니다.

## 주요 특징

### 선언적 클러스터 구성

기존 명령줄 옵션 대신 YAML 설정 파일을 사용하여 클러스터를 구성합니다:

```yaml
# configurations/init-configuration.yaml (요약)
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
kubernetesVersion: v1.32.0
networking:
  podSubnet: "10.10.0.0/16"
  serviceSubnet: "10.200.0.0/16"
---
apiVersion: kubeadm.k8s.io/v1beta3
kind: InitConfiguration
skipPhases:
  - addon/kube-proxy  # Cilium이 kube-proxy 역할 대체
```

### kube-proxy 비활성화

`skipPhases: ["addon/kube-proxy"]` 설정을 통해 `kube-proxy`를 설치하지 않습니다. 이를 통해:

- Cilium의 eBPF 기반 서비스 라우팅 사용 가능
- iptables 규칙 충돌 방지
- 더 나은 성능 및 관측성 확보

## 디렉토리 구조

```
vagrant-advanced/
├── Vagrantfile              # VM 정의 및 프로비저닝 설정
├── configurations/          # kubeadm 설정 파일
│   ├── init-configuration.yaml   # Master 초기화 설정
│   └── join-configuration.yaml   # Worker 조인 설정
├── init_cfg.sh              # 공통 패키지 설치 스크립트
├── k8s-ctr.sh               # Master 초기화 스크립트
└── k8s-w.sh                 # Worker 조인 스크립트
```

## 프로비저닝 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  vagrant up                                                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. init_cfg.sh (모든 노드)                                      │
│     - OS 업데이트 및 기본 패키지 설치                              │
│     - containerd 설치 및 구성                                     │
│     - kubelet, kubeadm, kubectl 설치                             │
│     - 커널 모듈 로드 (br_netfilter, overlay)                      │
│     - sysctl 설정 (ip_forward 등)                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐     ┌───────────────────────────────────┐
│  2. k8s-ctr.sh        │     │  3. k8s-w.sh (Worker 노드)         │
│     (Master 노드)      │     │     - join-configuration.yaml     │
│  - init-configuration │     │       사용하여 클러스터 참여        │
│    .yaml 사용         │     │     - kubeadm join --config=...   │
│  - kubeadm init       │     │                                   │
│    --config=...       │     │                                   │
│  - join 토큰 저장     │     │                                   │
│  - kubeconfig 설정    │     │                                   │
└───────────────────────┘     └───────────────────────────────────┘
```

## 사용 방법

### 1. 클러스터 생성

```bash
# 현재 디렉토리에서 실행
vagrant up

# 진행 상황 확인 (약 10-15분 소요)
# - cilium-m1: Master 노드 프로비저닝
# - cilium-w1: Worker 1 프로비저닝
# - cilium-w2: Worker 2 프로비저닝
```

### 2. 클러스터 상태 확인

```bash
# Master 노드 접속
vagrant ssh cilium-m1

# 노드 상태 확인 (CNI 설치 전이므로 NotReady 상태)
kubectl get nodes
# NAME        STATUS     ROLES           AGE   VERSION
# cilium-m1   NotReady   control-plane   5m    v1.32.0
# cilium-w1   NotReady   <none>          3m    v1.32.0
# cilium-w2   NotReady   <none>          1m    v1.32.0

# kube-proxy가 없는 것 확인
kubectl get ds -n kube-system kube-proxy
# No resources found in kube-system namespace.

# 시스템 Pod 확인
kubectl get pods -n kube-system
```

### 3. Cilium 설치

```bash
# Helm 리포지토리 추가
helm repo add cilium https://helm.cilium.io/
helm repo update

# Cilium 설치 (values 파일 사용)
helm install cilium cilium/cilium \
  --namespace kube-system \
  -f /vagrant/helm/cilium/cilium-values-lab.yaml

# 설치 완료 대기
kubectl rollout status daemonset/cilium -n kube-system

# 노드 상태 재확인 (Ready 상태로 변경)
kubectl get nodes
# NAME        STATUS   ROLES           AGE   VERSION
# cilium-m1   Ready    control-plane   10m   v1.32.0
# cilium-w1   Ready    <none>          8m    v1.32.0
# cilium-w2   Ready    <none>          6m    v1.32.0
```

### 4. 연결 테스트

```bash
# 테스트 Pod 배포
kubectl apply -f /vagrant/tests/

# Pod 간 통신 테스트
kubectl exec -it curl-pod -- curl webpod
```

## 설정 파일 상세

### init-configuration.yaml

| 섹션 | 설명 |
|------|------|
| `ClusterConfiguration` | API 서버, 컨트롤러 매니저 등 컨트롤 플레인 설정 |
| `InitConfiguration` | 초기화 시 스킵할 단계 (kube-proxy) |
| `KubeletConfiguration` | kubelet 런타임 설정 |

### join-configuration.yaml

| 섹션 | 설명 |
|------|------|
| `JoinConfiguration` | 클러스터 참여 토큰, API 서버 주소 |

## VM 리소스 요구사항

| 노드 | CPU | Memory | Disk |
|------|-----|--------|------|
| cilium-m1 | 2 cores | 2048 MB | 20 GB |
| cilium-w1 | 2 cores | 2048 MB | 20 GB |
| cilium-w2 | 2 cores | 2048 MB | 20 GB |
| **총합** | **6 cores** | **6 GB** | **60 GB** |

## 트러블슈팅

### 노드가 NotReady 상태로 유지되는 경우

CNI가 설치되지 않았거나 정상 동작하지 않을 수 있습니다:

```bash
# CNI 상태 확인
kubectl get pods -n kube-system -l k8s-app=cilium

# Cilium 로그 확인
kubectl logs -n kube-system -l k8s-app=cilium
```

### kubeadm init 실패

```bash
# 로그 확인
sudo journalctl -xeu kubelet

# 초기화 후 재시도
sudo kubeadm reset -f
sudo rm -rf /etc/cni/net.d/*
```

### containerd 소켓 오류

```bash
# containerd 상태 확인
sudo systemctl status containerd

# 재시작
sudo systemctl restart containerd
```

## 클린업

```bash
# 모든 VM 삭제
vagrant destroy -f

# 특정 VM만 삭제
vagrant destroy cilium-w2 -f
```

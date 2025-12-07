# vagrant-original: 스크립트 기반 Kubernetes 클러스터

`kubeadm`의 모든 옵션을 명령줄 인자로 직접 전달하는 전통적인 방식을 사용하여 Kubernetes 클러스터를 자동으로 구성하는 환경입니다.

이 방식은 Kubernetes 클러스터 구축의 **기본 원리를 이해**하는 데 적합합니다.

---

## 1. vagrant-advanced와의 차이점

| 항목 | vagrant-original | vagrant-advanced |
|------|-----------------|------------------|
| kubeadm 구성 방식 | CLI 옵션 직접 전달 | YAML 설정 파일 |
| kube-proxy | **활성화** | 비활성화 |
| 권장 CNI | Flannel, Calico 등 | Cilium |
| 설정 재현성 | 스크립트 의존 | 설정 파일 버전 관리 가능 |

---

## 2. 주요 특징

### 2.1. 명령줄 인수 기반 구성

별도의 YAML 설정 파일 없이 `kubeadm init` 및 `kubeadm join` 명령어에 필요한 옵션을 직접 명시합니다:

```bash
# Master 노드 초기화 (k8s-ctr.sh)
kubeadm init \
  --pod-network-cidr=10.244.0.0/16 \
  --apiserver-advertise-address=192.168.10.100 \
  --apiserver-cert-extra-sans=192.168.10.100

# Worker 노드 참여 (k8s-w.sh)
kubeadm join 192.168.10.100:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash>
```

### 2.2. kube-proxy 활성화

이 환경에서는 `kube-proxy`가 기본적으로 설치됩니다:

- iptables 기반 서비스 라우팅
- 대부분의 CNI 플러그인과 호환
- 전통적인 Kubernetes 네트워킹 학습에 적합

---

## 3. 디렉토리 구조

```
vagrant-original/
├── Vagrantfile     # VM 정의 및 프로비저닝 설정
├── init_cfg.sh     # 공통 패키지 설치 스크립트
├── k8s-ctr.sh      # Master 초기화 스크립트
└── k8s-w.sh        # Worker 조인 스크립트
```

---

## 4. 프로비저닝 흐름

```
┌─────────────────────────────────────────────────────────────────┐
│  vagrant up                                                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  1. init_cfg.sh (모든 노드)                                      │
│     - 패키지 업데이트 및 의존성 설치                               │
│     - containerd 설치 및 구성                                     │
│     - kubelet, kubeadm, kubectl 설치                             │
│     - 네트워크 설정 (br_netfilter, ip_forward)                    │
└───────────────────────────┬─────────────────────────────────────┘
                            │
            ┌───────────────┴───────────────┐
            ▼                               ▼
┌───────────────────────┐     ┌───────────────────────────────────┐
│  2. k8s-ctr.sh        │     │  3. k8s-w.sh (Worker 노드)         │
│     (Master 노드)      │     │     - 저장된 토큰으로              │
│  - kubeadm init 실행  │     │       kubeadm join 실행            │
│    (CLI 옵션 사용)    │     │     - 클러스터 참여                 │
│  - join 토큰 생성     │     │                                   │
│  - kubeconfig 설정    │     │                                   │
└───────────────────────┘     └───────────────────────────────────┘
```

---

## 5. 사용 방법

### 5.1. 클러스터 생성

```bash
# 현재 디렉토리에서 실행
vagrant up

# 진행 상황 확인 (약 10-15분 소요)
```

### 5.2. 클러스터 상태 확인

```bash
# Master 노드 접속
vagrant ssh cilium-m1

# 노드 상태 확인 (CNI 설치 전이므로 NotReady)
kubectl get nodes

# kube-proxy DaemonSet 확인 (이 환경에서는 존재함)
kubectl get ds -n kube-system kube-proxy
# NAME         DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE
# kube-proxy   3         3         3       3            3

# kube-proxy Pod 확인
kubectl get pods -n kube-system -l k8s-app=kube-proxy
```

### 5.3. CNI 설치

이 환경에서는 `kube-proxy`가 활성화되어 있으므로 대부분의 CNI를 사용할 수 있습니다:

**Flannel 설치 (권장):**

```bash
helm repo add flannel https://flannel-io.github.io/flannel/
helm install flannel flannel/flannel \
  --namespace kube-flannel --create-namespace \
  -f /vagrant/install-flannel/flannel-values.yaml
```

**Cilium 설치 (kube-proxy 모드):**

```bash
helm repo add cilium https://helm.cilium.io/
helm install cilium cilium/cilium \
  --namespace kube-system \
  --set kubeProxyReplacement=disabled
```

### 5.4. 클러스터 검증

```bash
# 노드 상태 확인 (Ready)
kubectl get nodes
# NAME        STATUS   ROLES           AGE   VERSION
# cilium-m1   Ready    control-plane   10m   v1.32.0
# cilium-w1   Ready    <none>          8m    v1.32.0
# cilium-w2   Ready    <none>          6m    v1.32.0

# 시스템 Pod 상태 확인
kubectl get pods -n kube-system
```

---

## 6. VM 리소스 요구사항

| 노드 | CPU | Memory | Disk |
|------|-----|--------|------|
| cilium-m1 | 2 cores | 2048 MB | 20 GB |
| cilium-w1 | 2 cores | 2048 MB | 20 GB |
| cilium-w2 | 2 cores | 2048 MB | 20 GB |
| **총합** | **6 cores** | **6 GB** | **60 GB** |

---

## 7. 트러블슈팅

### 7.1. 노드가 NotReady 상태

CNI 플러그인이 설치되지 않은 경우 발생합니다:

```bash
# CNI 플러그인 상태 확인
ls /etc/cni/net.d/

# Flannel 또는 다른 CNI 설치 필요
```

### 7.2. kubeadm join 실패

토큰이 만료되었을 수 있습니다:

```bash
# Master에서 새 토큰 생성
kubeadm token create --print-join-command

# Worker에서 새 명령어로 재시도
```

### 7.3. 네트워크 문제

```bash
# iptables 규칙 확인
sudo iptables -L -n

# kube-proxy 로그 확인
kubectl logs -n kube-system -l k8s-app=kube-proxy
```

---

## 8. 클린업

```bash
# 모든 VM 삭제
vagrant destroy -f

# 특정 VM만 삭제
vagrant destroy cilium-w2 -f
```

---

## 9. 다음 단계

- Cilium의 고급 기능을 실습하려면 [`vagrant-advanced`](../vagrant-advanced/README.md) 환경 사용을 권장합니다.
- 이 환경에서 Cilium을 사용하려면 `kubeProxyReplacement=disabled` 옵션으로 설치하세요.

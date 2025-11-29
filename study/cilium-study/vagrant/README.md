# Vagrant 기반 Kubernetes 클러스터

Vagrant와 VirtualBox를 사용하여 Kubernetes 클러스터를 자동으로 구축하는 환경입니다. 두 가지 구성 방식을 제공하여 학습 목적에 맞게 선택할 수 있습니다.

## 환경 비교

| 항목 | vagrant-original | vagrant-advanced |
|------|-----------------|------------------|
| **구성 방식** | kubeadm CLI 옵션 | kubeadm YAML 설정 파일 |
| **kube-proxy** | 활성화 | 비활성화 (Cilium 대체) |
| **학습 목적** | 기본 클러스터 구축 이해 | Cilium 실습 최적화 |
| **선언적 관리** | 제한적 | 완전 지원 |

## 환경 구성

### `vagrant-original/` - 스크립트 기반 구성

- `kubeadm` 명령어에 모든 옵션을 직접 인자로 전달하는 전통적인 방식
- Kubernetes 클러스터 구축의 기본적인 스크립트 기반 흐름을 이해하는 데 적합
- `kube-proxy`가 기본적으로 활성화되어 있어 Flannel 등 다른 CNI와 함께 사용 가능

```bash
# 예시: kubeadm init 명령어
kubeadm init --pod-network-cidr=10.244.0.0/16 --apiserver-advertise-address=192.168.10.100
```

### `vagrant-advanced/` - 선언적 구성 (권장)

- `kubeadm`의 `InitConfiguration`, `JoinConfiguration` 등 YAML 설정 파일을 사용하는 선언적 방식
- Cilium CNI 사용에 최적화되어 있으며, `kube-proxy`를 비활성화하는 설정 포함
- 설정 파일을 통해 클러스터 구성을 버전 관리 가능

```yaml
# 예시: InitConfiguration의 skipPhases
apiVersion: kubeadm.k8s.io/v1beta3
kind: ClusterConfiguration
skipPhases:
  - addon/kube-proxy  # Cilium이 kube-proxy 역할을 대체
```

## 공통 아키텍처

두 환경 모두 동일한 노드 구성을 사용합니다:

```
┌─────────────────────────────────────────────────────────────┐
│  VirtualBox VMs (Vagrant Managed)                          │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  cilium-m1   │  │  cilium-w1   │  │  cilium-w2   │      │
│  │  (Master)    │  │  (Worker 1)  │  │  (Worker 2)  │      │
│  │              │  │              │  │              │      │
│  │  CPU: 2      │  │  CPU: 2      │  │  CPU: 2      │      │
│  │  RAM: 2048MB │  │  RAM: 2048MB │  │  RAM: 2048MB │      │
│  │              │  │              │  │              │      │
│  │  eth0: NAT   │  │  eth0: NAT   │  │  eth0: NAT   │      │
│  │  eth1:       │  │  eth1:       │  │  eth1:       │      │
│  │  .10.100     │  │  .10.101     │  │  .10.102     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                             │
│  Network: 192.168.10.0/24 (Host-Only)                      │
└─────────────────────────────────────────────────────────────┘
```

### 네트워크 구성

| 네트워크 | CIDR | 용도 |
|----------|------|------|
| Node Network | 192.168.10.0/24 | 노드 간 통신 (Host-Only) |
| Pod Network | 10.10.0.0/16 | Pod 간 통신 |
| Service Network | 10.200.0.0/16 | 서비스 ClusterIP |

## 빠른 시작

### 사전 요구사항

```bash
# macOS
brew install vagrant
brew install --cask virtualbox

# Windows (Chocolatey)
choco install vagrant virtualbox

# Ubuntu/Debian
sudo apt update
sudo apt install -y vagrant virtualbox
```

### 클러스터 생성

```bash
# 환경 선택 (vagrant-advanced 권장)
cd vagrant-advanced

# VM 생성 및 클러스터 구축 (약 10-15분 소요)
vagrant up

# 클러스터 상태 확인
vagrant ssh cilium-m1 -c "kubectl get nodes"
```

### VM 관리 명령어

```bash
# 특정 VM에 SSH 접속
vagrant ssh cilium-m1
vagrant ssh cilium-w1
vagrant ssh cilium-w2

# 모든 VM 상태 확인
vagrant status

# VM 중지 (데이터 보존)
vagrant halt

# VM 재시작
vagrant up

# VM 완전 삭제 (주의: 데이터 손실)
vagrant destroy -f
```

## 프로비저닝 스크립트

각 환경은 다음 스크립트를 사용하여 자동 프로비저닝됩니다:

| 스크립트 | 실행 노드 | 역할 |
|----------|----------|------|
| `init_cfg.sh` | 모든 노드 | 공통 패키지 설치 (containerd, kubelet, kubeadm) |
| `k8s-ctr.sh` | Master | kubeadm init으로 컨트롤 플레인 초기화 |
| `k8s-w.sh` | Worker | kubeadm join으로 클러스터 참여 |

## 상세 문서

- [`vagrant-original/README.md`](./vagrant-original/README.md) - 스크립트 기반 구성 상세
- [`vagrant-advanced/README.md`](./vagrant-advanced/README.md) - 선언적 구성 상세

## 트러블슈팅

### VM 생성 실패

```bash
# VirtualBox 서비스 확인
sudo systemctl status vboxdrv

# Vagrant 플러그인 업데이트
vagrant plugin update
```

### 네트워크 충돌

```bash
# 기존 Host-Only 네트워크 확인
VBoxManage list hostonlyifs

# 충돌하는 네트워크 삭제
VBoxManage hostonlyif remove vboxnet0
```

### 메모리 부족

`Vagrantfile`에서 메모리 설정을 조정할 수 있습니다:

```ruby
config.vm.provider "virtualbox" do |vb|
  vb.memory = "1536"  # 2048 -> 1536MB로 축소
end
```

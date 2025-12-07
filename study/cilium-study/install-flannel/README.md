# Flannel CNI 설치 가이드

Cilium의 대안으로 Flannel CNI를 설치할 때 사용하는 설정과 가이드입니다.

---

## 1. Flannel이란?

**Flannel**은 CoreOS에서 개발한 간단하고 가벼운 Kubernetes CNI 플러그인입니다. VXLAN, host-gw 등 다양한 백엔드를 지원하며, 설정이 간단하여 학습 및 테스트 환경에 적합합니다.

### 1.1. Cilium vs Flannel 비교

| 항목 | Cilium | Flannel |
|------|--------|---------|
| 기반 기술 | eBPF | VXLAN/host-gw |
| 네트워크 정책 | L3/L4/L7 지원 | 미지원 (별도 도구 필요) |
| kube-proxy 대체 | 지원 | 미지원 |
| 관측성 | Hubble 내장 | 미지원 |
| 복잡도 | 높음 | 낮음 |
| 리소스 사용량 | 중간 | 낮음 |
| 권장 환경 | 프로덕션, 고급 기능 필요 시 | 개발/테스트, 간단한 네트워킹 |

---

## 2. 파일 설명

### 2.1. `flannel-values.yaml`

Flannel Helm 차트 설치 시 사용하는 values 파일입니다.

```yaml
# flannel-values.yaml 주요 설정
podCidr: "10.244.0.0/16"    # Pod 네트워크 CIDR
podCidrv6: ""               # IPv6 (사용 안 함)

flannel:
  # Vagrant 환경에서 eth1 인터페이스 사용
  # (eth0은 NAT, eth1은 Host-Only 네트워크)
  iface: "eth1"

  # 백엔드 설정 (기본: VXLAN)
  backend: "vxlan"
```

**주요 설정 항목:**

| 설정 | 설명 | 기본값 |
|------|------|--------|
| `podCidr` | Pod에 할당할 IP 대역 | `10.244.0.0/16` |
| `flannel.iface` | 사용할 네트워크 인터페이스 | 자동 탐지 |
| `flannel.backend` | 오버레이 네트워크 방식 | `vxlan` |

---

## 3. 설치 방법

### 3.1. Helm 리포지토리 추가

```bash
helm repo add flannel https://flannel-io.github.io/flannel/
helm repo update
```

### 3.2. Flannel 설치

```bash
# 네임스페이스 생성 및 Flannel 설치
helm install flannel flannel/flannel \
  --namespace kube-flannel \
  --create-namespace \
  -f flannel-values.yaml
```

### 3.3. 설치 확인

```bash
# Flannel Pod 상태 확인
kubectl get pods -n kube-flannel

# 예상 출력:
# NAME                    READY   STATUS    RESTARTS   AGE
# kube-flannel-ds-xxxxx   1/1     Running   0          30s
# kube-flannel-ds-yyyyy   1/1     Running   0          30s
# kube-flannel-ds-zzzzz   1/1     Running   0          30s

# DaemonSet 확인
kubectl get ds -n kube-flannel

# 노드 상태 확인 (Ready로 변경됨)
kubectl get nodes
```

---

## 4. 백엔드 옵션

Flannel은 여러 백엔드를 지원합니다:

### 4.1. VXLAN (기본값)

모든 환경에서 동작하는 범용 오버레이 네트워크입니다.

```yaml
flannel:
  backend: "vxlan"
```

**특징:**

- UDP 캡슐화로 L3 네트워크를 통과
- 약간의 오버헤드 발생
- 클라우드/온프레미스 모두 호환

### 4.2. host-gw

직접 라우팅 방식으로 더 나은 성능을 제공합니다.

```yaml
flannel:
  backend: "host-gw"
```

**특징:**

- L2 네트워크 필요 (노드가 같은 서브넷)
- 오버헤드 최소화
- Vagrant Host-Only 네트워크에 적합

### 4.3. WireGuard

암호화된 터널을 제공합니다.

```yaml
flannel:
  backend: "wireguard"
```

**특징:**

- 최신 암호화 프로토콜
- 커널 WireGuard 모듈 필요
- 보안이 중요한 환경에 적합

---

## 5. Vagrant 환경에서의 주의사항

### 5.1. 네트워크 인터페이스 설정

Vagrant VM은 일반적으로 두 개의 네트워크 인터페이스를 가집니다:

| 인터페이스 | 용도 | IP 대역 |
|------------|------|---------|
| `eth0` | NAT (Vagrant 관리용) | 10.0.2.x |
| `eth1` | Host-Only (노드 간 통신) | 192.168.10.x |

Flannel은 노드 간 통신에 `eth1`을 사용해야 합니다:

```yaml
flannel:
  iface: "eth1"  # 반드시 지정 필요
```

### 5.2. Pod CIDR 충돌 방지

`kubeadm init` 시 사용한 Pod CIDR과 Flannel 설정이 일치해야 합니다:

```bash
# kubeadm init 시
kubeadm init --pod-network-cidr=10.244.0.0/16

# flannel-values.yaml에서
podCidr: "10.244.0.0/16"  # 동일해야 함
```

---

## 6. 트러블슈팅

### 6.1. Flannel Pod가 CrashLoopBackOff

```bash
# 로그 확인
kubectl logs -n kube-flannel -l app=flannel

# 일반적인 원인:
# 1. 잘못된 인터페이스 설정
# 2. Pod CIDR 불일치
# 3. 커널 모듈 누락
```

### 6.2. 노드 간 통신 실패

```bash
# flannel.1 인터페이스 확인
ip addr show flannel.1

# 라우팅 테이블 확인
ip route | grep flannel

# VXLAN 연결 테스트
ping <other-node-flannel-ip>
```

### 6.3. CNI 설정 파일 확인

```bash
# CNI 설정 디렉토리 확인
ls -la /etc/cni/net.d/

# 설정 파일 내용 확인
cat /etc/cni/net.d/10-flannel.conflist
```

---

## 7. 제거 방법

```bash
# Helm으로 제거
helm uninstall flannel -n kube-flannel

# 네임스페이스 삭제
kubectl delete namespace kube-flannel

# CNI 설정 파일 정리 (각 노드에서)
sudo rm -f /etc/cni/net.d/10-flannel.conflist
```

---

## 8. 참고 자료

- [Flannel 공식 GitHub](https://github.com/flannel-io/flannel)
- [Flannel 문서](https://github.com/flannel-io/flannel/blob/master/Documentation/kubernetes.md)
- [CNI 명세](https://github.com/containernetworking/cni/blob/master/SPEC.md)

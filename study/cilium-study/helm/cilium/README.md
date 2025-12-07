# Cilium Helm Values

Cilium CNI를 설치하기 위한 `values.yaml` 설정 파일 모음입니다.

---

## 1. 파일 목록

| 파일 | k8sServiceHost | 권장 환경 |
|------|----------------|----------|
| `cilium-values-lab.yaml` | `192.168.10.100` (고정) | Vagrant 실습 환경 |
| `cilium-values-kkamji.yaml` | `auto` (자동 탐지) | 다양한 환경 |

---

## 2. 공통 활성화 기능

두 파일 모두 다음 기능이 활성화되어 있습니다:

### 2.1. kube-proxy 대체 (Strict 모드)

```yaml
kubeProxyReplacement: "strict"
```

- `kube-proxy`를 완전히 대체
- eBPF 기반 서비스 라우팅
- iptables 규칙 불필요

### 2.2. Hubble (네트워크 관측성)

```yaml
hubble:
  enabled: true
  relay:
    enabled: true
  ui:
    enabled: true
```

- 네트워크 플로우 실시간 관찰
- 서비스 맵 시각화
- 문제 진단 및 디버깅

### 2.3. Prometheus 메트릭

```yaml
prometheus:
  enabled: true
```

- Cilium 에이전트 메트릭 노출
- Grafana 대시보드 연동 가능

### 2.4. Native Routing

```yaml
routingMode: "native"
ipv4NativeRoutingCIDR: "10.10.0.0/16"
```

- VXLAN 오버헤드 없는 직접 라우팅
- 더 나은 네트워크 성능

### 2.5. Host Firewall

```yaml
hostFirewall:
  enabled: true
```

- 호스트 레벨 방화벽 정책 적용 가능

---

## 3. 파일별 상세 설정

### 3.1. `cilium-values-lab.yaml`

실습 환경을 위해 사전 구성된 설정입니다.

```yaml
# Kubernetes API 서버 주소 (고정)
k8sServiceHost: "192.168.10.100"
k8sServicePort: 6443
```

**특징:**

- Vagrant 환경의 Master 노드 IP 하드코딩
- `vagrant-advanced` 또는 `vagrant-original`의 Vagrantfile과 일치
- 설정 변경 없이 바로 사용 가능

**사용법:**

```bash
helm install cilium cilium/cilium \
  --namespace kube-system \
  -f cilium-values-lab.yaml
```

### 3.2. `cilium-values-kkamji.yaml`

다양한 환경에서 유연하게 사용할 수 있는 설정입니다.

```yaml
# Kubernetes API 서버 자동 탐지
k8sServiceHost: "auto"
k8sServicePort: 6443
```

**특징:**

- Cilium이 API 서버 주소를 자동으로 탐지
- 클라우드 환경, 다른 IP 대역 등에서도 동작
- 환경에 따라 일부 설정 조정 필요할 수 있음

**사용법:**

```bash
helm install cilium cilium/cilium \
  --namespace kube-system \
  -f cilium-values-kkamji.yaml
```

---

## 4. 주요 설정 항목 설명

### 4.1. 네트워크 설정

```yaml
# Pod 네트워크 CIDR (kubeadm init과 일치해야 함)
ipam:
  mode: "kubernetes"
  operator:
    clusterPoolIPv4PodCIDRList: ["10.10.0.0/16"]

# Native Routing CIDR
ipv4NativeRoutingCIDR: "10.10.0.0/16"
```

### 4.2. kube-proxy 대체 설정

```yaml
kubeProxyReplacement: "strict"

# API 서버 연결 정보
k8sServiceHost: "192.168.10.100"  # 또는 "auto"
k8sServicePort: 6443
```

**kubeProxyReplacement 옵션:**

| 값 | 설명 |
|----|------|
| `disabled` | kube-proxy와 공존 (기능 미사용) |
| `partial` | 일부 기능만 대체 |
| `strict` | 완전 대체 (kube-proxy 없이 사용) |

### 4.3. Hubble 설정

```yaml
hubble:
  enabled: true

  # Hubble Relay (gRPC 서버)
  relay:
    enabled: true

  # Hubble UI (웹 대시보드)
  ui:
    enabled: true

  # 메트릭 수집
  metrics:
    enabled:
      - dns
      - drop
      - tcp
      - flow
      - port-distribution
```

### 4.4. 에이전트 설정

```yaml
# BPF 마운트 경로
bpf:
  masquerade: true
  hostLegacyRouting: false

# 디버깅
debug:
  enabled: false
```

---

## 5. 설치 후 확인

### 5.1. Cilium 상태 확인

```bash
# Cilium Pod 상태
kubectl get pods -n kube-system -l k8s-app=cilium

# Cilium CLI로 상태 확인
cilium status

# 에이전트 로그 확인
kubectl logs -n kube-system -l k8s-app=cilium
```

### 5.2. Hubble 확인

```bash
# Hubble Relay 상태
kubectl get pods -n kube-system -l k8s-app=hubble-relay

# Hubble CLI로 플로우 관찰
hubble observe

# Hubble UI 접근 (포트 포워딩)
kubectl port-forward -n kube-system svc/hubble-ui 12000:80
# 브라우저에서 http://localhost:12000 접속
```

### 5.3. 메트릭 확인

```bash
# Prometheus 메트릭 엔드포인트
kubectl exec -n kube-system -l k8s-app=cilium -- \
  curl -s localhost:9962/metrics | head -50
```

---

## 6. 커스터마이징

### 6.1. 특정 설정만 오버라이드

```bash
# 설치 시 특정 값만 변경
helm install cilium cilium/cilium \
  -f cilium-values-lab.yaml \
  --set debug.enabled=true \
  --set hubble.ui.replicas=2 \
  -n kube-system
```

### 6.2. 새 values 파일 생성

기존 파일을 복사하여 환경에 맞게 수정:

```bash
cp cilium-values-lab.yaml cilium-values-custom.yaml
# 필요한 설정 수정 후 사용
```

---

## 7. 트러블슈팅

### 7.1. kube-proxy 대체 모드에서 서비스 접근 불가

```bash
# Cilium이 kube-proxy 역할을 하는지 확인
kubectl exec -n kube-system -l k8s-app=cilium -- \
  cilium service list

# BPF 맵 확인
kubectl exec -n kube-system -l k8s-app=cilium -- \
  cilium bpf lb list
```

### 7.2. k8sServiceHost 자동 탐지 실패

`auto` 설정이 동작하지 않으면 명시적으로 지정:

```yaml
k8sServiceHost: "192.168.10.100"
k8sServicePort: 6443
```

### 7.3. Native Routing 문제

```bash
# 라우팅 테이블 확인
ip route | grep cilium

# BPF 라우팅 확인
kubectl exec -n kube-system -l k8s-app=cilium -- \
  cilium bpf route list
```

---

## 8. 참고 자료

- [Cilium Helm Reference](https://docs.cilium.io/en/stable/helm-reference/)
- [kube-proxy Replacement](https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/)
- [Hubble Documentation](https://docs.cilium.io/en/stable/gettingstarted/hubble/)

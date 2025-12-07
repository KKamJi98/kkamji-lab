# 유틸리티 스크립트

Kubernetes 클러스터의 설치, 구성 및 관리를 자동화하는 헬퍼 스크립트 모음입니다.

---

## 1. 스크립트 목록

| 스크립트 | 용도 | 실행 위치 |
|----------|------|----------|
| `check-cilium-kernel-cfg.sh` | Cilium 커널 요구사항 검사 | 클러스터 노드 |
| `setup_cilium_kernel.sh` | 커널 모듈 자동 로드 | 클러스터 노드 |
| `rollout-restart-all.sh` | 전체 워크로드 재시작 | 로컬 또는 Master |
| `setup-kubecontext.sh` | 로컬 kubeconfig 설정 | 로컬 머신 |

---

## 2. 스크립트 상세

### 2.1. `check-cilium-kernel-cfg.sh`

Cilium이 정상 동작하기 위해 필요한 Linux 커널 설정을 검사합니다.

**검사 항목:**

- `CONFIG_BPF` - BPF 시스템 호출 지원
- `CONFIG_BPF_SYSCALL` - BPF 시스템 호출 활성화
- `CONFIG_NET_CLS_BPF` - BPF 기반 트래픽 분류
- `CONFIG_BPF_JIT` - BPF JIT 컴파일러
- `CONFIG_NET_CLS_ACT` - 트래픽 제어 액션
- `CONFIG_NET_SCH_INGRESS` - Ingress Qdisc
- `CONFIG_CRYPTO_SHA1` - SHA1 해시 (IPsec)
- `CONFIG_CRYPTO_USER_API_HASH` - 사용자 공간 해시 API

**사용법:**

```bash
# 클러스터 노드에서 실행
./check-cilium-kernel-cfg.sh

# 예상 출력:
# CONFIG_BPF: y (enabled)
# CONFIG_BPF_SYSCALL: y (enabled)
# CONFIG_NET_CLS_BPF: m (module)
# ...
```

**결과 해석:**

| 상태 | 의미 |
|------|------|
| `y` | 커널에 빌트인 (항상 사용 가능) |
| `m` | 모듈로 제공 (로드 필요할 수 있음) |
| `n` 또는 미존재 | 비활성화 (문제 발생 가능) |

---

### 2.2. `setup_cilium_kernel.sh`

`check-cilium-kernel-cfg.sh`의 확장 버전으로, 누락된 커널 모듈을 자동으로 로드합니다.

**기능:**

1. 커널 설정 검사
2. 모듈(`m`)로 제공되지만 로드되지 않은 항목 탐지
3. 사용자 확인 후 `modprobe`로 모듈 로드

**사용법:**

```bash
# 클러스터 노드에서 실행 (sudo 필요)
sudo ./setup_cilium_kernel.sh

# 예상 출력:
# Checking kernel configuration for Cilium...
# CONFIG_NET_CLS_BPF is available as module but not loaded.
# Load module cls_bpf? [y/N]: y
# Loading cls_bpf...
# Module loaded successfully.
```

**자동 로드 설정:**

로드한 모듈이 재부팅 후에도 유지되도록 하려면:

```bash
# /etc/modules-load.d/cilium.conf 파일 생성
echo "cls_bpf" | sudo tee -a /etc/modules-load.d/cilium.conf
```

---

### 2.3. `rollout-restart-all.sh`

클러스터의 모든 네임스페이스를 순회하며 Deployment, StatefulSet, DaemonSet 리소스를 롤아웃 재시작합니다.

**사용 시나리오:**

- CNI 변경 후 모든 Pod 재생성 필요
- ConfigMap/Secret 변경 후 전체 적용
- 네트워크 문제 해결을 위한 전체 재시작

**사용법:**

```bash
# Master 노드 또는 kubectl 접근 가능한 환경에서 실행
./rollout-restart-all.sh

# 예상 출력:
# Restarting deployments in namespace: default
#   deployment.apps/webpod restarted
# Restarting deployments in namespace: kube-system
#   deployment.apps/coredns restarted
# Restarting daemonsets in namespace: kube-system
#   daemonset.apps/cilium restarted
# ...
```

**스크립트 동작:**

```bash
# 내부 로직 (개념적)
for ns in $(kubectl get namespaces -o name); do
  kubectl rollout restart deployment -n $ns
  kubectl rollout restart statefulset -n $ns
  kubectl rollout restart daemonset -n $ns
done
```

**주의사항:**

- 프로덕션 환경에서는 신중하게 사용
- 대규모 클러스터에서는 시간이 오래 걸릴 수 있음
- 특정 네임스페이스만 재시작하려면 스크립트 수정 필요

---

### 2.4. `setup-kubecontext.sh`

Vagrant로 생성된 클러스터의 kubeconfig를 로컬 머신에 설정합니다.

**기능:**

1. `cilium-m1` Master 노드에서 `/etc/kubernetes/admin.conf` 복사
2. 로컬 `~/.kube/config`에 새 컨텍스트로 병합
3. 클러스터 이름과 컨텍스트 이름 설정

**사용법:**

```bash
# 로컬 머신에서 실행 (vagrant 디렉토리에서)
./setup-kubecontext.sh

# 예상 출력:
# Fetching kubeconfig from cilium-m1...
# Merging kubeconfig...
# Context 'cilium-cluster' added to ~/.kube/config
#
# Switch context with:
#   kubectl config use-context cilium-cluster
```

**사전 요구사항:**

- Vagrant VM이 실행 중이어야 함
- `vagrant ssh` 접근이 가능해야 함

**컨텍스트 관리:**

```bash
# 사용 가능한 컨텍스트 확인
kubectl config get-contexts

# 컨텍스트 전환
kubectl config use-context cilium-cluster

# 현재 컨텍스트 확인
kubectl config current-context
```

---

## 3. 권한 설정

스크립트 실행 전 실행 권한을 부여해야 합니다:

```bash
chmod +x *.sh
```

---

## 4. 트러블슈팅

### 4.1. 스크립트 실행 권한 오류

```bash
# Permission denied 오류 시
chmod +x script-name.sh
```

### 4.2. kubectl 연결 실패

```bash
# kubeconfig 확인
kubectl config view

# 클러스터 연결 테스트
kubectl cluster-info
```

### 4.3. 커널 모듈 로드 실패

```bash
# 모듈 존재 여부 확인
modinfo cls_bpf

# 수동 로드 시도
sudo modprobe cls_bpf

# 오류 로그 확인
dmesg | tail -20
```

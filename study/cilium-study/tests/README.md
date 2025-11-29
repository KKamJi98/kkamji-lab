# 테스트용 샘플 애플리케이션

Cilium CNI 설치 후 네트워크 연결성을 테스트하기 위한 샘플 애플리케이션입니다.

## 개요

이 테스트 환경은 다음을 검증합니다:

- Pod 간 통신 (Pod-to-Pod)
- 서비스 디스커버리 (Service Discovery)
- ClusterIP 서비스 라우팅
- Pod 안티-어피니티 (다른 노드에 분산 배치)

## 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│  Kubernetes Cluster                                             │
│                                                                  │
│  ┌──────────────┐                    ┌──────────────────────┐   │
│  │  curl-pod    │                    │  webpod Deployment   │   │
│  │  (netshoot)  │───── curl ────────▶│  (traefik/whoami)    │   │
│  │              │                    │                      │   │
│  │  Node: m1    │                    │  Replicas: 2         │   │
│  └──────────────┘                    │  (Anti-Affinity)     │   │
│                                      └──────────────────────┘   │
│                                                 │               │
│                                                 ▼               │
│                                      ┌──────────────────────┐   │
│                                      │  webpod Service      │   │
│                                      │  (ClusterIP)         │   │
│                                      │  Port: 80            │   │
│                                      └──────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 배포 매니페스트

### 1. 웹 애플리케이션 (webpod)

`traefik/whoami` 이미지를 사용하는 간단한 웹 서버입니다. 요청자의 정보를 응답으로 반환합니다.

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webpod
spec:
  replicas: 2
  selector:
    matchLabels:
      app: webpod
  template:
    metadata:
      labels:
        app: webpod
    spec:
      # Pod Anti-Affinity: 같은 노드에 배치되지 않도록 설정
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - sample-app
            topologyKey: "kubernetes.io/hostname"
      containers:
      - name: webpod
        image: traefik/whoami
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: webpod
  labels:
    app: webpod
spec:
  selector:
    app: webpod
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: ClusterIP
```

### 2. 테스트 클라이언트 (curl-pod)

네트워크 디버깅 도구가 포함된 `nicolaka/netshoot` 이미지를 사용합니다.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: curl-pod
  labels:
    app: curl
spec:
  nodeName: k8s-m1  # Master 노드에 고정 배치
  containers:
  - name: curl
    image: nicolaka/netshoot
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
```

## 사용 방법

### 1. 리소스 배포

```bash
# 방법 1: 직접 적용
cat << 'EOF' | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: webpod
spec:
  replicas: 2
  selector:
    matchLabels:
      app: webpod
  template:
    metadata:
      labels:
        app: webpod
    spec:
      affinity:
        podAntiAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
          - labelSelector:
              matchExpressions:
              - key: app
                operator: In
                values:
                - sample-app
            topologyKey: "kubernetes.io/hostname"
      containers:
      - name: webpod
        image: traefik/whoami
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: webpod
  labels:
    app: webpod
spec:
  selector:
    app: webpod
  ports:
  - protocol: TCP
    port: 80
    targetPort: 80
  type: ClusterIP
---
apiVersion: v1
kind: Pod
metadata:
  name: curl-pod
  labels:
    app: curl
spec:
  nodeName: k8s-m1
  containers:
  - name: curl
    image: nicolaka/netshoot
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
EOF
```

### 2. 배포 확인

```bash
# Pod 상태 확인
kubectl get pods -o wide

# 예상 출력:
# NAME                     READY   STATUS    RESTARTS   AGE   IP           NODE
# curl-pod                 1/1     Running   0          30s   10.10.0.5    k8s-m1
# webpod-xxxxx-yyyyy       1/1     Running   0          30s   10.10.1.10   k8s-w1
# webpod-xxxxx-zzzzz       1/1     Running   0          30s   10.10.2.15   k8s-w2

# 서비스 확인
kubectl get svc webpod

# 예상 출력:
# NAME     TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
# webpod   ClusterIP   10.200.100.50   <none>        80/TCP    30s
```

### 3. 연결 테스트

```bash
# 서비스 이름으로 접근 (DNS 기반)
kubectl exec -it curl-pod -- curl webpod

# ClusterIP로 접근
kubectl exec -it curl-pod -- curl 10.200.100.50

# Pod IP로 직접 접근
kubectl exec -it curl-pod -- curl 10.10.1.10

# 여러 번 요청하여 로드밸런싱 확인
for i in {1..5}; do
  kubectl exec curl-pod -- curl -s webpod | grep Hostname
done
```

### 4. 예상 응답

```
Hostname: webpod-xxxxx-yyyyy
IP: 127.0.0.1
IP: 10.10.1.10
RemoteAddr: 10.10.0.5:54321
GET / HTTP/1.1
Host: webpod
User-Agent: curl/8.1.2
Accept: */*
```

## 추가 네트워크 테스트

### DNS 해석 테스트

```bash
# 서비스 DNS 조회
kubectl exec curl-pod -- nslookup webpod

# 전체 FQDN으로 조회
kubectl exec curl-pod -- nslookup webpod.default.svc.cluster.local
```

### 네트워크 경로 확인

```bash
# traceroute
kubectl exec curl-pod -- traceroute webpod

# MTR (더 상세한 경로 분석)
kubectl exec curl-pod -- mtr -r -c 5 webpod
```

### TCP 연결 테스트

```bash
# netcat으로 포트 연결 확인
kubectl exec curl-pod -- nc -zv webpod 80
```

## Cilium 관측성 (Hubble 활성화 시)

```bash
# Hubble CLI로 트래픽 관찰
hubble observe --from-pod default/curl-pod

# 특정 서비스로의 트래픽만 필터링
hubble observe --to-service default/webpod
```

## 리소스 정리

```bash
# 테스트 리소스 삭제
kubectl delete deployment webpod
kubectl delete service webpod
kubectl delete pod curl-pod
```

## 트러블슈팅

### curl이 실패하는 경우

```bash
# CNI 상태 확인
kubectl get pods -n kube-system -l k8s-app=cilium

# DNS 정상 동작 확인
kubectl exec curl-pod -- nslookup kubernetes

# Cilium 상태 확인
kubectl exec -n kube-system -l k8s-app=cilium -- cilium status
```

### Pod가 Pending 상태인 경우

```bash
# 이벤트 확인
kubectl describe pod curl-pod

# 노드 리소스 확인
kubectl describe node k8s-m1
```

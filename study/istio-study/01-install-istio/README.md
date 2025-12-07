# Istio Install Guide (Mac)

## Makefile 기반 실행 (추천)

- Init 모드 설치: `make istio-install-init`
- CNI 모드 설치: `make istio-install-cni` (`ISTIO_OVERLAY_CNI=./istio-cni.yaml` 기본값 사용)
- 설치 검증: `make istio-verify`
- 삭제: `make istio-uninstall` (CRD까지 삭제하려면 `ISTIO_PURGE=true make istio-uninstall`)
- 모니터링 스택(kube-prometheus-stack + Kiali): `make monitoring-install` / `make monitoring-delete`
- 기본 컨텍스트는 `KUBE_CONTEXT=rancher-desktop`이며, 필요하면 환경변수로 덮어쓸 수 있습니다.

[KubeOps - [이스티오(Istio) 시작하기] Istio 설치하기](https://cafe.naver.com/kubeops/821)
[Istio Docs - Getting Started](https://istio.io/latest/docs/setup/getting-started/)
[Istio GitHub](https://github.com/istio/istio)

![Istio Install](img/01_install_istio.png)

---

## 1. Istio Install

```shell
##############################################################
# Istio 패키지 다운로드 -> brew install istioctl로 대체
##############################################################
brew install istioctl

##############################################################
# Istio 설치 (Istio-init 방식)
##############################################################
istioctl install --set profile=default -y \
  --set values.pilot.resources.requests.cpu=250m \
  --set values.pilot.resources.requests.memory=512Mi

# * profile
# - default : 실무용 기본 구성 [Istiod, Gateway 설치, 사이드카 자동 주입]
# - demo : 학습/테스트 목적 [Istiod, Gateway 설치, 사이드카 자동 주입, Prometheus, Grafana, Kiali 등 설치가능)
# - minimal : Istio의 특정 기능만 사용하기 위한 목적 [Istiod]

##############################################################
# istio-system에 생성된 리소스 확인
##############################################################
kubectl get deployments -n istio-system
# NAME                                    READY   STATUS    RESTARTS   AGE
# istio-ingressgateway-846cf58fd4-hclfr   1/1     Running   0          55s
# istiod-5478f484df-4gb2m                 1/1     Running   0          77s
kubectl get crd | grep istio
# authorizationpolicies.security.istio.io    2025-12-06T13:41:06Z
# destinationrules.networking.istio.io       2025-12-06T13:41:06Z
# envoyfilters.networking.istio.io           2025-12-06T13:41:06Z
# gateways.networking.istio.io               2025-12-06T13:41:06Z
# peerauthentications.security.istio.io      2025-12-06T13:41:06Z
# proxyconfigs.networking.istio.io           2025-12-06T13:41:06Z
# requestauthentications.security.istio.io   2025-12-06T13:41:06Z
# serviceentries.networking.istio.io         2025-12-06T13:41:06Z
# sidecars.networking.istio.io               2025-12-06T13:41:06Z
# telemetries.telemetry.istio.io             2025-12-06T13:41:06Z
# virtualservices.networking.istio.io        2025-12-06T13:41:06Z
# wasmplugins.extensions.istio.io            2025-12-06T13:41:06Z
# workloadentries.networking.istio.io        2025-12-06T13:41:06Z
# workloadgroups.networking.istio.io         2025-12-06T13:41:06Z
```

---

## 2. Demo Application Deploy

![Demo App Deploy](img/02_demo_app_deploy.png)

```shell
##############################################################
# BookStore App 배포 (Istio sidecar 자동 주입 미적용)
##############################################################
kubectl apply -f bookstore-app/bookinfo.yaml -n default

##############################################################
# BookStore App 배포 (Istio sidecar 자동 주입 미적용)
##############################################################
kubectl get pods -n default
# NAME                              READY   STATUS              RESTARTS   AGE
# details-v1-766844796b-h8bn4       1/1     Running             0          2m18s
# productpage-v1-54bb874995-pvhw2   1/1     Running             0          2m18s
# ratings-v1-5dc79b6bcd-jkqmv       1/1     Running             0          2m18s
# reviews-v1-598b896c9d-l8rds       1/1     Running             0          2m18s
# reviews-v2-556d6457d-x9xbf        1/1     Running             0          2m18s
# reviews-v3-564544b4d6-ghk4v       1/1     Running             0          2m18s

##############################################################
# BookStore App 제거
##############################################################
kubectl delete -f bookstore-app/bookinfo.yaml -n default

##############################################################
# default 네임스페이스에 만들어지는 Pod에 sidecar proxy가 자동으로 주입 되도록 설정
##############################################################
kubectl label namespace default istio-injection=enabled

##############################################################
# 확인
##############################################################
kubectl get ns default --show-labels

##############################################################
# BookStore App 배포 (Istio sidecar 자동 주입 적용)
##############################################################
kubectl apply -f bookstore-app/bookinfo.yaml -n default
##############################################################
# 리소스 확인
##############################################################
kubectl get services
kubectl get pods
# NAME                              READY   STATUS    RESTARTS   AGE
# details-v1-766844796b-7zf28       2/2     Running   0          2m58s
# productpage-v1-54bb874995-7g5t6   2/2     Running   0          2m58s
# ratings-v1-5dc79b6bcd-c8mmg       2/2     Running   0          2m58s
# reviews-v1-598b896c9d-8mgh6       2/2     Running   0          2m58s
# reviews-v2-556d6457d-76lhl        2/2     Running   0          2m58s
# reviews-v3-564544b4d6-zqwnn       2/2     Running   0          2m58s

##############################################################
# Pod 내부 컨테이너 확인 (main, sidecar, init)
##############################################################
kubectl get pod details-v1-<tab> -o yaml
# ❯ kubectl describe po details-v1-766844796b-7zf28
# Init Containers:
#   istio-init:
# ...
#   istio-proxy:
# ...

##############################################################
# Application 응답 결과 확인
##############################################################
kubectl exec "$(kubectl get pod -l app=ratings -o jsonpath='{.items[0].metadata.name}')" -c ratings -- curl -sS productpage:9080/productpage | grep -o "<title>.*</title>"
# <title>Simple Bookstore App</title>
```

---

## 3. Gateway 구성 및 Web UI 접속

![Gateway 구성 및 Web UI 접속](img/03_gateway_web_ui.png)

### 3.1. Istio API

```shell
##############################################################
# Gateway, VirtualService 배포
##############################################################
kubectl apply -f istio-api/bookinfo-gateway.yaml -n default

##############################################################
# 리소스 확인
##############################################################
kubectl get gateways.networking.istio.io -o yaml | kubectl neat
kubectl get virtualservices.networking.istio.io -o yaml | kubectl neat
##############################################################
# Service에서 NodePort 수정
##############################################################
kubectl edit svc istio-ingressgateway -n istio-system
# ...
  ports:
  - name: http2
    nodePort: 30010  # 이렇게 수정 후 저장
    port: 80
    protocol: TCP
    targetPort: 8080
```

### 3.2. Gateway API

```shell
##############################################################
# Kubernetes Gateway API CRDs 설치
##############################################################
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.1/standard-install.yaml

##############################################################
# 리소스 확인
##############################################################
kubectl get gatewayclass
# NAME           CONTROLLER                    ACCEPTED   AGE
# istio          istio.io/gateway-controller   True       6m3s
# istio-remote   istio.io/unmanaged-gateway    True       6m3s
kubectl get crd | grep gateway
# backendtlspolicies.gateway.networking.k8s.io   2025-12-06T20:04:36Z
# gatewayclasses.gateway.networking.k8s.io       2025-12-06T20:03:37Z
# gateways.gateway.networking.k8s.io             2025-12-06T20:03:37Z
# gateways.networking.istio.io                   2025-12-06T19:52:22Z
# grpcroutes.gateway.networking.k8s.io           2025-12-06T20:03:37Z
# httproutes.gateway.networking.k8s.io           2025-12-06T20:03:37Z
# referencegrants.gateway.networking.k8s.io      2025-12-06T20:03:37Z

##############################################################
# Gateway, HTTPRoute 배포
##############################################################
kubectl apply -f gateway-api/bookinfo-gateway.yaml -n default

##############################################################
# 리소스 확인
##############################################################
kubectl get gateways.gateway.networking.k8s.io -n default -o yaml | kubectl neat
# apiVersion: v1
# items:
# - apiVersion: gateway.networking.k8s.io/v1
#   kind: Gateway
#   metadata:
#     name: bookinfo-gateway
#     namespace: default
#   spec:
#     gatewayClassName: istio
#     listeners:
#     - allowedRoutes:
#         namespaces:
#           from: Same
#       name: http
#       port: 80
#       protocol: HTTP
# kind: List
# metadata: {}

kubectl get httproutes.gateway.networking.k8s.io -n default -o yaml | kubectl neat
# apiVersion: v1
# items:
# - apiVersion: gateway.networking.k8s.io/v1
#   kind: HTTPRoute
#   metadata:
#     name: bookinfo
#     namespace: default
#   spec:
#     parentRefs:
#     - group: gateway.networking.k8s.io
#       kind: Gateway
#       name: bookinfo-gateway
#     rules:
#     - backendRefs:
#       - group: ""
#         kind: Service
#         name: productpage
#         port: 9080
#         weight: 1
#       matches:
#       - path:
#           type: Exact
#           value: /productpage
#       - path:
#           type: PathPrefix
#           value: /static
#       - path:
#           type: Exact
#           value: /login
#       - path:
#           type: Exact
#           value: /logout
#       - path:
#           type: PathPrefix
#           value: /api/v1/products
# kind: List
# metadata: {}

##############################################################
# Gateway Pod 확인
##############################################################
kubectl get pod -n default

# Service에서 NodePort 수정
kubectl edit svc bookinfo-gateway-istio -n default
# ...
# ports:
# - appProtocol: http
#   name: http
#   nodePort: 30020  # 이렇게 수정 후 저장
#   port: 80
#   protocol: TCP
#   targetPort: 80
```

### 3.3. Web UI 접속

```shell
kubectl get nodes -o wide
# NAME                   STATUS   ROLES                  AGE   VERSION        INTERNAL-IP    EXTERNAL-IP    OS-IMAGE             KERNEL-VERSION   CONTAINER-RUNTIME
# lima-rancher-desktop   Ready    control-plane,master   47m   v1.33.6+k3s1   192.168.5.15   192.168.64.2   Alpine Linux v3.22   6.6.116-0-virt   docker://28.3.3
# Istio API
open http://192.168.64.2:30010/productpage

# Gateway API
open http://192.168.64.2:30020/productpage
```

![Book Info Web](img/04_book_info_web.png)

---

## 4. Kiali 대시보드 설치 및 Prometheus 연동

- [Istio Docs - kiali Install](https://istio.io/latest/docs/ops/integrations/kiali/)
- [Kiali Docs](https://kiali.io/docs/)

| Name       | NodePort |
| ---------- | -------- |
| grafana    | 30000    |
| prometheus | 30001    |
| kiali      | 30002    |

### 4.1. Prometheus & Grafana 설치

```shell
##############################################################
# Kube-Prometheus-Stack 설치
##############################################################
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
helm upgrade -i monitoring -n monitoring prometheus-community/kube-prometheus-stack -f ./kube-prometheus-stack/kkamji_values.yaml --version 79.12.0 --create-namespace

##############################################################
# 접속 확인
##############################################################
open http://192.168.64.2:30000
open http://192.168.64.2:30001
```

### 4.2. Kiali 설치

```shell
##############################################################
# Kiali 배포
##############################################################
kubectl apply -f kiali/kiali.yaml

##############################################################
# Kiali 리소스 확인
##############################################################
kubectl get pod -n istio-system
kubectl get svc -n istio-system kiali
kubectl get cm -n istio-system kiali
```

### 4.3. Istiod, Sidecar(envoy proxy) Metrics 수집을 위한 ServiceMonitor, PodMonitor 설정

```shell
kubectl apply -f monitor/istiod-servicemonitor.yaml
kubectl apply -f monitor/podmonitor.yaml
```

### 4.4. Prometheus에서 Istio Metrics 확인

```shell
open http://192.168.64.2:30001/targets
```

![Prometheus Targets](img/05_prometheus-targets.png)

### 4.5. Kiali 접속 및 트래픽 확인

```shell
##############################################################
# Demo Application에 트래픽 발생
##############################################################
for i in {1..100}; do
  PORT=$(( i % 2 == 0 ? 30020 : 30010 ))

  echo "[$i] Request → Port: $PORT"
  curl -s -o /dev/null -w "%{http_code}\n" \
       "http://192.168.64.2:$PORT/productpage"

  sleep 0.1
done

##############################################################
# Kiali 접속
##############################################################
open http://192.168.64.2:30002
```

![Kiali Dashboard](img/06_kiali_dashboard.png)

## Istio CNI 방식 적용

![Istio CNI](img/07_istio_cni.png)

### 1. Istio init 방식 확인 (initContainer - istio-init)

아래와 같이 securityContext에서 노드의 IP Tables 설정을 위해 NET_ADMIN, NET_RAW 권한이 부여되고, root User로 실행되는 것을 확인할 수 있습니다.

보안이 중요시되는 환경에서는 해당 권한을 사용하는 것에 대한 제약사항이 있을 수 있기 때문에 CNI 방식을 적용할 수 있습니다.

```yaml
initContainers:
- args: ..
  image: docker.io/istio/proxyv2:1.26.1
  imagePullPolicy: IfNotPresent
  name: istio-init
  securityContext:
	allowPrivilegeEscalation: false
	capabilities:  
	  add:
		- NET_ADMIN  # 네트워크와 raw 소켓 제어 권한
		- NET_RAW
	  drop:
		- ALL
	privileged: false
	readOnlyRootFilesystem: false # 파일 쓰기 가능
	runAsGroup: 0
	runAsNonRoot: false  # root 유저로 실행
	runAsUser: 0  # root 유저로 실행
```

### 2. Istio CNI 방식 적용

[Istio Docs - Install the Istio CNI node agent](https://istio.io/latest/docs/setup/additional-setup/cni/)

```shell
##############################################################
# Demo Application 제거
##############################################################
kubectl delete -f bookstore-app/bookinfo.yaml -n default

##############################################################
# Istio 설치 (CNI 방식)
##############################################################
cat <<EOF > istio-cni.yaml
apiVersion: install.istio.io/v1alpha1
kind: IstioOperator
spec:
  components:
    cni:
      namespace: istio-system
      enabled: true
EOF

istioctl install -f istio-cni.yaml -y

##############################################################
# CNI node agents 확인
##############################################################
kubectl get pod -n istio-system
# NAME                                    READY   STATUS    RESTARTS   AGE
# istio-cni-node-4lp72                    1/1     Running   0          68s
# istio-ingressgateway-846cf58fd4-gw5b7   1/1     Running   0          9h
# istiod-7fbc4dd9c9-92njf                 1/1     Running   0          68s
# kiali-54d6cf4c4d-r44r5                  1/1     Running   0          8h

##############################################################
# Demo Application 생성
##############################################################
kubectl apply -f bookstore-app/bookinfo.yaml -n default

##############################################################
# Pod 내부 컨테이너 확인 (main, sidecar, init)
##############################################################
kubectl get po details-v1-766844796b-sgdkh -o yaml | kubectl neat
# initContainers:
# - args: ...
#   image: docker.io/istio/proxyv2:1.26.1
#   imagePullPolicy: IfNotPresent
#   name: istio-validation  # 이름 확인 (설정 유효성 검증)
#   securityContext:
#     allowPrivilegeEscalation: false
#     capabilities:  
#       drop:
#         - ALL
#     privileged: false  
#     readOnlyRootFilesystem: true   # 파일 읽기 모드
#     runAsGroup: 1337
#     runAsNonRoot: true    # 비 root 유저로 실행
#     runAsUser: 1337  # 일반 유저로 실행
```

## 5. Istio 전체 삭제 (Istio 설치에 문제가 생긴 경우)

```shell
##############################################################
# Demo Application 및 Istio Gateway 리소스 삭제 (Istio API)
##############################################################
kubectl delete -f bookstore-app/bookinfo.yaml -n default
kubectl delete -f istio-api/bookinfo-gateway.yaml -n default

##############################################################
# Gateway API 리소스 및 CRD 삭제
##############################################################
kubectl delete -f gateway-api/bookinfo-gateway.yaml -n default
kubectl delete -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.4.1/standard-install.yaml

##############################################################
# 모니터링 스택 삭제
##############################################################
kubectl delete -f monitor/istiod-servicemonitor.yaml -n monitoring
kubectl delete -f monitor/podmonitor.yaml -n monitoring
helm uninstall monitoring -n monitoring

##############################################################
# Kiali 삭제
##############################################################
kubectl delete -f kiali/kiali.yaml -n istio-system

##############################################################
# Istio 삭제
##############################################################
istioctl uninstall -y --purge
kubectl delete namespace istio-system
kubectl label namespace default istio-injection-
```

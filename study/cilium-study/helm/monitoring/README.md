# 모니터링 Helm Values

Kubernetes 클러스터 모니터링을 위한 Helm 차트 `values.yaml` 파일을 저장하기 위한 공간입니다.

## 개요

이 디렉토리는 Cilium 클러스터의 관측성을 강화하기 위한 모니터링 스택 설정을 위해 예약되어 있습니다.

## 예정된 구성 요소

### Prometheus Stack

전체 모니터링 스택을 한 번에 설치할 수 있는 `kube-prometheus-stack` 사용 예정:

| 구성 요소 | 역할 |
|----------|------|
| **Prometheus** | 메트릭 수집 및 저장 |
| **Grafana** | 대시보드 및 시각화 |
| **Alertmanager** | 알림 관리 |
| **Node Exporter** | 노드 메트릭 수집 |
| **kube-state-metrics** | Kubernetes 리소스 상태 메트릭 |

### Cilium 메트릭 연동

Cilium은 Prometheus 형식의 메트릭을 기본 제공합니다:

```yaml
# cilium-values.yaml에서 활성화
prometheus:
  enabled: true

hubble:
  metrics:
    enabled:
      - dns
      - drop
      - tcp
      - flow
```

## 설치 가이드 (향후 적용)

### 1. Helm 리포지토리 추가

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
```

### 2. Prometheus Stack 설치

```bash
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  -f prometheus-values.yaml
```

### 3. Cilium Grafana 대시보드 추가

```bash
# Cilium 공식 대시보드 ID
# - Cilium Metrics: 15513
# - Hubble Dashboard: 15514

# Grafana에서 Import Dashboard로 추가
```

## 권장 대시보드

### Cilium 대시보드

| 대시보드 | ID | 용도 |
|----------|-----|------|
| Cilium Metrics | 15513 | Cilium 에이전트 성능 |
| Cilium Operator | 15514 | Operator 상태 |
| Hubble | 15515 | 네트워크 플로우 |

### 일반 Kubernetes 대시보드

| 대시보드 | ID | 용도 |
|----------|-----|------|
| Kubernetes Cluster | 7249 | 클러스터 전체 현황 |
| Node Exporter | 1860 | 노드 리소스 상세 |
| Pod Metrics | 6417 | Pod 레벨 메트릭 |

## 알림 규칙 (예정)

### Cilium 관련 알림

```yaml
# prometheus-rules.yaml (예시)
groups:
  - name: cilium
    rules:
      - alert: CiliumAgentDown
        expr: up{job="cilium-agent"} == 0
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Cilium Agent is down"

      - alert: CiliumEndpointNotReady
        expr: cilium_endpoint_state{endpoint_state!="ready"} > 0
        for: 10m
        labels:
          severity: warning
```

## 리소스 요구사항

| 구성 요소 | CPU Request | Memory Request |
|----------|-------------|----------------|
| Prometheus | 100m | 512Mi |
| Grafana | 100m | 256Mi |
| Alertmanager | 10m | 64Mi |

실습 환경에서는 리소스 요청을 낮추는 것을 권장합니다.

## 접근 방법

### Grafana 접근

```bash
# 포트 포워딩
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80

# 브라우저에서 http://localhost:3000 접속
# 기본 계정: admin / prom-operator
```

### Prometheus 접근

```bash
# 포트 포워딩
kubectl port-forward -n monitoring svc/prometheus-kube-prometheus-prometheus 9090:9090

# 브라우저에서 http://localhost:9090 접속
```

## 다음 단계

1. `prometheus-values.yaml` 파일 작성
2. Cilium ServiceMonitor 구성
3. Grafana 대시보드 프로비저닝
4. 알림 규칙 설정

## 참고 자료

- [kube-prometheus-stack Chart](https://artifacthub.io/packages/helm/prometheus-community/kube-prometheus-stack)
- [Cilium Monitoring](https://docs.cilium.io/en/stable/observability/metrics/)
- [Grafana Dashboard Gallery](https://grafana.com/grafana/dashboards/)

# CloudNet@ CI/CD Study - ArgoCD 심화

`CloudNet@` 커뮤니티 CI/CD 스터디 6주차 ArgoCD 심화 학습 자료입니다.

---

## 1. 학습 목표

- ArgoCD 고급 기능 활용
- ApplicationSet을 통한 멀티 환경 배포
- Argo Rollouts를 활용한 Progressive Delivery
- 실무 적용 가능한 GitOps 파이프라인 구성

---

## 2. 주요 학습 내용

### 2.1. ApplicationSet

여러 Application을 자동으로 생성하고 관리합니다.

**Generator 종류:**

| Generator | 용도 |
|-----------|------|
| `list` | 정적 목록에서 Application 생성 |
| `cluster` | 등록된 클러스터마다 Application 생성 |
| `git` | Git 저장소 디렉토리/파일 기반 생성 |
| `matrix` | 여러 Generator 조합 |
| `merge` | Generator 결과 병합 |

**예제: 멀티 환경 배포**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: myapp-environments
  namespace: argocd
spec:
  generators:
  - list:
      elements:
      - env: dev
        namespace: myapp-dev
        values_file: values-dev.yaml
      - env: staging
        namespace: myapp-staging
        values_file: values-staging.yaml
      - env: prod
        namespace: myapp-prod
        values_file: values-prod.yaml
  template:
    metadata:
      name: 'myapp-{{env}}'
    spec:
      project: default
      source:
        repoURL: https://github.com/myorg/myapp.git
        targetRevision: HEAD
        path: helm/myapp
        helm:
          valueFiles:
          - '{{values_file}}'
      destination:
        server: https://kubernetes.default.svc
        namespace: '{{namespace}}'
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
```

### 2.2. Sync Waves와 Hooks

배포 순서를 제어하고 전/후 작업을 수행합니다.

**Sync Waves:**

```yaml
# 숫자가 낮을수록 먼저 배포 (기본값: 0)
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "-1"  # 가장 먼저
---
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "0"   # 기본
---
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"   # 마지막
```

**Hooks:**

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  name: db-migration
  annotations:
    argocd.argoproj.io/hook: PreSync
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
spec:
  template:
    spec:
      containers:
      - name: migration
        image: myapp/migration:latest
        command: ["./migrate.sh"]
      restartPolicy: Never
```

| Hook | 실행 시점 |
|------|----------|
| `PreSync` | 동기화 전 |
| `Sync` | 동기화 중 (일반 리소스와 함께) |
| `PostSync` | 동기화 성공 후 |
| `SyncFail` | 동기화 실패 시 |
| `Skip` | 동기화에서 제외 |

### 2.3. Argo Rollouts 연동

Progressive Delivery를 위한 고급 배포 전략입니다.

**Canary 배포:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp
spec:
  replicas: 10
  strategy:
    canary:
      steps:
      - setWeight: 10        # 10% 트래픽
      - pause: {duration: 1h} # 1시간 대기
      - setWeight: 30        # 30% 트래픽
      - pause: {duration: 1h}
      - setWeight: 50        # 50% 트래픽
      - pause: {}            # 수동 승인 대기
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: myapp
        image: myapp:v2
```

**Blue-Green 배포:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: myapp
spec:
  replicas: 5
  strategy:
    blueGreen:
      activeService: myapp-active
      previewService: myapp-preview
      autoPromotionEnabled: false  # 수동 승인
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      containers:
      - name: myapp
        image: myapp:v2
```

### 2.4. 멀티 클러스터 배포

**클러스터 등록:**

```bash
# 외부 클러스터 등록
argocd cluster add <context-name> --name prod-cluster

# 클러스터 목록 확인
argocd cluster list

# 클러스터 삭제
argocd cluster rm prod-cluster
```

**ApplicationSet으로 멀티 클러스터 배포:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: myapp-multicluster
spec:
  generators:
  - clusters:
      selector:
        matchLabels:
          env: production
  template:
    metadata:
      name: 'myapp-{{name}}'
    spec:
      source:
        repoURL: https://github.com/myorg/myapp.git
        path: manifests
      destination:
        server: '{{server}}'
        namespace: myapp
```

### 2.5. 보안 및 RBAC

**Project 기반 권한 분리:**

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: team-a
  namespace: argocd
spec:
  description: Team A applications
  sourceRepos:
  - https://github.com/myorg/team-a-*
  destinations:
  - namespace: team-a-*
    server: https://kubernetes.default.svc
  clusterResourceWhitelist:
  - group: ''
    kind: Namespace
  namespaceResourceWhitelist:
  - group: '*'
    kind: '*'
```

**RBAC 정책:**

```yaml
# argocd-rbac-cm ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-rbac-cm
  namespace: argocd
data:
  policy.csv: |
    p, role:team-a, applications, *, team-a/*, allow
    p, role:team-a, logs, get, team-a/*, allow
    g, team-a-group, role:team-a
```

---

## 3. 실습 환경 구성

### 3.1. Argo Rollouts 설치

```bash
# Argo Rollouts 설치
kubectl create namespace argo-rollouts
kubectl apply -n argo-rollouts -f https://github.com/argoproj/argo-rollouts/releases/latest/download/install.yaml

# kubectl 플러그인 설치
brew install argoproj/tap/kubectl-argo-rollouts

# 상태 확인
kubectl argo rollouts list rollouts
```

### 3.2. 대시보드 접근

```bash
# ArgoCD UI
kubectl port-forward svc/argocd-server -n argocd 8080:443

# Argo Rollouts Dashboard
kubectl argo rollouts dashboard &
# http://localhost:3100 접속
```

---

## 4. 베스트 프랙티스

### 4.1. 저장소 구조

```
gitops-repo/
├── apps/                    # Application 정의
│   ├── dev/
│   ├── staging/
│   └── prod/
├── base/                    # 공통 매니페스트
├── overlays/                # 환경별 오버레이
│   ├── dev/
│   ├── staging/
│   └── prod/
└── applicationsets/         # ApplicationSet 정의
```

### 4.2. 네이밍 컨벤션

- Application: `{app-name}-{environment}`
- Namespace: `{app-name}-{environment}`
- Project: `{team-name}`

### 4.3. 동기화 정책

| 환경 | 자동 동기화 | Prune | SelfHeal |
|------|-----------|-------|----------|
| Dev | O | O | O |
| Staging | O | O | X |
| Prod | X | X | X |

---

## 5. 참고 자료

- [ArgoCD ApplicationSet](https://argo-cd.readthedocs.io/en/stable/user-guide/application-set/)
- [Argo Rollouts](https://argoproj.github.io/argo-rollouts/)
- [GitOps Best Practices](https://argo-cd.readthedocs.io/en/stable/user-guide/best_practices/)

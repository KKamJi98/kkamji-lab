# CI/CD Study - Season 1 (ArgoCD)

`CloudNet@` 커뮤니티의 Gasida님이 진행하신 CI/CD 스터디 1기 학습 자료입니다.

GitOps 원칙을 기반으로 한 CI/CD 파이프라인 구축을 학습하며, **ArgoCD**를 중심으로 Kubernetes 환경에서의 선언적 배포 관리를 실습합니다.

## GitOps란?

**GitOps**는 Git을 단일 진실 공급원(Single Source of Truth)으로 사용하여 인프라와 애플리케이션을 관리하는 방법론입니다.

### 핵심 원칙

| 원칙 | 설명 |
|------|------|
| **선언적 구성** | 시스템의 원하는 상태를 선언적으로 정의 |
| **Git 기반 버전 관리** | 모든 변경사항을 Git으로 추적 |
| **자동 동기화** | Git 상태와 클러스터 상태를 자동으로 동기화 |
| **지속적 조정** | 실제 상태가 원하는 상태와 다르면 자동 복구 |

### 전통적 CI/CD vs GitOps

```
[전통적 CI/CD - Push 모델]
                                         ┌─────────────┐
┌──────┐    ┌────────┐    ┌────────┐    │ Kubernetes  │
│ Git  │───▶│   CI   │───▶│   CD   │───▶│   Cluster   │
└──────┘    └────────┘    └────────┘    └─────────────┘
                              │
                         kubectl apply
                         (외부에서 Push)


[GitOps - Pull 모델]
                                         ┌─────────────┐
┌──────┐    ┌────────┐                  │ Kubernetes  │
│ Git  │───▶│   CI   │                  │   Cluster   │
└──────┘    └────────┘                  │  ┌───────┐  │
     │                                  │  │ArgoCD │  │
     └──────────────────────────────────│──│ Agent │  │
                                        │  └───────┘  │
                 Git 상태를 Poll하여     └─────────────┘
                 자동으로 동기화
```

## 프로젝트 구조

```
ci-cd-study/
├── 1w-gitops-image-build/              # 1주차: 컨테이너 이미지 빌드
│   ├── README.md                       # 실습 가이드
│   ├── practice.md                     # 상세 명령어 모음
│   └── chapters/                       # GitOps Cookbook 실습
│       ├── ch03/                       # 3장: 애플리케이션 배포
│       │   ├── nodejs-app/
│       │   ├── python-app/
│       │   └── spring-boot-app/
│       └── ch06/                       # 6장: RBAC 설정
│
├── 4w-1-of-3-argo-cd/                  # 4주차: ArgoCD 실습
│   └── ArgoCD-in-Practice/             # "Argo CD in Practice" 예제
│       └── ch02/                       # 2장 실습 코드
│
├── 6w-3-of-3-argocd/                   # 6주차: ArgoCD 심화
│   └── cicd-study/                     # 심화 실습 자료
│
└── README.md                           # 본 파일
```

## 주차별 학습 내용

### 1주차: 컨테이너 이미지 빌드 및 로컬 환경 구성

**학습 목표:**

- Docker를 활용한 컨테이너 이미지 빌드 실습
- kind를 사용한 로컬 Kubernetes 클러스터 구축
- 다양한 언어(Python, Node.js, Java) 애플리케이션 컨테이너화

**주요 내용:**

```bash
# kind 클러스터 생성
kind create cluster --name myk8s --image kindest/node:v1.32.8

# Docker 이미지 빌드
docker build -t myapp:latest .

# Docker Hub 푸시
docker push myregistry/myapp:latest
```

[1주차 상세 가이드](./1w-gitops-image-build/README.md)

### 2-3주차: GitOps 원칙 및 도구 소개

**학습 목표:**

- GitOps의 핵심 원칙 이해
- ArgoCD vs Flux 비교
- 선언적 배포의 장점

### 4주차: ArgoCD 기초

**학습 목표:**

- ArgoCD 설치 및 구성
- Application CRD 이해
- Git 저장소 연동

**ArgoCD 아키텍처:**

```
┌─────────────────────────────────────────────────────────────────┐
│  ArgoCD Architecture                                            │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  ArgoCD Server (API + UI)                                 │  │
│  │  - REST API 제공                                          │  │
│  │  - 웹 UI 제공                                             │  │
│  │  - RBAC 처리                                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Application Controller                                   │  │
│  │  - Git 저장소 모니터링                                     │  │
│  │  - 실제 상태 vs 원하는 상태 비교                           │  │
│  │  - 동기화 수행                                            │  │
│  └──────────────────────────────────────────────────────────┘  │
│                              │                                   │
│                              ▼                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Repo Server                                              │  │
│  │  - Git 저장소 캐싱                                        │  │
│  │  - Helm/Kustomize 렌더링                                  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

[4주차 상세 가이드](./4w-1-of-3-argo-cd/ArgoCD-in-Practice/README.md)

### 5-6주차: ArgoCD 심화

**학습 목표:**

- Sync Waves와 Hooks
- ApplicationSet 활용
- 멀티 클러스터 배포
- Progressive Delivery (Argo Rollouts 연동)

## 참고 도서

### GitOps Cookbook

<img src="https://static.packt-cdn.com/products/9781801072360/cover/smaller" alt="GitOps Cookbook" height="200px">

**"GitOps Cookbook"** (Packt Publishing)

- 실용적인 GitOps 레시피 모음
- ArgoCD, Flux 활용법
- Kubernetes 배포 자동화

### Argo CD in Practice

<img src="https://static.packt-cdn.com/products/9781803233321/cover/smaller" alt="Argo CD in Practice" height="200px">

**"Argo CD in Practice"** (Packt Publishing)

- ArgoCD 심층 분석
- 프로덕션 환경 운영 노하우
- 고급 기능 활용법

## 실습 환경 요구사항

| 도구 | 용도 | 설치 (macOS) |
|------|------|--------------|
| Docker | 컨테이너 빌드 | `brew install --cask docker` |
| kind | 로컬 K8s 클러스터 | `brew install kind` |
| kubectl | K8s CLI | `brew install kubernetes-cli` |
| Helm | 패키지 관리자 | `brew install helm` |
| argocd | ArgoCD CLI | `brew install argocd` |

## 빠른 시작

### 1. kind 클러스터 생성

```bash
# 포트 매핑이 포함된 클러스터 생성
kind create cluster --name argocd-lab --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30080
    hostPort: 30080
  - containerPort: 30443
    hostPort: 30443
EOF
```

### 2. ArgoCD 설치

```bash
# 네임스페이스 생성
kubectl create namespace argocd

# ArgoCD 설치
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# 초기 비밀번호 확인
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath="{.data.password}" | base64 -d

# 포트 포워딩
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

### 3. 첫 번째 Application 배포

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: guestbook
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/argoproj/argocd-example-apps.git
    targetRevision: HEAD
    path: guestbook
  destination:
    server: https://kubernetes.default.svc
    namespace: guestbook
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
```

## 주요 개념 정리

### Application

ArgoCD에서 배포 단위를 정의하는 CRD입니다.

| 필드 | 설명 |
|------|------|
| `source` | Git 저장소, 경로, 브랜치 |
| `destination` | 대상 클러스터, 네임스페이스 |
| `syncPolicy` | 자동 동기화 정책 |
| `project` | 소속 프로젝트 |

### Sync Status

| 상태 | 의미 |
|------|------|
| **Synced** | Git과 클러스터 상태 일치 |
| **OutOfSync** | Git과 클러스터 상태 불일치 |
| **Unknown** | 상태 확인 불가 |

### Health Status

| 상태 | 의미 |
|------|------|
| **Healthy** | 모든 리소스 정상 |
| **Progressing** | 배포 진행 중 |
| **Degraded** | 일부 리소스 문제 |
| **Missing** | 리소스 누락 |

## 트러블슈팅

### ArgoCD UI 접근 불가

```bash
# Pod 상태 확인
kubectl get pods -n argocd

# 로그 확인
kubectl logs -n argocd deployment/argocd-server
```

### 동기화 실패

```bash
# Application 상태 확인
argocd app get <app-name>

# 강제 동기화
argocd app sync <app-name> --force
```

## 참고 자료

- [ArgoCD 공식 문서](https://argo-cd.readthedocs.io/)
- [GitOps 원칙 - CNCF](https://opengitops.dev/)
- [CloudNet@ 스터디 노션](https://www.notion.so/CloudNet-Blog-c9dfa44a27ff431dafdd2edacc8a1863)

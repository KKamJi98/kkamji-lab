# Argo CD in Practice - 실습 자료

**"Argo CD in Practice"** (Packt Publishing) 도서의 예제 코드 및 실습 자료입니다.

---

## 1. 도서 소개

<img src="https://static.packt-cdn.com/products/9781803233321/cover/smaller" alt="Argo CD in Practice" height="200px" align="right">

**Argo CD in Practice: The GitOps way of managing cloud-native applications**

GitOps 방식으로 클라우드 네이티브 애플리케이션을 관리하는 실용적인 가이드입니다.

**주요 내용:**

- GitOps 원칙과 Infrastructure as Code(IaC) 관계
- ArgoCD를 활용한 Git 상태와 클러스터 상태 동기화
- 프로덕션 환경에서의 ArgoCD 운영 및 트러블슈팅
- CI/CD 파이프라인 구성 및 배포 실패 최소화
- Kubernetes YAML 검증 및 유효성 검사

**대상 독자:**

- CI/CD 파이프라인을 구축하는 소프트웨어 개발자
- Kubernetes 환경에서 작업하는 DevOps 엔지니어
- GitOps 도입을 고려하는 SRE

---

## 2. 디렉토리 구조

```
ArgoCD-in-Practice/
├── ch01/    # 1장: GitOps 소개
├── ch02/    # 2장: ArgoCD 시작하기
├── ch03/    # 3장: Application 관리
├── ch04/    # 4장: 동기화 전략
├── ch05/    # 5장: RBAC 및 보안
├── ch06/    # 6장: 프로덕션 운영
├── ch07/    # 7장: 트러블슈팅
├── ch08/    # 8장: 멀티 클러스터
└── ch09/    # 9장: 고급 기능
```

---

## 3. 주요 학습 내용

### 3.1. 1장: GitOps 소개

- GitOps 핵심 원칙
- 기존 CI/CD와의 차이점
- Pull vs Push 모델

### 3.2. 2장: ArgoCD 시작하기

ArgoCD 설치 및 첫 번째 Application 배포:

```bash
# ArgoCD 설치
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# CLI 로그인
argocd login localhost:8080

# 첫 번째 앱 배포
argocd app create guestbook \
  --repo https://github.com/argoproj/argocd-example-apps.git \
  --path guestbook \
  --dest-server https://kubernetes.default.svc \
  --dest-namespace default
```

### 3.3. 3장: Application 관리

Application CRD 상세 구조:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: myapp
  namespace: argocd
spec:
  project: default

  source:
    repoURL: https://github.com/myorg/myapp.git
    targetRevision: HEAD
    path: manifests

  destination:
    server: https://kubernetes.default.svc
    namespace: myapp

  syncPolicy:
    automated:
      prune: true       # Git에서 삭제된 리소스 자동 삭제
      selfHeal: true    # 수동 변경 자동 복구
    syncOptions:
    - CreateNamespace=true
```

### 3.4. 4장: 동기화 전략

**Sync Waves**: 리소스 배포 순서 제어

```yaml
metadata:
  annotations:
    argocd.argoproj.io/sync-wave: "1"  # 숫자가 낮을수록 먼저 배포
```

**Hooks**: 동기화 전/후 작업 실행

```yaml
metadata:
  annotations:
    argocd.argoproj.io/hook: PreSync      # 동기화 전 실행
    argocd.argoproj.io/hook-delete-policy: HookSucceeded
```

### 3.5. 5장: RBAC 및 보안

ArgoCD 계정 관리:

```yaml
# argocd-cm ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: argocd-cm
data:
  accounts.developer: apiKey, login
```

### 3.6. 6장: 프로덕션 운영

- HA(High Availability) 구성
- 모니터링 및 알림
- 백업 및 복구

### 3.7. 7장: 트러블슈팅

일반적인 문제 해결:

```bash
# Application 상태 확인
argocd app get myapp

# 동기화 로그 확인
argocd app logs myapp

# 강제 동기화
argocd app sync myapp --force --prune

# 리소스 차이 확인
argocd app diff myapp
```

### 3.8. 8장: 멀티 클러스터

```bash
# 외부 클러스터 등록
argocd cluster add <context-name>

# 클러스터 목록 확인
argocd cluster list
```

### 3.9. 9장: 고급 기능

**ApplicationSet**: 여러 Application 자동 생성

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: cluster-apps
spec:
  generators:
  - list:
      elements:
      - cluster: dev
        url: https://dev-cluster
      - cluster: prod
        url: https://prod-cluster
  template:
    metadata:
      name: '{{cluster}}-app'
    spec:
      source:
        repoURL: https://github.com/myorg/apps.git
        path: '{{cluster}}'
```

---

## 4. 실습 환경

### 4.1. 요구사항

| 소프트웨어 | 버전 | 비고 |
|-----------|------|------|
| ArgoCD | v2.1+ | v2.2 권장 |
| Kubernetes | 1.20+ | kind/minikube 가능 |
| kubectl | 1.20+ | |
| argocd CLI | 최신 | |

### 4.2. 환경 구성

```bash
# kind 클러스터 생성
kind create cluster --name argocd-practice

# ArgoCD 설치
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/v2.8.0/manifests/install.yaml

# 초기 비밀번호 확인
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d

# 포트 포워딩
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

---

## 5. 관련 자료

- [Argo CD in Practice - Packt](https://www.packtpub.com/product/argo-cd-in-practice/9781803233321)
- [무료 eBook 다운로드](https://packt.link/free-ebook/9781803233321) (구매자 대상)
- [ArgoCD 공식 문서](https://argo-cd.readthedocs.io/)
- [ArgoCD GitHub](https://github.com/argoproj/argo-cd)

---

## 6. 저자

- **Spiros Economakis** - SRE, GitOps 전문가
- **Liviu Costea** - DevOps 엔지니어, CNCF Ambassador

# KKamJi Lab

클라우드 네이티브 기술 학습 및 실습 자료를 모아둔 개인 저장소입니다.

---

## 1. 개요

이 저장소는 클라우드 네이티브 기술을 학습하고 실습한 내용을 정리한 개인 저장소입니다. Kubernetes, CNI(Container Network Interface), CI/CD 파이프라인 등 클라우드 네이티브 생태계의 핵심 기술들을 다룹니다.

---

## 2. 저장소 구조

```
.
├── study/
│   ├── cilium-study/         # Cilium CNI 스터디 자료
│   │   ├── helm/             # Helm 차트 values 파일
│   │   ├── install-flannel/  # Flannel CNI 설치 가이드
│   │   ├── scripts/          # 유틸리티 스크립트
│   │   ├── tests/            # 테스트용 샘플 애플리케이션
│   │   └── vagrant/          # Vagrant 기반 K8s 클러스터 환경
│   ├── ci-cd-study/          # CI/CD 스터디 자료 (ArgoCD 중심)
│   └── argocd-study/         # ArgoCD 심화 학습 자료
└── README.md
```

---

## 3. 스터디 목록

### 3.1. Cilium Study - Season 1

eBPF 기반의 고성능 네트워킹, 관측성(Observability), 보안 솔루션인 **Cilium**을 심층적으로 학습하는 스터디입니다.

**주요 학습 내용:**

- Vagrant와 VirtualBox를 활용한 Kubernetes 클러스터 자동 구축
- Cilium의 핵심 기능 이해 (eBPF, kube-proxy 대체, 네트워크 정책 등)
- Hubble을 활용한 네트워크 관측성 확보
- `kube-proxy` 없이 Cilium만으로 서비스 라우팅 구현

**실습 환경:**

- Master Node 1대 + Worker Node 2대 구성
- kubeadm을 활용한 클러스터 초기화
- 선언적(YAML) 또는 명령형(CLI) 방식의 클러스터 구성 선택 가능

자세한 내용은 [Cilium Study README](./study/cilium-study/README.md)를 참고하세요.

### 3.2. CI/CD Study - Season 1 (ArgoCD)

GitOps 원칙을 기반으로 한 CI/CD 파이프라인 구축을 학습하는 스터디입니다. **ArgoCD**를 중심으로 선언적 배포 관리를 실습합니다.

**주요 학습 내용:**

- GitOps의 핵심 원칙 이해
- ArgoCD를 활용한 Kubernetes 애플리케이션 자동 배포
- 다양한 애플리케이션(Node.js, Python, Spring Boot) 컨테이너화 및 배포
- Helm, Kustomize를 활용한 매니페스트 관리

**참고 도서:**

- "GitOps Cookbook" (Packt Publishing)
- "Argo CD in Practice" (Packt Publishing)

자세한 내용은 [CI/CD Study README](./study/ci-cd-study/README.md)를 참고하세요.

---

## 4. 사전 요구사항

실습을 진행하기 위해 다음 도구들이 필요합니다:

| 도구 | 용도 | 설치 (macOS) |
|------|------|--------------|
| Docker | 컨테이너 런타임 | `brew install --cask docker` |
| Vagrant | VM 프로비저닝 | `brew install vagrant` |
| VirtualBox | 가상화 플랫폼 | `brew install --cask virtualbox` |
| kubectl | Kubernetes CLI | `brew install kubernetes-cli` |
| Helm | 패키지 관리자 | `brew install helm` |
| kind | 로컬 K8s 클러스터 | `brew install kind` |

---

## 5. 빠른 시작

### 5.1. Cilium 실습 환경 구축

```bash
# 저장소 클론
git clone https://github.com/KKamJi98/kkamji-lab.git
cd kkamji-lab

# Vagrant 환경으로 이동 (고급 설정 권장)
cd study/cilium-study/vagrant/vagrant-advanced

# VM 생성 및 클러스터 구축
vagrant up

# Master 노드 접속
vagrant ssh cilium-m1

# 클러스터 상태 확인
kubectl get nodes
```

### 5.2. kind를 활용한 로컬 클러스터 구축

```bash
# kind 클러스터 생성
kind create cluster --name myk8s --image kindest/node:v1.32.8

# 클러스터 확인
kubectl get nodes -o wide
```

---

## 6. 참고 자료

- [Cilium 공식 문서](https://docs.cilium.io/)
- [ArgoCD 공식 문서](https://argo-cd.readthedocs.io/)
- [Kubernetes 공식 문서](https://kubernetes.io/docs/)

---

## 7. Markdown 도구 실행 방법

저장소 내 마크다운 헤더 규칙 수정 및 번호 재정렬을 자동화할 수 있습니다.

```bash
# 저장소 루트에서 실행
./scripts/run_md_tools.sh --root .
```

- Python 3이 필요하며, `PYTHON_BIN` 환경변수로 다른 파이썬 실행 파일을 지정할 수 있습니다.
- `--root` 인자로 처리할 디렉터리를 지정합니다. 생략 시 기본값은 현재 디렉터리입니다.

---

## 8. 라이선스

이 저장소의 실습 자료는 학습 목적으로 자유롭게 활용할 수 있습니다.

# KKamJi Lab

클라우드 네이티브/DevOps 학습과 실습을 정리한 개인 저장소입니다. 스터디 기록과 실험용 도구를 함께 관리합니다.

---

## 1. 빠른 안내

- `study/`: 기술 스터디 및 실습 노트 (Cilium, Istio, ArgoCD 등)
- `tools/`: 실습/운영을 위한 Python CLI 도구 모음
- `packer/`: Packer 기반 이미지 빌드 실험

---

## 2. 저장소 구조

```
.
├── packer/
│   └── eks-1.34/               # EKS AMI 빌드 실험
├── study/
│   ├── aws/                    # AWS 실험 (Kinesis)
│   ├── ci-cd-study/            # GitOps/ArgoCD 중심 CI/CD 스터디
│   ├── cilium-study/           # Cilium CNI 스터디
│   ├── istio-study/            # Istio 서비스 메시 스터디
│   └── jenkins/                # Jenkins Operator 실습
├── tools/
│   ├── domain-resource-tracer/ # Route53 → AWS 리소스 추적
│   ├── eks-token-cache/        # EKS 토큰 캐시 스크립트
│   ├── git-worktree-tool/      # Git worktree bare repo 관리 CLI
│   ├── kube-pick/              # kubeconfig 컨텍스트 선택/전환
│   ├── kubectx-kubens/         # kubectx/kubens 셸 함수 (fzf+캐시)
│   ├── kubeconfig-cleaner/     # 미사용 cluster/user 정리
│   ├── kubeconfig-merger/      # kubeconfig 병합
│   ├── markdown-fmt/           # README 헤더 번호 정리
│   ├── mirror-container-images/# 컨테이너 이미지 ECR 미러링
│   ├── pull-request-jump/      # PR 페이지 오픈 CLI
│   ├── route53-traffic-monitor/# Route53 가중치 트래픽 모니터
│   └── swagger-loadgen/        # Swagger 기반 부하 생성 도구
└── README.md
```

---

## 3. 스터디 트랙

| 트랙 | 내용 | 시작 지점 |
| --- | --- | --- |
| Cilium Study | eBPF 기반 CNI, Vagrant K8s 클러스터에서 Hubble/네트워크 정책 실습 | `study/cilium-study/README.md` |
| Istio Study | 서비스 메시 설치, 트래픽 라우팅, Fault Injection, 모니터링 | `study/istio-study/README.md` |
| CI/CD Study (ArgoCD) | GitOps 기반 선언적 배포, ArgoCD 설치 및 운영 | `study/ci-cd-study/README.md` |
| Jenkins Operator | Kubernetes 환경 Jenkins Operator 설치/구성 | `study/jenkins/README.md` |
| AWS (Kinesis) | Kinesis 스트리밍 실험 (WIP) | `study/aws/README.md` |

---

## 4. 도구 (CLI)

각 도구의 설치/사용법은 해당 README를 따르세요. Python CLI 도구는 `uv tool install .` 패턴을 사용합니다.

### Python CLI 도구

| 도구 | 명령어 | 목적 | Python |
| --- | --- | --- | --- |
| domain-resource-tracer | `drt` | Route53 도메인에서 연결된 AWS 리소스(ALB, CloudFront 등) 추적 | 3.11+ |
| git-worktree-tool | `wt` | Git worktree bare repository 관리 CLI | 3.9+ |
| kube-pick | `kubepick` | 여러 kubeconfig 파일 중 원하는 컨텍스트 선택/전환 | 3.9+ |
| kubeconfig-cleaner | `kubeconfig-cleaner` | 미사용 cluster/user 엔트리 정리 | 3.9+ |
| kubeconfig-merger | `kubeconfig-merger` | 여러 kubeconfig 파일을 하나로 병합 | 3.9+ |
| pull-request-jump | `prj` | CLI에서 GitHub/Bitbucket PR 페이지 자동 열기 | 3.9+ |
| route53-traffic-monitor | `dnsmon` | Route53 가중치 레코드의 설정 비율 vs 실제 트래픽 실시간 비교 | 3.11+ |
| swagger-loadgen | `swagger-loadgen` | Swagger/OpenAPI 스펙에서 GET endpoint 자동 수집 후 고정 TPS 부하 생성 | 3.11+ |

### 셸 스크립트 / 기타

| 도구 | 목적 | 안내 |
| --- | --- | --- |
| eks-token-cache | EKS 토큰 캐싱으로 kubectl 실행 속도 개선 | `tools/eks-token-cache/README.md` |
| kubectx-kubens | kubectx/kubens 대체 zsh 셸 함수 (fzf+캐시 기반) | `tools/kubectx-kubens/README.md` |
| markdown-fmt | study README 헤더 번호 자동 정리 | `tools/markdown-fmt/` |
| mirror-container-images | crane 기반 컨테이너 이미지 ECR 미러링 | `tools/mirror-container-images/README.md` |

---

## 5. 빠른 시작

```bash
# 저장소 클론
git clone https://github.com/KKamJi98/kkamji-lab.git
cd kkamji-lab

# 원하는 스터디로 이동
cd study/cilium-study

# Python CLI 도구 설치 (예: git-worktree-tool)
cd tools/git-worktree-tool
uv tool install .
wt --help
```

각 스터디/도구의 상세 절차는 해당 README를 따르세요.

---

## 6. 공통 요구사항 (선택)

다음 도구들은 스터디/도구에 따라 필요합니다.

| 도구 | 용도 | 설치 (macOS) |
|------|------|--------------|
| Docker | 컨테이너 런타임 | `brew install --cask docker` |
| Vagrant | VM 프로비저닝 | `brew install vagrant` |
| VirtualBox | 가상화 플랫폼 | `brew install --cask virtualbox` |
| kubectl | Kubernetes CLI | `brew install kubernetes-cli` |
| Helm | 패키지 관리자 | `brew install helm` |
| kind | 로컬 K8s 클러스터 | `brew install kind` |
| Packer | 머신 이미지 빌드 | `brew install hashicorp/tap/packer` |
| Terraform | IaC 프로비저닝 | `brew install hashicorp/tap/terraform` |
| uv | Python CLI 도구 설치 | `brew install uv` |

---

## 7. 문서 관리 (Markdown)

`study/` 하위 README에 한해 헤더 규칙/번호를 정리하는 스크립트가 있습니다.

```bash
# study 하위 README 포맷팅
./tools/markdown-fmt/format-study-readme.sh
```

- `tools/markdown-fmt/markdown-formatter` 경로가 필요합니다. 없으면 스크립트 경로를 수정하거나 별도 준비가 필요합니다.
- 단일 파일 번호만 갱신하려면 `tools/markdown-fmt/renumber_readme.py`를 사용할 수 있습니다.

---

## 8. 참고 자료

- [Cilium 공식 문서](https://docs.cilium.io/)
- [Istio 공식 문서](https://istio.io/latest/docs/)
- [ArgoCD 공식 문서](https://argo-cd.readthedocs.io/)
- [Kubernetes 공식 문서](https://kubernetes.io/docs/)

---

## 9. 라이선스

이 저장소의 실습 자료는 학습 목적으로 자유롭게 활용할 수 있습니다.

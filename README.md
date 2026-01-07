# KKamJi Lab

클라우드 네이티브/DevOps 학습과 실습을 정리한 개인 저장소입니다. 스터디 기록과 실험용 도구를 함께 관리합니다.

---

## 1. 빠른 안내

- `study/`: 기술 스터디 및 실습 노트 (Cilium, Istio, ArgoCD 등)
- `tools/`: 실습/운영을 위한 Python CLI 도구 모음

---

## 2. 저장소 구조

```
.
├── study/
│   ├── aws/                # AWS 실험 (Kinesis 디렉터리만 존재)
│   ├── ci-cd-study/        # GitOps/ArgoCD 중심 CI/CD 스터디
│   ├── cilium-study/       # Cilium CNI 스터디
│   ├── istio-study/        # Istio 서비스 메시 스터디
│   └── jenkins/            # Jenkins Operator 실습
├── tools/
│   ├── domain-resource-tracer/
│   ├── kube-pick/
│   ├── kubeconfig-cleaner/
│   ├── kubeconfig-merger/
│   └── markdown-fmt/
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

각 도구의 설치/사용법은 해당 README를 따르세요. Python CLI 도구는 보통 `uv tool install .` 패턴을 사용합니다.

| 도구 | 목적 | 안내 |
| --- | --- | --- |
| domain-resource-tracer | AWS 도메인 기반 리소스 추적 | `tools/domain-resource-tracer/README.md` |
| kube-pick | kubeconfig 빠른 전환 | `tools/kube-pick/README.md` |
| kubeconfig-cleaner | kubeconfig 정리/정제 | `tools/kubeconfig-cleaner/README.md` |
| kubeconfig-merger | kubeconfig 병합 | `tools/kubeconfig-merger/README.md` |
| markdown-fmt | study README 포맷/번호 정리 | `tools/markdown-fmt/` |

---

## 5. 빠른 시작

```bash
# 저장소 클론
git clone https://github.com/KKamJi98/kkamji-lab.git
cd kkamji-lab

# 원하는 스터디로 이동
cd study/cilium-study
# 또는
cd study/istio-study
```

각 스터디의 상세 절차는 해당 README를 따르세요.

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

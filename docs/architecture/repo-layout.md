---
title: Repository layout
updated: 2026-08-24
type: architecture
status: current
---

# Repository layout

새 도구나 스터디 모듈을 추가하면 이 트리도 함께 고친다. 손으로 유지하는 트리는
조용히 낡는다.

```
kkamji-lab/
├── .claude/                    # Agent settings
├── .codex/                     # Codex skills
├── packer/                     # Packer 이미지 빌드 실험
│   └── eks-1.34/
├── study/                      # 기술 스터디 및 실습
│   ├── aws/                    # AWS 실험 (Kinesis)
│   ├── ci-cd-study/            # GitOps/ArgoCD CI/CD 스터디
│   ├── cilium-study/           # Cilium CNI 스터디
│   ├── istio-study/            # Istio 서비스 메시 스터디
│   └── jenkins/                # Jenkins Operator 실습
├── tools/                      # CLI 도구 및 셸 함수
│   ├── domain-resource-tracer/ # Route53 → AWS 리소스 추적
│   ├── eks-token-cache/        # EKS 토큰 캐시 스크립트
│   ├── gcloud-pick/            # gcloud CLI auth + ADC 동시 전환 (gp)
│   ├── kube-pick/              # kubeconfig 컨텍스트 선택/전환
│   ├── kubectx-kubens/         # kubectx/kubens 셸 함수 (fzf+캐시)
│   ├── kubeconfig-cleaner/     # 미사용 cluster/user 정리
│   ├── kubeconfig-merger/      # kubeconfig 병합
│   ├── markdown-fmt/           # README 헤더 번호 정리
│   ├── mirror-container-images/# 컨테이너 이미지 미러링
│   ├── route53-traffic-monitor/# Route53 가중치 트래픽 모니터
│   └── swagger-loadgen/        # Swagger 기반 부하 생성 도구
└── README.md
```

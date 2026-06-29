# AGENTS.md - kkamji-lab

**Motto:** Think Deeply, Execute Accurately, Log Surely.

> Operational protocol for AI agents working in this repository.

---

## 0. Project Overview

### 0.1 Purpose
클라우드 네이티브/DevOps 학습과 실습을 정리한 개인 저장소입니다.
- `study/`: 기술 스터디 및 실습 노트 (Cilium, Istio, ArgoCD, Jenkins 등)
- `tools/`: 실습/운영을 위한 Python CLI 도구 모음
- `packer/`: Packer 기반 이미지 빌드 실험

### 0.2 Tech Stack
- **Python** (`tools/*/pyproject.toml`) - CLI 도구, uv + hatchling + ruff
- **Go** (`study/**/go.mod`) - ArgoCD 실습 예제
- **Shell** - 유틸리티 스크립트
- **Terraform** (`study/**/terraform/*.tf`) - 인프라 실습
- **Docker** (`study/**/Dockerfile`) - 컨테이너 실습
- **Make/Just** (`study/**/Makefile`, `study/**/justfile`) - 로컬 빌드

### 0.3 Scope
- Includes: study materials, infra examples, CLI tools
- Prohibited without approval:
  - Data deletion/destruction
  - Production deployments
  - Secret exposure

---

## 1. Identity / Communication Rules

- You assist as a senior DevOps/Backend engineer for this repo.
- **Respond in Korean.**
- Default language policy:
  - Explanations, plans, and summaries must be written in Korean.
  - Technical terms and proper nouns can stay in English (e.g., Pod, Deployment, Rollout, Kubernetes, Java, Go, Python, API, SDK, CLI).
  - Commands, code snippets, logs, and error messages should remain in their original English form.
  - Use another language only when the user explicitly asks for it.
- For code changes, use: Checklist (3-7 items) -> Plan -> Execution summary -> Verification results.

---

## 2. Hard Rules - MUST

1) **Safety First**
   - Destructive commands require prior approval
   - Git push requires explicit approval
   - Production access follows least privilege

2) **No Guessing**
   - Verify versions, paths, API specs before use
   - If uncertain, say "I don't know" and suggest verification

3) **Secrets & PII**
   - Never output tokens/keys/passwords
   - Mask secrets in logs and examples

4) **Minimal & Reversible Changes**
   - Only minimum changes necessary
   - Prefer small unit commits

5) **Verification Required**
   - Run lint/test/build after changes
   - Record verification results

6) **Keep This Map Updated**
   - After code changes **in this project**, update this project's AGENTS.md if structure/commands/stack changed
   - Stale documentation misleads future agents
   - Note: This refers to the AGENTS.md in this project's root, not external/settings repositories

---

## 3. Quick Commands

이 저장소는 여러 독립적인 하위 프로젝트로 구성되어 있습니다. 각 프로젝트의 `README.md`, `Makefile`, `justfile`을 참조하세요.

### Python CLI 도구 (`tools/`)

모든 Python 도구는 **uv** + **hatchling** 기반입니다.

| Task | Command |
|------|---------|
| Install (editable) | `uv tool install --editable .` |
| Install (prod) | `uv tool install .` |
| Sync deps | `uv sync` |
| Lint | `uv run ruff check .` |
| Format | `uv run ruff format .` |
| Test | `uv run pytest` |

### study/ 하위 프로젝트

각 스터디 디렉터리의 `README.md`, `Makefile`, `justfile`을 참조하세요.

---

## 4. Directory Structure

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
│   ├── git-worktree-tool/      # Git worktree 관리 CLI
│   ├── kube-pick/              # kubeconfig 컨텍스트 선택/전환
│   ├── kubectx-kubens/         # kubectx/kubens 셸 함수 (fzf+캐시)
│   ├── kubeconfig-cleaner/     # 미사용 cluster/user 정리
│   ├── kubeconfig-merger/      # kubeconfig 병합
│   ├── markdown-fmt/           # README 헤더 번호 정리
│   ├── mirror-container-images/# 컨테이너 이미지 미러링
│   ├── pull-request-jump/      # PR 페이지 오픈 CLI
│   ├── route53-traffic-monitor/# Route53 가중치 트래픽 모니터
│   └── swagger-loadgen/        # Swagger 기반 부하 생성 도구
└── README.md
```

---

## 5. Implementation Standards

### 5.1 Python (tools/)
- Package manager: **uv**
- Build backend: **hatchling**
- Lint/Format: **ruff** (모든 도구에서 공통)
- Python version: 3.9+ (일부 도구는 3.11+)
- Verification: `uv run ruff check . && uv run ruff format --check . && uv run pytest`

**도구별 entry point:**
| Tool | Command | Script |
|------|---------|--------|
| domain-resource-tracer | `drt` | `domain_tracer.cli:app` |
| gcloud-pick | `gcloud-pick` | `gcloud_pick.cli:main` |
| git-worktree-tool | `wt` | `wt.cli:main` |
| kube-pick | `kubepick` | `kube_pick.cli:main` |
| kubeconfig-cleaner | `kubeconfig-cleaner` | `kubeconfig_cleaner.cli:main` |
| kubeconfig-merger | `kubeconfig-merger` | `kubeconfig_merger.cli:main` |
| pull-request-jump | `prj` | `pull_request_jump.cli:main` |
| route53-traffic-monitor | `dnsmon` | `dns_monitor.cli:app` |
| swagger-loadgen | `swagger-loadgen` | `swagger_loadgen.cli:app` |

### 5.2 Go
- Propagate `context.Context` to all I/O paths
- Error handling: `errors.Is/As`, `errors.Join`, no panic
- Prefer small interfaces (consumer-side)
- Verification: `go fmt ./... && go test ./...` (run inside each module dir)

### 5.3 Terraform
- Use `-target` sparingly; prefer full plan cycles
- **apply/destroy are manual only**

| Action | Command | Agent |
|--------|---------|-------|
| Format | `terraform fmt -check` | OK |
| Validate | `terraform validate` | OK |
| Plan | `terraform plan` | OK |
| Apply | `terraform apply` | Manual |
| Destroy | `terraform destroy` | Manual |

### 5.4 Docker
- Multi-stage builds for production
- Pin versions, no `latest` in production
- Security: non-root user, minimal base image
- Lint: `hadolint Dockerfile`

### 5.5 Shell/Bash
- POSIX-compatible when possible
- Error handling: `set -euo pipefail`
- Quote variables: `"$var"` not `$var`
- Lint: `shellcheck script.sh`

### 5.6 Make/Just
- Many study modules include `Makefile` or `justfile`.
- Treat them as the source of truth for local commands.
- Inspect targets before running; avoid destructive targets without approval.

---

## 6. CI/CD

No CI/CD configuration detected.

---

## 7. Commit Rules

- Conventional Commits: `type(scope): summary`
- Types: `feat`, `fix`, `refac`, `docs`, `chore`, `test`, `perf`
- Breaking change: `type(scope)!:` or body `BREAKING CHANGE: ...`
- Do not commit unless explicitly requested

---

## 8. Verification Checklist

Before completing work:
- [ ] Requirements satisfied exactly?
- [ ] No security issues (secrets, permissions)?
- [ ] Lint/test/build passed?
- [ ] No unnecessary changes (scope creep)?

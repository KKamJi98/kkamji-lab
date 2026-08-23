---
title: Implementation standards
updated: 2026-08-24
type: rule
status: current
---

# Implementation standards

언어와 도구별 표준이다. `tools/*/pyproject.toml` 을 고치면 아래 entry point 표도
같은 PR 에서 고친다. CI 가 그것을 확인한다.

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
| kube-pick | `kubepick` | `kube_pick.cli:main` |
| kubeconfig-cleaner | `kubeconfig-cleaner` | `kubeconfig_cleaner.cli:main` |
| kubeconfig-merger | `kubeconfig-merger` | `kubeconfig_merger.cli:main` |
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

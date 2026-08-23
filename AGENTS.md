# AGENTS.md - kkamji-lab

**Motto:** Think Deeply, Execute Accurately, Log Surely.

> Operational protocol for AI agents working in this repository.

---

## Knowledge Layout

- **Current structure, decisions, rules**: `docs/`. Catalog is `docs/index.md`. Read it before changing code.
- **Work journal and backlog**: vault `workspaces/`.
- **Cross-repo knowledge**: vault `wiki/`, `shapes/`, `runbooks/`.
- Frontmatter requires exactly four keys: `title`, `updated`, `type`, `status`. Register every new document in `docs/index.md`.
- No wikilinks. Relative markdown links only.
- When code mapped in `docs/_meta/coupling.json` changes, change the mapped document in the same PR.
- Never hand-edit `docs/_meta/docs_lint.py`. Canonical copy is `kkamji-settings/agents/docs-wiki/docs_lint.py`.
- Lint: `python3 docs/_meta/docs_lint.py --root .`

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

- 디렉터리 트리는 `docs/architecture/repo-layout.md` 가 정본이다.

---

## 5. Implementation Standards

- 언어/도구별 표준과 entry point 표는 `docs/rules/implementation-standards.md` 가 정본이다.

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

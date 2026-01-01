---
name: blog-post-generator
description: Generate a Jekyll blog post in kkamji98.github.io from a study directory (README.md + manifests + images) in kkamji-lab. Use when the user asks to write a blog post based on a study topic directory or wants README content converted into a post with WebP images, raw GitHub links for kubectl apply, and references.
---

# Blog Post Generator

## Overview

Convert a study directory into a polished Korean blog post that matches the existing Jekyll style, with WebP images in assets/img and raw GitHub links for manifests.

## Workflow

### 1) Confirm inputs and target paths
- Get the source directory path from the user and verify README.md exists.
- Locate the blog repo (default: /Users/ethan/code/code-personal/kkamji98.github.io). If the path differs, ask.
- Determine the target _posts path and filename using the current date (use `date`).

### 2) Collect materials
- Read README.md and identify the key sections, commands, and manifest files.
- List manifests and scripts referenced by the README.
- List images under the source directory (commonly img/).

### 3) Prepare assets (images)
- Choose the destination assets/img category by inspecting existing folders (see references/repo-layout.md).
- Convert PNG/JPG images to WebP and place them under assets/img/<category>/<topic>.
- Check for duplicate filenames in the destination before converting. If duplicates exist, rename or split into a subfolder; the conversion script skips duplicates and warns.
- Do not delete source images unless the user explicitly asks.
- Use scripts/convert-images-to-webp.sh for bulk conversion.

### 4) Write the post
- Follow the front matter template and structure in references/front-matter.md.
- **제목 형식**: 영어로 간결하게 작성 (예: "Istio Request Routing", "Kubernetes Network Policy")
  - `[Study N]`, `실습` 등 접미사 제거
- Write the post in Korean and keep tone consistent with existing posts.
- Add a short section to fetch the lab sources (git clone + cd).
- Replace local manifest paths in kubectl apply commands with raw GitHub URLs.
- **글 흐름 개선**: 실습/검증 섹션에서 자연스러운 흐름 유지
  - 섹션 시작: 맥락 연결 (왜 이 단계를 수행하는지)
  - 섹션 끝: 결과 정리 (결과와 의미 요약)
- Add a References section with authoritative sources and upstream repos.

### 5) Validate and reconcile gaps
- Verify raw GitHub URLs and image paths exist.
- If a referenced file is missing, add it to kkamji-lab or ask the user how to proceed.
- Check for any secrets or sensitive info before writing to the blog repo.

### 6) Pre-commit review (NEW)
- 포스트 작성 완료 후, git add/commit 전에 `blog-post-reviewer` 스킬 실행 권장
- 검토 항목:
  1. 글 흐름 (맥락 연결 + 결과 정리)
  2. 제목 형식 (영어, 접미사 제거)
  3. Markdown 형식 검증
- Markdown 형식 검증 명령:
  ```shell
  /Users/ethan/code/code-personal/kkamji98.github.io/kkamji_scripts/blog/run_md_tools.sh
  ```

## Title Format Examples

| Before (피하기) | After (권장) |
|-----------------|--------------|
| Istio 개요와 설치 흐름 [Istio Study 1] | Istio Overview & Installation Guide |
| Istio Request Routing 실습 [Istio Study 2] | Istio Request Routing |
| Kubernetes 네트워크 정책 [K8s Study 1] | Kubernetes Network Policy |

## Flow Writing Example

```markdown
### 4.1. 지연 시간 변경 (4s → 2s)

위에서 4초 지연 주입 시 timeout 오류가 발생했습니다. 이제 지연 시간을 2초로 낮춰 정상 동작을 확인해보겠습니다.

[설정 변경 + 이미지 + 설명]

이를 통해 지연 시간이 2초로 적용되었고, timeout 제한(2.5초) 내에 응답이 완료되어 정상 동작함을 확인했습니다.
```

## URL Pattern

- Raw file URL template:
  https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/<relative-path>

## Resources

- scripts/convert-images-to-webp.sh: Convert PNG/JPG images to WebP in bulk.
- references/repo-layout.md: Repository paths and discovery commands.
- references/front-matter.md: Front matter and section template.

## Related Skills

- **blog-post-reviewer**: 커밋 전 품질 검토 스킬
  - 글 흐름, 제목 형식, Markdown 형식 검증

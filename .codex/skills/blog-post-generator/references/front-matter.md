# Front Matter and Structure Template

## Front Matter (Example)

---
title: <Post Title in English>
date: <YYYY-MM-DD HH:MM:SS +0900>
author: kkamji
categories: [Kubernetes, <Topic>]
tags: [kubernetes, <tags...>]
comments: true
image:
  path: /assets/img/<category>/<topic>/<cover>.webp
---

## Title Format Rules

- **영어로 간결하게 작성**
- `[Study N]`, `[Part N]`, `실습` 등 접미사 제거
- 기술명 + 핵심 개념/기능 형태

### Examples

| Before (피하기) | After (권장) |
|-----------------|--------------|
| Istio 개요와 설치 흐름 [Istio Study 1] | Istio Overview & Installation Guide |
| Istio Request Routing 실습 [Istio Study 2] | Istio Request Routing |
| Istio Fault Injection 실습 [Istio Study 3] | Istio Fault Injection |

## Suggested Structure

- Intro: problem statement and summary
- Concepts / Architecture (if needed)
- Prerequisites
- Lab source fetch (git clone + cd)
- Step-by-step practice
- Verification / troubleshooting
- Cleanup
- References

## Image Placement

Use Markdown with absolute asset paths, for example:

![Alt text](/assets/img/<category>/<topic>/<image>.webp)

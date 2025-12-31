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
- Write the post in Korean and keep tone consistent with existing posts.
- Add a short section to fetch the lab sources (git clone + cd).
- Replace local manifest paths in kubectl apply commands with raw GitHub URLs.
- Insert images near relevant sections using /assets/img/... paths.
- Add a References section with authoritative sources and upstream repos.

### 5) Validate and reconcile gaps
- Verify raw GitHub URLs and image paths exist.
- If a referenced file is missing, add it to kkamji-lab or ask the user how to proceed.
- Check for any secrets or sensitive info before writing to the blog repo.

## URL Pattern

- Raw file URL template:
  https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/<relative-path>

## Resources

- scripts/convert-images-to-webp.sh: Convert PNG/JPG images to WebP in bulk.
- references/repo-layout.md: Repository paths and discovery commands.
- references/front-matter.md: Front matter and section template.

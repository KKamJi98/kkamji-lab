# Repo Layout and Conventions

## Key Paths

- Lab repo (source study content):
  /Users/ethan/code/code-personal/kkamji-lab

- Blog repo (target posts and assets):
  /Users/ethan/code/code-personal/kkamji98.github.io

- Blog posts:
  /Users/ethan/code/code-personal/kkamji98.github.io/_posts

- Blog images:
  /Users/ethan/code/code-personal/kkamji98.github.io/assets/img

## Image Placement Rule

- Choose the category folder by inspecting existing assets/img subfolders.
- Typical categories: kubernetes, ci-cd, observability, security, storage, etc.
- For a new topic, create assets/img/<category>/<topic>.

## Discovery Commands

- Locate README and manifests:
  rg --files -g 'README.md' <study-dir>
  rg --files -g '*.yaml' <study-dir>

- List images:
  find <study-dir> -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \)

- Check existing post patterns:
  rg -n "^title:|^categories:|^tags:" /Users/ethan/code/code-personal/kkamji98.github.io/_posts

## Raw GitHub URL Template

https://raw.githubusercontent.com/KKamJi98/kkamji-lab/main/<relative-path>

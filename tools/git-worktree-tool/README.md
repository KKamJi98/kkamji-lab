# git-worktree-tool (wt)

Git worktree 구조의 bare repository를 관리하는 CLI 도구입니다.
어떤 worktree 디렉토리에서든 `wt` 명령으로 전체 worktree를 관리할 수 있습니다.

## Features

- **wt init**: bare repository 초기 설정 자동화
- **wt add/remove**: worktree 추가/삭제 (복수/패턴 삭제 지원)
- **wt status**: 모든 worktree의 상태 (clean/dirty, sync 상태) 확인
- **wt fetch**: bare repo에서 `git fetch --all --prune` 실행
- **wt pull**: fetch 후 모든 worktree를 동기화 (기본 ff-only, `--rebase` 옵션)
- **wt upstream**: 모든 worktree에 `origin/<branch>` upstream 자동 설정

## Installation

```bash
# 개발 모드 설치
uv tool install --editable ~/code/code-personal/kkamji-lab/tools/git-worktree-tool

# 또는 일반 설치
uv tool install ~/code/code-personal/kkamji-lab/tools/git-worktree-tool
```

## Quick Start

```bash
# 새 프로젝트 시작 (bare repo + worktree 자동 설정)
wt init git@github.com:org/repo.git my-project

# 생성 결과:
# my-project/
# ├── .bare/    # bare repository
# └── main/     # main branch worktree

# 추가 브랜치와 함께 초기화
wt init git@github.com:org/repo.git my-project -w staging,develop
```

## Usage

### 초기화 (wt init)

```bash
# 기본 초기화 (URL에서 repo 이름 자동 추출)
wt init git@github.com:org/repo.git

# 경로 지정
wt init git@github.com:org/repo.git my-project

# 추가 worktree 브랜치 지정
wt init git@github.com:org/repo.git my-project -w staging,develop,feat/new-feature
```

### Worktree 관리 (wt add/remove)

```bash
# 기존 브랜치로 worktree 추가
wt add staging

# 새 브랜치 생성하면서 worktree 추가
wt add feat/my-feature -c

# 특정 브랜치 기반으로 새 브랜치 생성 (예: staging에서 분기)
wt add chore/test123 -c --base staging

# worktree 삭제
wt remove staging

# 여러 worktree 한 번에 삭제
wt remove provider exemplars

# 패턴으로 일괄 삭제 (branch/path name/full path glob)
wt remove --match "fix/*"

# 실제 삭제 없이 대상만 확인
wt remove --match "feat/*" --dry-run

# 강제 삭제 (dirty 상태여도)
wt remove staging -f
```

### 새 원격 브랜치를 worktree로 추가

```bash
# 1) 원격 최신화
wt fetch

# 2) 원격 브랜치를 worktree로 추가
wt add feature/new-remote

# 3) upstream이 없으면(선택)
wt upstream
```

### 상태 확인 (wt status)

```bash
wt status
wt st
```

### 동기화 (wt fetch/pull)

```bash
# 원격에서 fetch (bare repo에서 실행)
wt fetch
wt f

# fetch + 모든 worktree 동기화 (ff-only)
wt pull
wt p

# rebase 모드로 동기화
wt pull --rebase
wt p -r
```

### 기타

```bash
# worktree 목록 확인
wt list
wt ls

# 모든 worktree에 upstream 설정 (origin/<branch>)
wt upstream
wt up
```

## Example Output

### `wt init`

```
Initializing worktree repository
  URL:    git@github.com:org/repo.git
  Path:   /Users/you/code/repo

Step 1: Clone bare repository
  OK cloned to /Users/you/code/repo/.bare

Step 2: Configure fetch refspec
  OK configured fetch refspec
  OK fetched all branches

Step 3: Create worktrees
  Default branch: main
  OK created worktree: main/

✓ Initialization complete!

Next steps:
  cd /Users/you/code/repo/main
  wt status

To add more worktrees:
  cd /Users/you/code/repo/.bare
  git worktree add ../<branch-name> <branch-name>
```

### `wt status`

```
Bare repo: /path/to/repo/.bare

STATUS   BRANCH                    SYNC           PATH
-------- ------------------------- -------------- ----------------------------------------
CLEAN    main                      =              /path/to/repo/main
CLEAN    staging                   ↓3             /path/to/repo/staging
DIRTY    feat/new-feature          ↑2             /path/to/repo/feat-new-feature

Summary: total=3 clean=2 dirty=1
```

### `wt pull`

```
Bare repo: /path/to/repo/.bare

Step 1: Fetch
Fetching from bare repo: /path/to/repo/.bare
OK fetch --all --prune completed

Step 2: Sync worktrees

==> main (main)
  OK already up to date

==> staging (staging)
  OK fast-forwarded

==> feat/new-feature (feat-new-feature)
  SKIP dirty working tree

Summary: ok=2 skip=1 fail=0
```

## Git Worktree 구조

이 도구는 다음과 같은 bare repository + worktree 구조를 사용합니다:

```
my-project/
├── .bare/              # bare repository (git clone --bare)
├── main/               # worktree for main branch
├── staging/            # worktree for staging branch
└── feat-new-feature/   # worktree for feature branch
```

### 수동 설정 방법 (참고)

`wt init` 없이 수동으로 설정하려면:

```bash
# 1. bare repository 클론
git clone --bare git@github.com:org/repo.git my-project/.bare

# 2. fetch 설정
cd my-project/.bare
git config remote.origin.fetch "+refs/heads/*:refs/remotes/origin/*"
git fetch --all

# 3. worktree 추가
git worktree add ../main main
git worktree add ../staging staging
```

## Safety Features

- **ff-only by default**: `wt pull`은 기본적으로 fast-forward만 수행합니다. 로컬 커밋이 있으면 실패합니다.
- **optional rebase**: `--rebase` 옵션 사용 시 rebase 수행, 충돌 시 자동 abort됩니다.
- **dirty check**: uncommitted 변경이 있는 worktree는 자동으로 스킵합니다.
- **no upstream skip**: upstream이 설정되지 않은 브랜치는 스킵합니다.

## Command Reference

| Command | Alias | Description |
|---------|-------|-------------|
| `wt init <url> [path]` | - | 새 bare repo + worktree 초기화 |
| `wt add <branch>` | `a` | worktree 추가 |
| `wt remove <identifier...> [--match <glob>] [--dry-run]` | `rm` | worktree 삭제 (복수/패턴 지원) |
| `wt status` | `st` | 모든 worktree 상태 확인 |
| `wt fetch` | `f` | `git fetch --all --prune` |
| `wt pull` | `p` | fetch + ff-only (기본) |
| `wt pull --rebase` | `p -r` | fetch + rebase |
| `wt list` | `ls` | worktree 목록 |
| `wt upstream` | `up` | upstream 자동 설정 |

## Requirements

- Python 3.9+
- Git 2.15+ (worktree support)

## License

MIT

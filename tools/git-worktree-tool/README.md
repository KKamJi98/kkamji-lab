# git-worktree-tool (wt)

Git worktree 구조의 bare repository를 관리하는 CLI 도구입니다.
어떤 worktree 디렉토리에서든 `wt` 명령으로 전체 worktree를 관리할 수 있습니다.

## Features

- **wt init**: bare repository 초기 설정 자동화
- **wt add/remove**: worktree 추가/삭제 (`wt rm`은 기본적으로 worktree만 삭제, 복수/패턴 삭제 지원)
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

# worktree만 삭제 (로컬 브랜치는 유지)
wt remove staging

# worktree + 로컬 브랜치 삭제
wt remove feat/my-feature -b

# worktree + 로컬 브랜치 + 원격 브랜치 삭제
wt remove feat/my-feature -b --remote

# 여러 worktree 한 번에 삭제
wt remove provider exemplars

# 패턴으로 일괄 삭제 (branch/path name/full path glob)
wt remove --match "fix/*"

# 실제 삭제 없이 대상만 확인
wt remove --match "feat/*" --dry-run

# 강제 삭제 (dirty 상태여도)
wt remove staging -f
```

`wt remove`는 기본적으로 worktree entry와 디렉토리만 제거합니다.
로컬 브랜치까지 같이 정리하려면 `-b/--branch`를 명시적으로 사용하세요.
원격 브랜치까지 삭제하려면 `--remote`를 함께 사용하되, `--remote`는 `-b/--branch`가 필요합니다.

`-b`로 브랜치를 삭제할 때, 머지되지 않은 브랜치는 커밋 손실을 막기 위해 **안전하게 보존**되며
`WARN branch kept`으로 표시됩니다(에러 아님, exit code는 2). 보존된 브랜치는 머지 여부를
확인한 뒤 `wt rm -f -b <id>` 또는 `git -C <repo>/.bare branch -D <branch>`로 강제 삭제할 수 있습니다.
로컬 브랜치가 보존되면 `--remote`가 있어도 원격 브랜치는 삭제하지 않습니다(유일 사본 보호).
`--dry-run -b`는 현재 refs 기준으로 로컬/원격 브랜치가 삭제될지, 보존될지, 검증 불가인지 미리 표시합니다.

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

`wt pull`은 각 브랜치에 설정된 실제 upstream ref(`@{u}`)를 기준으로 동기화합니다.
일반적인 경우는 `origin/<branch>`이지만, 다른 remote를 upstream으로 지정한 브랜치도 그대로 따릅니다.

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

루트 디렉토리(`my-project/`)는 컨테이너 역할만 하며 `.git` 파일/디렉토리를 생성하지 않습니다.

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
- **dirty check**: uncommitted 변경이 있거나 상태 확인에 실패한 worktree는 안전하게 스킵합니다.
- **no upstream skip**: upstream이 설정되지 않은 브랜치는 스킵합니다.

## Command Reference

| Command | Alias | Description |
|---------|-------|-------------|
| `wt init <url> [path]` | - | 새 bare repo + worktree 초기화 |
| `wt add <branch>` | `a` | worktree 추가 |
| `wt remove <identifier...> [--match <glob>] [--dry-run]` | `rm` | worktree 삭제, 로컬 브랜치는 기본 유지 (`-b`로 함께 삭제) |
| `wt status` | `st` | 모든 worktree 상태 확인 |
| `wt fetch` | `f` | `git fetch --all --prune` |
| `wt pull` | `p` | fetch + ff-only (기본) |
| `wt pull --rebase` | `p -r` | fetch + rebase |
| `wt list` | `ls` | worktree 목록 |
| `wt upstream` | `up` | upstream 자동 설정 |

## Exit Codes

`status`, `pull`, `upstream`, `remove`는 다음 규약을 따릅니다:

| Code | 의미 |
|------|------|
| `0` | 모든 대상 성공 (요청한 worktree/branch/remote 작업 완료) |
| `1` | 사용 오류 또는 치명적 상황 (worktree 없음, 매칭 없음, 사용자 중단, `--remote`를 `-b` 없이 사용) |
| `2` | 부분 완료 (일부 `SKIP`/`WARN(kept)`/`FAIL`, 또는 매칭되지 않은 identifier/pattern 존재) |

`status`는 dirty worktree가 있으면 `2`, `remove`는 보존된 브랜치(`kept`)가 있어도 `2`를 반환합니다.

## Requirements

- Python 3.9+
- Git 2.15+ (worktree support)
- Git 2.38+ (`wt remove -b`의 squash/rebase-merge 자동 감지 — `merge-tree --write-tree`. 미만 버전에서는 해당 브랜치가 보존되며 수동 삭제가 필요)

## License

MIT

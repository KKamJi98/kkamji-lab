# pull-request-jump (pr)

Open GitHub/Bitbucket Cloud pull request pages from the CLI.

## Install

```bash
uv tool install .
```

Editable install for local development:

```bash
uv tool install --editable .
```

Uninstall:

```bash
uv tool uninstall pull-request-jump
```

## Usage

```bash
# Open PR page for current branch (auto-detect provider)
pr open

# Use a specific remote
pr open --remote origin

# Override base or head branch
pr open --base main --head feature/my-branch

# Force provider if auto-detection fails
pr open --provider github
pr open --provider bitbucket

# Print URL without opening the browser
pr open --print
```

Notes:
- Run inside a git repository with the target remote configured.
- For Bitbucket Cloud, `--base` adds a `dest` query parameter as a best-effort
  preselection. If the UI ignores it, choose the destination branch manually.

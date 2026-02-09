# pull-request-jump (prj)

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
prj open

# Use a specific remote
prj open --remote origin

# Override base or head branch
prj open --base main --head feature/my-branch

# Force provider if auto-detection fails
prj open --provider github
prj open --provider bitbucket

# Print URL without opening the browser
prj open --print
```

Notes:
- Run inside a git repository with the target remote configured.
- For Bitbucket Cloud, `--base` adds a `dest` query parameter as a best-effort
  preselection. If the UI ignores it, choose the destination branch manually.

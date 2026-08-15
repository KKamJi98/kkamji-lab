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

# Override target (merge into) or source (merge from) branch
# short flags: -t/--target, -s/--source
prj open --target main --source feature/my-branch
prj open -t main -s feature/my-branch

# Force provider if auto-detection fails
prj open --provider github
prj open --provider bitbucket

# Print URL without opening the browser
prj open --print
```

Notes:
- Run inside a git repository with the target remote configured.
- For Bitbucket Cloud, `--target` adds a `dest` query parameter as a best-effort
  preselection. If the UI ignores it, choose the destination branch manually.

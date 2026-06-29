# Last Agent Run

- Tool created: gcloud-pick (gp)
- Purpose: switch gcloud CLI auth + ADC together, per-shell, synced.
- Modules: config.py (configs/accounts/ADC paths + resolution), shell.py (export/unset + shared profile), cli.py (picker + --login).
- Verify: `uv run ruff check . && uv run ruff format --check . && uv run pytest`
- Shell glue: gp() in ~/.zsh_aliases, gcloudpick_sync in ~/.zshrc.

# gcloud-pick (gp) Design

- Date: 2026-06-29
- Status: Approved design, pending implementation plan
- Location: `~/code/code-personal/kkamji-lab/tools/gcloud-pick/`
- Sibling/template: `kkamji-lab/tools/kube-pick`

## 1. Purpose

A `gp` CLI (Python uv tool, mirroring `kube-pick`/`aws-pick`) that switches the
gcloud identity used by BOTH systems at once, per-shell and synced across panes:

1. gcloud CLI auth - the active configuration's account/project
2. ADC (Application Default Credentials) - the identity used by SDKs and Terraform

The goal is that the CLI identity and the ADC identity never silently diverge.

## 2. Background / Why

gcloud has two independent auth systems:

- gcloud CLI commands use the active configuration's `core.account`.
- SDKs / Terraform / client libraries use ADC, resolved from
  `GOOGLE_APPLICATION_CREDENTIALS` -> `~/.config/gcloud/application_default_credentials.json`.

These can drift apart (e.g. `gcloud config` switched to `infra` while ADC still
points at `ethan.kim`), causing SDK/Terraform writes against the wrong identity.

A companion starship module (`custom.gcloud_adc`, already shipped in
`kkamji-settings/terminal/starship`) shows a bold-red warning when the ADC account
diverges from the active gcloud auth account. `gp` is the tool that switches both
levers in lockstep, so in normal use the warning stays hidden; the warning remains
the safety net for any drift introduced outside `gp`.

Verified facts that this design relies on:

- starship's `gcloud` module respects `CLOUDSDK_ACTIVE_CONFIG_NAME` (per-shell switch
  is reflected in the prompt).
- `gcloud-adc-status.sh` (the warning helper) also respects `CLOUDSDK_ACTIVE_CONFIG_NAME`.
- `GOOGLE_APPLICATION_CREDENTIALS` is the highest-priority ADC source and accepts both
  `authorized_user` and `service_account` JSON.

## 3. Goals / Non-goals

Goals:

- `gp` interactive picker over gcloud configurations; `gp <config>` direct switch.
- Switch CLI auth (per-shell `CLOUDSDK_ACTIVE_CONFIG_NAME`) and ADC
  (`GOOGLE_APPLICATION_CREDENTIALS` -> per-account saved ADC file) together.
- Cross-pane sync via a shared profile file + a `precmd` hook (mirrors `awspick_sync`).
- `gp --login [config]` to create/refresh a per-account ADC file without manual copying.
- Package layout, tooling, and conventions consistent with `kube-pick`.

Non-goals (YAGNI for v1):

- Group/filter flags (`-f/--filter`, `--group-rules`) like aws-pick. Defer unless needed.
- Separate project/region switching beyond what the chosen configuration already carries.
- Editing `~/.zshrc` on each switch (aws-pick does this; we deliberately do NOT).
- Managing service-account ADC beyond detecting `client_email` (initial focus is user creds).

## 4. UX / Commands

Invoked through a shell wrapper: `gp() { eval "$(command gcloud-pick "$@")" }`.

- `gp` (no args): interactive picker.
  - Lists gcloud configurations as a numbered list to stderr: `name`, `account`,
    `project`, and an ADC-file-present marker.
  - Highlights the current config.
  - User selects by number or name (`input()`); `q`/`quit`/empty cancels.
  - On selection, prints export commands to stdout (the only stdout output).
- `gp <config>`: switch directly to a named configuration (no prompt).
- `gp --login [config]`: (re)create the per-account ADC file.
  - Runs `gcloud auth application-default login` (interactive browser).
  - Resolves the account the resulting ADC belongs to (token introspection).
  - Saves the ADC JSON to `~/.config/gcloud/adc/<account>.json` with mode 0600.
  - If `config` is given, verifies the resolved account equals that config's
    `core.account`; warns on mismatch.
- `gp --list`: deferred to a later iteration (the no-arg picker already shows the list);
  not in v1 scope.

All human-facing output (list, prompts, warnings, status) goes to stderr.
Only the `export`/`unset` lines go to stdout for `eval`.

## 5. What a switch emits

For a selected configuration `<config>` whose account is `<account>`:

```sh
export CLOUDSDK_ACTIVE_CONFIG_NAME="<config>"
export GOOGLE_APPLICATION_CREDENTIALS="<HOME>/.config/gcloud/adc/<account>.json"
```

If `<config>` has no saved ADC file at `~/.config/gcloud/adc/<account>.json`:

```sh
export CLOUDSDK_ACTIVE_CONFIG_NAME="<config>"
unset GOOGLE_APPLICATION_CREDENTIALS
```

plus a stderr warning suggesting `gp --login <config>`. Unsetting makes ADC fall
back to the default `application_default_credentials.json`; if that differs from
`<account>`, the starship warning surfaces the divergence (safe + visible).

Shell-specific formats follow aws-pick/kube-pick (bash/zsh `export NAME="v"`,
fish `set -gx NAME "v"` / `set -e NAME`).

## 6. Cross-pane sync

- Shared profile file: `~/.config/gcloudpick/profile`, two lines:
  - line 1: selected configuration name
  - line 2: resolved `GOOGLE_APPLICATION_CREDENTIALS` path, or empty if none
  - written atomically (tmp + `os.replace`), mirroring aws-pick's `write_shared_profile`.
- `gcloudpick_sync` precmd (shell glue, see section 8) reads this file each prompt and
  re-exports `CLOUDSDK_ACTIVE_CONFIG_NAME` and `GOOGLE_APPLICATION_CREDENTIALS`
  (or unsets the latter when line 2 is empty). This is the equivalent of `awspick_sync`.

Storing the resolved ADC path on line 2 keeps the precmd trivial and fast (no INI
parsing in the hot path).

## 7. Package layout (mirror kube-pick)

```
kkamji-lab/tools/gcloud-pick/
├── gcloud_pick/
│   ├── __init__.py        # __version__
│   ├── cli.py             # argparse, picker prompt, orchestration, --login
│   ├── config.py          # gcloud configurations (INI), accounts, ADC file discovery + account resolution
│   └── shell.py           # export/unset command generation, shared profile read/write, shell detection
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   └── test_shell.py
├── pyproject.toml         # hatchling + ruff + rich; [project.scripts] gcloud-pick = "gcloud_pick.cli:main"
├── README.md
└── LAST_AGENT_RUN.md      # per monorepo convention
```

`pyproject.toml` mirrors kube-pick: `requires-python = ">=3.9"`, `dependencies = ["rich>=13,<14"]`,
dev `pytest`+`ruff`, hatchling build backend, ruff lint/format config.

## 8. Module responsibilities

`config.py`:

- `gcloud_dir()` -> respects `CLOUDSDK_CONFIG`, default `~/.config/gcloud`.
- `list_configurations()` -> parse `configurations/config_*` (INI via `configparser`),
  return list of `{name, account, project}`.
- `current_config()` -> `CLOUDSDK_ACTIVE_CONFIG_NAME` or `active_config` file.
- `adc_path_for(account)` -> `~/.config/gcloud/adc/<account>.json`; `adc_exists(account)`.
- `resolve_adc_account(adc_file)` -> for `--login` verification:
  service_account -> `client_email`; authorized_user -> token introspection
  (`gcloud auth application-default print-access-token` then tokeninfo). Network only
  during `--login`, never in a switch.

`shell.py`:

- `detect_shell()`, multi-shell export/unset formatting (bash/zsh/fish).
- `generate_export_commands(config, adc_path_or_none, shell)`.
- `shared_profile_path()` = `~/.config/gcloudpick/profile`.
- `write_shared_profile(config, adc_path_or_none)` (atomic).

`cli.py`:

- argparse: optional positional `config`, `--login`, `--list`.
- numbered picker to stderr + `input()` selection (mirror aws-pick `get_profile_selection`).
- orchestration: resolve config -> account -> ADC path (warn if missing) ->
  write shared profile -> print exports.
- `--login` flow (section 4).

## 9. ADC file setup (`gp --login`)

1. Run `gcloud auth application-default login` (interactive).
2. Read the freshly written default `application_default_credentials.json`.
3. Resolve its account (`resolve_adc_account`).
4. Copy it to `~/.config/gcloud/adc/<account>.json`, `chmod 600`, parent dir `0700`.
5. If a `config` arg was passed, compare resolved account with that config's
   `core.account`; warn on mismatch (do not block).

ADC files hold long-lived refresh tokens; treat them at the same sensitivity as the
default ADC file (0600, never printed).

## 10. Shell glue (separate deliverable, in dotfiles / kkamji-settings)

Not part of the Python package. Added where `ap()`/`awspick_sync` live:

```zsh
function gp() { eval "$(command gcloud-pick "$@")" }

gcloudpick_sync() {
  local f="$HOME/.config/gcloudpick/profile"
  [ -f "$f" ] || return
  local cfg adc
  IFS= read -r cfg < "$f"
  adc="$(sed -n '2p' "$f")"
  [ -n "$cfg" ] && export CLOUDSDK_ACTIVE_CONFIG_NAME="$cfg"
  if [ -n "$adc" ]; then export GOOGLE_APPLICATION_CREDENTIALS="$adc"; else unset GOOGLE_APPLICATION_CREDENTIALS; fi
}
if [[ -z "${precmd_functions[(r)gcloudpick_sync]}" ]]; then
  precmd_functions+=(gcloudpick_sync)
fi
```

## 11. Error handling

- No configurations found -> error to stderr, exit 1, emit nothing on stdout.
- Invalid selection -> reprompt (interactive) / error (direct).
- Missing ADC file -> warn + `unset` fallback (section 5), still exit 0.
- `--login` failures (login aborted, account unresolved) -> error to stderr, exit 1,
  do not write a partial ADC file.
- Any unexpected exception -> log to stderr, exit 1, never emit malformed stdout.

## 12. Testing

- `test_config.py`: parse fixture `config_*` files (name/account/project), current-config
  resolution, ADC path derivation, `adc_exists`.
- `test_shell.py`: export/unset generation per shell, shared profile atomic write/read.
- `--login` and network introspection are mocked (no real gcloud/network in tests).
- Mirror kube-pick's `conftest.py` fixture style.

## 13. Verification

- `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`.
- Manual: `uv tool install --editable .`; add `gp()` + `gcloudpick_sync` to shell;
  `gp infra` then `gp default` switches both; starship prompt reflects the per-shell
  config; ADC warning hidden when aligned, red when forced to diverge.

## 14. Integration with existing starship work

No changes required to starship. The `custom.gcloud_adc` warning is the safety net;
`gp` keeps CLI and ADC aligned so it normally stays hidden. The monorepo `AGENTS.md`
directory structure + tools table must be updated to include `gcloud-pick`
(monorepo Hard Rule #6).

## 15. Open items deferred to the plan

- Exact `rich` rendering of the configuration list (columns, current marker).
- README content and `LAST_AGENT_RUN.md` initialization.

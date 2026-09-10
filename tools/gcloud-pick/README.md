# gcloud-pick (gp)

Switch the gcloud CLI auth (active configuration) and ADC (Application Default
Credentials) identity together, per-shell and synced across panes.

## Why

gcloud has two independent auth systems: the CLI uses the active configuration's
account; SDKs/Terraform use ADC. They can silently diverge and cause wrong-account
writes. `gp` switches both in lockstep. The starship `custom.gcloud_adc` module
warns (red) when they drift anyway.

## Install

```bash
uv tool install --editable .
```

With the shared `kkamji-settings` dotfiles, load the wrapper and completion after
`compinit`. The wrapper reads a data-only state record and never evaluates CLI
output as shell code. The editable install makes source fixes effective immediately.

```zsh
# ~/.zshrc (kkamji-settings-managed ~/.zsh_functions)
source ~/.zsh_functions

# ~/.zshrc
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

## Usage

```bash
gp                 # interactive picker over gcloud configurations
gp infra           # switch directly to the 'infra' configuration
gp login           # CLI + ADC login for the current configuration
gp login infra     # CLI + ADC login for the exact 'infra' configuration
gp --login infra   # equivalent spelling
gp --help          # -h and -help also work
gp -- login        # switch to a configuration literally named 'login'
```

`login` uses `gcloud auth login ACCOUNT --configuration CONFIG --update-adc`.
Both the CLI credential store and default ADC are updated, then the matching ADC
is saved per account and the shell/shared profile switches to the selected config.
An existing configuration with `core/account` is required. Unknown configs,
authentication failures and ADC identity mismatches return nonzero without
switching the shared profile. The gcloud login itself can already have updated
its credential store/default ADC before a later identity check fails.

This replaces the old `--login` behavior, which ran only
`gcloud auth application-default login`. See the
[gcloud auth login reference](https://docs.cloud.google.com/sdk/gcloud/reference/auth/login).

Tab completion supports configuration names, `login`, `--login`, help and version
for both `gp` and `gcloud-pick`. Names are read from local configuration filenames
on each Tab, honoring `CLOUDSDK_CONFIG`, without a gcloud process or network call.

Each switch sets `CLOUDSDK_ACTIVE_CONFIG_NAME` and `GOOGLE_APPLICATION_CREDENTIALS`
(to `~/.config/gcloud/adc/<account>.json`), or unsets the latter when no saved ADC
file exists yet.

If no per-account ADC file is found on switch, `gp` will ask interactively whether
to run the combined CLI/ADC login immediately.
Decline or run in a non-interactive context to fall back with a warning instead.

## ADC files

`gp --login` saves the ADC credential to `~/.config/gcloud/adc/<account>.json`
(mode 0600). These hold long-lived refresh tokens; treat them like the default ADC
file.

## Validation and rollback

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
# From kkamji-settings; requires zsh and tmux, uses isolated fake configuration:
zsh shell/scripts/test-gp.zsh
```

Reload existing terminals with `source ~/.zsh_functions` or open a new terminal.
To roll back this fix, restore the previous `cli.py`, `shell/zsh_aliases`, and
`shell/zsh_functions` together and open a fresh shell. Tests do not authenticate
real accounts; browser authorization and live credential validity need a user login.

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

Add the shell glue (zsh) to your dotfiles:

```zsh
# ~/.zsh_aliases
function gp() { eval "$(command gcloud-pick "$@")" }

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
gp --login         # ADC login, save the per-account ADC file
gp --login infra   # ADC login and verify it matches 'infra' account
```

Each switch sets `CLOUDSDK_ACTIVE_CONFIG_NAME` and `GOOGLE_APPLICATION_CREDENTIALS`
(to `~/.config/gcloud/adc/<account>.json`), or unsets the latter when no saved ADC
file exists yet.

If no per-account ADC file is found on switch, `gp` will ask interactively whether
to run the ADC login immediately (keeping CLI auth and ADC matched in one step).
Decline or run in a non-interactive context to fall back with a warning instead.

## ADC files

`gp --login` saves the ADC credential to `~/.config/gcloud/adc/<account>.json`
(mode 0600). These hold long-lived refresh tokens; treat them like the default ADC
file.

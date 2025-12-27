# Kube Pick

A simple CLI tool to easily switch kubeconfig files in your shell environment.

## Installation

```bash
# Install from the current checkout as a global tool
uv tool install .

# Keep it editable if you want code changes to take effect immediately
uv tool install --editable .

# Upgrade an existing installation (reinstall with latest changes)
uv tool install --upgrade .

# Editable + upgrade: reinstall in editable mode so code changes apply immediately
uv tool install --editable --upgrade .
```

## Usage

```bash
# Interactive mode - select kubeconfig files
kubepick

# List available kubeconfig files
kubepick -l

# Show current KUBECONFIG setting
kubepick -c

# Apply to current shell
eval "$(kubepick)"
```

## Alias Setup

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Function to apply kubepick selection to current shell
function kp() {
    eval "$(command kubepick)"
}
```

For fish shell, add to `~/.config/fish/config.fish`:

```fish
function kp
    eval (command kubepick)
end
```

## Features

- Lists all kubeconfig files in `~/.kube` directory
- Includes files whose names contain `config` (excluding backups)
- Supports multiple selection (comma or space separated)
- Select all configs by entering `all`
- Updates shell rc file (`~/.zshrc`, `~/.bashrc`, etc.)
- Creates automatic backups before modifications
- Shows currently active configurations

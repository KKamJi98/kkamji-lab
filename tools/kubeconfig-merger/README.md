# kubeconfig-merger

Merge multiple kubeconfig files into a single output file.

## Installation

```bash
uv tool install .
```

## Usage

```bash
# Merge two kubeconfig files into ~/.kube/config
kubeconfig-merger --merge ~/.kube/config ~/.kube/config-dev --kubeconfig ~/.kube/config

# Interactive selection from ~/.kube
kubeconfig-merger --select

# Interactive selection from a custom directory
kubeconfig-merger --select --kube-dir ~/kubeconfigs

# Override current-context in the output
kubeconfig-merger --current-context my-context

# Dry-run (no file changes)
kubeconfig-merger --dry-run
```

## Notes

- Backups are created in `~/.kube/config_backup`.
- Interactive selection scans `~/.kube` for files containing `config` (excluding backups).
- Duplicate names are resolved by **last file wins**.

# kubeconfig-cleaner

Clean unused clusters/users from kubeconfig files after contexts are removed, and optionally
merge multiple kubeconfig files into a single output.

## Installation

```bash
uv tool install .
```

## Usage

```bash
# Clean the default kubeconfig (~/.kube/config)
kubeconfig-cleaner

# Clean a specific kubeconfig
kubeconfig-cleaner --kubeconfig ~/.kube/config-dev

# Dry-run (no file changes)
kubeconfig-cleaner --dry-run

# Allow pruning when no contexts remain
kubeconfig-cleaner --force-empty
```

## Notes

- Backups are created in `~/.kube/config_backup`.
- For merging multiple configs, use `kubeconfig-merger` first and then run this cleaner.

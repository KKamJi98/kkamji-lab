#!/bin/bash
set -euo pipefail

# ==============================================================================
# Golden Image Bootstrap Script
#
# This script configures the instance for a Golden Image.
# It includes examples for:
# 1. IPVS setup (for kube-proxy)
# 2. Security hardening (simplified example of CIS benchmarks)
# ==============================================================================

echo ">>> [Bootstrap] Starting Golden Image setup..."

# ------------------------------------------------------------------------------
# 1. System Updates & Dependencies
# ------------------------------------------------------------------------------
echo ">>> [System] Updating packages..."
yum update -y --security
yum install -y bind-utils

# ------------------------------------------------------------------------------
# 2. Security Hardening (Example)
#    Purpose: Apply basic hardening. In production, reference full CIS scripts.
# ------------------------------------------------------------------------------
echo ">>> [Security] Applying basic hardening examples..."

# SSH: Disable Root Login
if grep -q "^PermitRootLogin" /etc/ssh/sshd_config; then
  sed -i 's/^PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
else
  echo "PermitRootLogin no" >> /etc/ssh/sshd_config
fi

# Kernel: Restrict access to kernel logs
echo "kernel.dmesg_restrict = 1" > /etc/sysctl.d/50-security.conf
sysctl -p /etc/sysctl.d/50-security.conf || true

# Audit: Add example audit rules (Simplified)
# Real production would have 100+ lines here.
cat <<EOF > /etc/audit/rules.d/golden-image.rules
# Example rules
-w /etc/group -p wa -k identity
-w /etc/passwd -p wa -k identity
-w /etc/sudoers -p wa -k scope
EOF

# Restart services if available
if command -v systemctl >/dev/null; then
  systemctl restart sshd || true
  systemctl restart auditd || true
fi

echo ">>> [Security] Hardening examples applied."

echo ">>> [Bootstrap] Setup complete."

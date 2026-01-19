#!/usr/bin/env bash
set -euo pipefail
IFS=$'\n\t'

usage() {
  cat <<'USAGE'
Usage:
  verify-ami-ssm.sh -i instance-id [-r region] [-p profile]

Options:
  -i  EC2 instance ID (required)
  -r  AWS region (default: ap-northeast-2)
  -p  AWS profile (optional)

This script runs an SSM command to verify AMI provisioning.
USAGE
}

instance_id=""
region="ap-northeast-2"
profile=""

while getopts ":i:r:p:h" opt; do
  case "$opt" in
    i) instance_id="$OPTARG" ;;
    r) region="$OPTARG" ;;
    p) profile="$OPTARG" ;;
    h)
      usage
      exit 0
      ;;
    \?)
      echo "Unknown option: -$OPTARG" >&2
      usage
      exit 1
      ;;
  esac
done

if [ -z "$instance_id" ]; then
  echo "Error: -i instance-id is required." >&2
  usage
  exit 1
fi

aws_args=("--region" "$region")
if [ -n "$profile" ]; then
  aws_args+=("--profile" "$profile")
fi

REMOTE_SCRIPT=$(cat <<'CMDS'
#!/bin/bash
set -euo pipefail

#==============================================================================
# AMI Security Verification Script
# Based on: inspector.sh, ipvs.sh
#==============================================================================

# Counters
PASS=0
FAIL=0
WARN=0

# Category counters
SYSTEM_PASS=0; SYSTEM_FAIL=0; SYSTEM_WARN=0
SSH_PASS=0; SSH_FAIL=0; SSH_WARN=0
PKG_PASS=0; PKG_FAIL=0; PKG_WARN=0
SHELL_PASS=0; SHELL_FAIL=0; SHELL_WARN=0
PAM_PASS=0; PAM_FAIL=0; PAM_WARN=0
PERM_PASS=0; PERM_FAIL=0; PERM_WARN=0
CIS_PASS=0; CIS_FAIL=0; CIS_WARN=0
AUDIT_PASS=0; AUDIT_FAIL=0; AUDIT_WARN=0

# Store FAIL/WARN messages
FAIL_LIST=""
WARN_LIST=""

#------------------------------------------------------------------------------
# Output functions
#------------------------------------------------------------------------------
header() {
  printf "\n===================================================================\n"
  printf "  %s\n" "$1"
  printf "===================================================================\n"
}

section() {
  printf "\n[%s]\n" "$1"
}

pass() {
  PASS=$((PASS + 1))
  eval "${2}_PASS=\$((${2}_PASS + 1))"
  printf "  [PASS] %s\n" "$1"
}

fail() {
  FAIL=$((FAIL + 1))
  eval "${2}_FAIL=\$((${2}_FAIL + 1))"
  printf "  [FAIL] %s\n" "$1"
  FAIL_LIST="${FAIL_LIST}[${2}] $1
"
}

warn() {
  WARN=$((WARN + 1))
  eval "${2}_WARN=\$((${2}_WARN + 1))"
  printf "  [WARN] %s\n" "$1"
  WARN_LIST="${WARN_LIST}[${2}] $1
"
}

info() {
  printf "  - %s\n" "$1"
}

#==============================================================================
# SYSTEM INFO
#==============================================================================
header "SYSTEM INFORMATION"

section "OS Release"
if [ -f /etc/os-release ]; then
  source /etc/os-release
  info "Name: ${NAME:-unknown}"
  info "Version: ${VERSION:-unknown}"
  pass "OS release file present" "SYSTEM"
else
  fail "OS release file missing" "SYSTEM"
fi

section "Kernel"
info "$(uname -r)"

#==============================================================================
# INSPECTOR.SH - SSH Configuration
#==============================================================================
header "SSH SECURITY (inspector.sh)"

section "PermitRootLogin"
if command -v sshd >/dev/null 2>&1; then
  value="$(sshd -T 2>/dev/null | awk 'tolower($1)=="permitrootlogin"{print $2}')"
  if [ "$value" = "no" ]; then
    pass "PermitRootLogin is 'no'" "SSH"
  else
    fail "PermitRootLogin is '${value:-unknown}' (expected: no)" "SSH"
  fi
else
  warn "sshd command not found" "SSH"
fi

#==============================================================================
# INSPECTOR.SH - Package Verification
#==============================================================================
header "PACKAGES (inspector.sh)"

section "bind-utils"
if rpm -q bind-utils >/dev/null 2>&1; then
  pass "bind-utils installed ($(rpm -q bind-utils --qf '%{VERSION}'))" "PKG"
else
  fail "bind-utils not installed" "PKG"
fi

#==============================================================================
# INSPECTOR.SH - Shell Security
#==============================================================================
header "SHELL SECURITY (inspector.sh)"

section "umask Configuration"
for file in /etc/bashrc /etc/profile; do
  if grep -qF 'umask 027' "$file" 2>/dev/null; then
    pass "umask 027 in ${file}" "SHELL"
  else
    fail "umask 027 not in ${file}" "SHELL"
  fi
done

section "Session Timeout (TMOUT)"
for file in /etc/bashrc /etc/profile; do
  if grep -qF 'TMOUT=600' "$file" 2>/dev/null; then
    pass "TMOUT=600 in ${file}" "SHELL"
  else
    fail "TMOUT=600 not in ${file}" "SHELL"
  fi
done

#==============================================================================
# INSPECTOR.SH - PAM Configuration
#==============================================================================
header "PAM SECURITY (inspector.sh)"

section "Wheel Group Restriction"
if grep -qF 'auth required pam_wheel.so use_uid' /etc/pam.d/su 2>/dev/null; then
  pass "pam_wheel.so use_uid in /etc/pam.d/su" "PAM"
else
  fail "pam_wheel.so use_uid not in /etc/pam.d/su" "PAM"
fi

#==============================================================================
# INSPECTOR.SH - File Permissions
#==============================================================================
header "FILE PERMISSIONS (inspector.sh)"

section "/etc/crontab"
if [ -f /etc/crontab ]; then
  owner=$(stat -c '%U:%G' /etc/crontab 2>/dev/null)
  perm=$(stat -c '%a' /etc/crontab 2>/dev/null)
  if [ "$owner" = "root:root" ]; then
    pass "/etc/crontab owner is root:root" "PERM"
  else
    fail "/etc/crontab owner is ${owner} (expected: root:root)" "PERM"
  fi
  # og-rwx means 600 or less
  if [ "$perm" = "600" ] || [ "$perm" = "400" ]; then
    pass "/etc/crontab permission is ${perm} (og-rwx)" "PERM"
  else
    fail "/etc/crontab permission is ${perm} (expected: 600 or stricter)" "PERM"
  fi
else
  fail "/etc/crontab not found" "PERM"
fi

section "Cron Directories"
for dir in /etc/cron.hourly /etc/cron.daily /etc/cron.weekly /etc/cron.monthly; do
  if [ -d "$dir" ]; then
    owner=$(stat -c '%U:%G' "$dir" 2>/dev/null)
    perm=$(stat -c '%a' "$dir" 2>/dev/null)
    if [ "$owner" = "root:root" ]; then
      pass "${dir} owner is root:root" "PERM"
    else
      fail "${dir} owner is ${owner} (expected: root:root)" "PERM"
    fi
    # og-rwx on directory means 700
    if [ "$perm" = "700" ]; then
      pass "${dir} permission is ${perm} (og-rwx)" "PERM"
    else
      fail "${dir} permission is ${perm} (expected: 700)" "PERM"
    fi
  else
    warn "${dir} not found" "PERM"
  fi
done

section "/var/log Permissions"
# Check sample log files for g-wx,o-rwx
for logfile in /var/log/messages /var/log/secure /var/log/audit/audit.log; do
  if [ -f "$logfile" ]; then
    perm=$(stat -c '%a' "$logfile" 2>/dev/null)
    # g-wx,o-rwx means group has no write/execute, others have nothing
    # Valid perms: 600, 640, 400, 440
    if [ "$perm" = "600" ] || [ "$perm" = "640" ] || [ "$perm" = "400" ] || [ "$perm" = "440" ]; then
      pass "${logfile} permission is ${perm} (g-wx,o-rwx)" "PERM"
    else
      fail "${logfile} permission is ${perm} (expected: g-wx,o-rwx)" "PERM"
    fi
  fi
done

#==============================================================================
# INSPECTOR.SH - CIS Module Blacklist
#==============================================================================
header "CIS MODULE BLACKLIST (inspector.sh)"

section "Disabled Kernel Modules"
if [ -f /etc/modprobe.d/CIS.conf ]; then
  pass "/etc/modprobe.d/CIS.conf exists" "CIS"
  for mod in cramfs dccp freevxfs hfs hfsplus jffs2 rds sctp squashfs tipc udf vfat; do
    if grep -qF "install ${mod} /bin/true" /etc/modprobe.d/CIS.conf 2>/dev/null; then
      pass "Module ${mod} disabled" "CIS"
    else
      fail "Module ${mod} not disabled" "CIS"
    fi
  done
else
  fail "/etc/modprobe.d/CIS.conf missing" "CIS"
  for mod in cramfs dccp freevxfs hfs hfsplus jffs2 rds sctp squashfs tipc udf vfat; do
    fail "Module ${mod} not disabled (CIS.conf missing)" "CIS"
  done
fi

#==============================================================================
# INSPECTOR.SH - Audit Configuration
#==============================================================================
header "AUDIT CONFIGURATION (inspector.sh)"

section "Auditd Service"
if command -v systemctl >/dev/null 2>&1; then
  status=$(systemctl is-active auditd 2>/dev/null || true)
  if [ "$status" = "active" ]; then
    pass "auditd service is active" "AUDIT"
  else
    fail "auditd service is ${status:-unknown}" "AUDIT"
  fi
else
  warn "systemctl not available" "AUDIT"
fi

section "Audit Rules File"
AUDIT_RULES="/etc/audit/rules.d/audit.rules"
if [ -f "$AUDIT_RULES" ]; then
  pass "${AUDIT_RULES} exists" "AUDIT"
else
  fail "${AUDIT_RULES} missing" "AUDIT"
fi

section "Login/Session Audit Rules"
check_audit_rule() {
  rule="$1"
  short_rule=$(echo "$rule" | cut -c1-40)
  if grep -qF -- "$rule" "$AUDIT_RULES" 2>/dev/null; then
    pass "Rule: ${short_rule}..." "AUDIT"
  else
    fail "Missing: ${short_rule}..." "AUDIT"
  fi
}
check_audit_rule "-w /var/log/lastlog -p wa -k logins"
check_audit_rule "-w /var/run/faillock/ -p wa -k logins"
check_audit_rule "-w /var/log/sudo.log -p wa -k actions"
check_audit_rule "-w /var/run/utmp -p wa -k session"
check_audit_rule "-w /var/log/wtmp -p wa -k logins"
check_audit_rule "-w /var/log/btmp -p wa -k logins"

section "Sudoers Audit Rules (scope)"
check_audit_exact() {
  rule="$1"
  if grep -qF -- "$rule" "$AUDIT_RULES" 2>/dev/null; then
    pass "Rule: ${rule}" "AUDIT"
  else
    fail "Missing: ${rule}" "AUDIT"
  fi
}
check_audit_exact "-w /etc/sudoers -p wa -k scope"
check_audit_exact "-w /etc/sudoers.d/ -p wa -k scope"

section "Permission Modification Audit Rules (perm_mod)"
# Check for perm_mod rules (simplified check)
if grep -q 'perm_mod' "$AUDIT_RULES" 2>/dev/null; then
  count=$(grep -c 'perm_mod' "$AUDIT_RULES" 2>/dev/null || echo 0)
  if [ "$count" -ge 6 ]; then
    pass "perm_mod rules present (${count} rules)" "AUDIT"
  else
    warn "perm_mod rules incomplete (${count}/6 rules)" "AUDIT"
  fi
else
  fail "perm_mod rules missing" "AUDIT"
fi

section "File Access Audit Rules (access)"
if grep -q '\-k access' "$AUDIT_RULES" 2>/dev/null; then
  count=$(grep -c '\-k access' "$AUDIT_RULES" 2>/dev/null || echo 0)
  if [ "$count" -ge 4 ]; then
    pass "access rules present (${count} rules)" "AUDIT"
  else
    warn "access rules incomplete (${count}/4 rules)" "AUDIT"
  fi
else
  fail "access rules missing" "AUDIT"
fi

section "Mount Audit Rules (mounts)"
if grep -q '\-k mounts' "$AUDIT_RULES" 2>/dev/null; then
  pass "mounts rules present" "AUDIT"
else
  fail "mounts rules missing" "AUDIT"
fi

section "File Deletion Audit Rules (delete)"
if grep -q '\-k delete' "$AUDIT_RULES" 2>/dev/null; then
  pass "delete rules present" "AUDIT"
else
  fail "delete rules missing" "AUDIT"
fi

section "Kernel Module Audit Rules (modules)"
check_audit_exact "-w /sbin/insmod -p x -k modules"
check_audit_exact "-w /sbin/rmmod -p x -k modules"
check_audit_exact "-w /sbin/modprobe -p x -k modules"
if grep -q 'init_module.*delete_module.*modules' "$AUDIT_RULES" 2>/dev/null; then
  pass "init_module/delete_module rules present" "AUDIT"
else
  fail "init_module/delete_module rules missing" "AUDIT"
fi

section "Time Change Audit Rules (time-change)"
if grep -q '\-k time-change' "$AUDIT_RULES" 2>/dev/null; then
  count=$(grep -c '\-k time-change' "$AUDIT_RULES" 2>/dev/null || echo 0)
  if [ "$count" -ge 5 ]; then
    pass "time-change rules present (${count} rules)" "AUDIT"
  else
    warn "time-change rules incomplete (${count}/5 rules)" "AUDIT"
  fi
else
  fail "time-change rules missing" "AUDIT"
fi

section "System Locale Audit Rules (system-locale)"
check_audit_exact "-w /etc/issue -p wa -k system-locale"
check_audit_exact "-w /etc/issue.net -p wa -k system-locale"
check_audit_exact "-w /etc/hosts -p wa -k system-locale"

section "SELinux/MAC Audit Rules (MAC-policy)"
check_audit_exact "-w /etc/selinux/ -p wa -k MAC-policy"
check_audit_exact "-w /usr/share/selinux/ -p wa -k MAC-policy"

section "Identity Audit Rules"
IDENTITY_RULES="/etc/audit/rules.d/identity.rules"
if [ -f "$IDENTITY_RULES" ]; then
  pass "${IDENTITY_RULES} exists" "AUDIT"
  for entry in /etc/group /etc/passwd /etc/gshadow /etc/shadow /etc/security/opasswd; do
    if grep -qF -- "$entry" "$IDENTITY_RULES" 2>/dev/null; then
      pass "Identity rule for ${entry}" "AUDIT"
    else
      fail "Missing identity rule for ${entry}" "AUDIT"
    fi
  done
else
  fail "${IDENTITY_RULES} missing" "AUDIT"
fi

#==============================================================================
# SUMMARY
#==============================================================================
header "VERIFICATION SUMMARY"

printf "\n"
printf "Results by Category:\n"
printf "+----------------+------+------+------+\n"
printf "| %-14s | PASS | FAIL | WARN |\n" "Category"
printf "+----------------+------+------+------+\n"
printf "| %-14s | %4d | %4d | %4d |\n" "SYSTEM" "$SYSTEM_PASS" "$SYSTEM_FAIL" "$SYSTEM_WARN"
printf "| %-14s | %4d | %4d | %4d |\n" "SSH" "$SSH_PASS" "$SSH_FAIL" "$SSH_WARN"
printf "| %-14s | %4d | %4d | %4d |\n" "PKG" "$PKG_PASS" "$PKG_FAIL" "$PKG_WARN"
printf "| %-14s | %4d | %4d | %4d |\n" "SHELL" "$SHELL_PASS" "$SHELL_FAIL" "$SHELL_WARN"
printf "| %-14s | %4d | %4d | %4d |\n" "PAM" "$PAM_PASS" "$PAM_FAIL" "$PAM_WARN"
printf "| %-14s | %4d | %4d | %4d |\n" "PERM" "$PERM_PASS" "$PERM_FAIL" "$PERM_WARN"
printf "| %-14s | %4d | %4d | %4d |\n" "CIS" "$CIS_PASS" "$CIS_FAIL" "$CIS_WARN"
printf "| %-14s | %4d | %4d | %4d |\n" "AUDIT" "$AUDIT_PASS" "$AUDIT_FAIL" "$AUDIT_WARN"
printf "+----------------+------+------+------+\n"
printf "| %-14s | %4d | %4d | %4d |\n" "TOTAL" "$PASS" "$FAIL" "$WARN"
printf "+----------------+------+------+------+\n"

# Show FAIL & WARN list
if [ -n "$FAIL_LIST" ] || [ -n "$WARN_LIST" ]; then
  printf "\n"
  printf "FAIL & WARN List:\n"
  printf '%s\n' '-------------------------------------------------------------------'
  if [ -n "$FAIL_LIST" ]; then
    echo -n "$FAIL_LIST"
  fi
  if [ -n "$WARN_LIST" ]; then
    echo -n "$WARN_LIST"
  fi
fi

# Final result
if [ "$FAIL" -eq 0 ] && [ "$WARN" -eq 0 ]; then
  FINAL_STATUS="PASS"
elif [ "$FAIL" -eq 0 ]; then
  FINAL_STATUS="WARN"
else
  FINAL_STATUS="FAIL"
fi

printf "\n"
printf "===================================================================\n"
printf "  FINAL RESULT\n"
printf "===================================================================\n"
printf "PASS: %d\n" "$PASS"
printf "FAIL: %d\n" "$FAIL"
printf "WARN: %d\n" "$WARN"
printf "RESULT: %s\n" "$FINAL_STATUS"
CMDS
)

if command -v python3 >/dev/null 2>&1; then
  py=python3
elif command -v python >/dev/null 2>&1; then
  py=python
else
  echo "python3 or python is required to build SSM parameters JSON." >&2
  exit 1
fi

params_file=$(mktemp)
trap 'rm -f "$params_file"' EXIT

export REMOTE_SCRIPT
"$py" - <<'PY' > "$params_file"
import json
import os
import sys

def sh_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"

script_text = os.environ.get("REMOTE_SCRIPT", "")
if not script_text.strip():
    print("REMOTE_SCRIPT is empty; cannot build SSM command script.", file=sys.stderr)
    sys.exit(1)

script = script_text.splitlines()
commands = [
    "echo 'SSM_OUTPUT_TEST'",
    "rm -f /tmp/verify-ami.sh",
]
for line in script:
    commands.append("printf '%s\\n' {} >> /tmp/verify-ami.sh".format(sh_single_quote(line)))
commands += [
    "chmod +x /tmp/verify-ami.sh",
    "bash /tmp/verify-ami.sh",
]
json.dump({"commands": commands}, sys.stdout)
PY

command_id=$(aws ssm send-command \
  "${aws_args[@]}" \
  --document-name "AWS-RunShellScript" \
  --targets "Key=InstanceIds,Values=${instance_id}" \
  --comment "verify-ami" \
  --parameters "file://${params_file}" \
  --query "Command.CommandId" \
  --output text)

echo "CommandId: ${command_id}"

echo "Waiting for command completion..."
aws ssm wait command-executed \
  "${aws_args[@]}" \
  --command-id "$command_id" \
  --instance-id "$instance_id"

status=$(aws ssm get-command-invocation \
  "${aws_args[@]}" \
  --command-id "$command_id" \
  --instance-id "$instance_id" \
  --query "Status" \
  --output text)

echo "Status: ${status}"

stdout=$(aws ssm get-command-invocation \
  "${aws_args[@]}" \
  --command-id "$command_id" \
  --instance-id "$instance_id" \
  --query "StandardOutputContent" \
  --output text)

stderr=$(aws ssm get-command-invocation \
  "${aws_args[@]}" \
  --command-id "$command_id" \
  --instance-id "$instance_id" \
  --query "StandardErrorContent" \
  --output text)

echo "=============================================================="
echo "                      VERIFICATION OUTPUT"
echo "=============================================================="
if [ -n "$stdout" ] && [ "$stdout" != "None" ]; then
  echo "$stdout"
else
  echo "(empty)"
fi

if [ -n "$stderr" ] && [ "$stderr" != "None" ]; then
  echo ""
  echo "--- stderr ---"
  echo "$stderr"
fi

if { [ -z "$stdout" ] || [ "$stdout" = "None" ]; } && { [ -z "$stderr" ] || [ "$stderr" = "None" ]; }; then
  echo "--- invocation ---"
  aws ssm get-command-invocation \
    "${aws_args[@]}" \
    --command-id "$command_id" \
    --instance-id "$instance_id" \
    --query '{StatusDetails:StatusDetails,ResponseCode:ResponseCode,StandardOutputUrl:StandardOutputUrl,StandardErrorUrl:StandardErrorUrl}' \
    --output json
fi

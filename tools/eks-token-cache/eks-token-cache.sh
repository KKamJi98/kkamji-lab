#!/bin/bash
# EKS 토큰 캐싱 스크립트 v2
# 토큰 내부 expirationTimestamp 기반 캐시 검증
# AWS credential fingerprint 기반 세션 변경 감지

set -euo pipefail

CLUSTER_NAME="${1:?cluster name required}"
REGION="${2:-ap-northeast-2}"
PROFILE_ARG="${3:-}"
PROFILE_KEY="${PROFILE_ARG:-${AWS_PROFILE:-}}"
SAFETY_MARGIN=60  # 만료 60초 전 갱신

CACHE_DIR="${HOME}/.kube/cache/eks-tokens"
# 캐시 키: 클러스터명 + 리전 + 프로파일 (프로파일별 토큰 분리)
CACHE_KEY="${CLUSTER_NAME}_${REGION}${PROFILE_KEY:+_${PROFILE_KEY}}"
CACHE_FILE="${CACHE_DIR}/${CACHE_KEY}.json"
META_FILE="${CACHE_FILE}.meta"

debug() { [[ "${EKS_TOKEN_DEBUG:-}" == "1" ]] && echo "[DEBUG] $*" >&2 || true; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing required command: $1" >&2
        exit 127
    }
}

require_cmd aws
require_cmd jq

# AWS credential fingerprint: 세션 파일의 mtime 조합
get_credential_fingerprint() {
    local fp=""

    # ~/.aws/cli/cache/session.db — STS 세션 갱신 시 업데이트
    local session_db="${HOME}/.aws/cli/cache/session.db"
    if [[ -f "$session_db" ]]; then
        if [[ "$(uname)" == "Darwin" ]]; then
            fp+="sdb:$(stat -f '%m' "$session_db" 2>/dev/null || echo 0)"
        else
            fp+="sdb:$(stat -c '%Y' "$session_db" 2>/dev/null || echo 0)"
        fi
    fi

    # ~/.aws/login/cache/ — aws login / aws sso login 시 업데이트
    local login_cache_dir="${HOME}/.aws/login/cache"
    if [[ -d "$login_cache_dir" ]]; then
        local latest_mtime="0"
        local mtime
        for f in "$login_cache_dir"/*.json; do
            [[ -f "$f" ]] || continue
            if [[ "$(uname)" == "Darwin" ]]; then
                mtime=$(stat -f '%m' "$f" 2>/dev/null || echo 0)
            else
                mtime=$(stat -c '%Y' "$f" 2>/dev/null || echo 0)
            fi
            [[ "$mtime" -gt "$latest_mtime" ]] && latest_mtime="$mtime"
        done
        fp+="|lc:${latest_mtime}"
    fi

    echo "$fp"
}

# 캐시 유효성: 토큰 내부 expirationTimestamp 기준 + credential fingerprint
is_cache_valid() {
    [[ ! -f "$CACHE_FILE" || ! -s "$CACHE_FILE" ]] && return 1

    # credential fingerprint 비교 (.meta 파일이 있는 경우만)
    if [[ -f "$META_FILE" ]]; then
        local saved_fp current_fp
        saved_fp=$(cat "$META_FILE" 2>/dev/null || true)
        current_fp=$(get_credential_fingerprint)
        if [[ -n "$saved_fp" && "$saved_fp" != "$current_fp" ]]; then
            debug "Credential fingerprint changed, invalidating cache"
            return 1
        fi
    fi

    local exp_time
    exp_time=$(jq -r '.status.expirationTimestamp // empty' "$CACHE_FILE" 2>/dev/null) || return 1
    [[ -z "$exp_time" ]] && return 1

    local exp_epoch now_epoch
    exp_epoch=$(jq -r '(.status.expirationTimestamp // empty) | fromdateiso8601? // empty' "$CACHE_FILE" 2>/dev/null || true)
    if [[ -z "$exp_epoch" || "$exp_epoch" == "null" ]]; then
        if [[ "$(uname)" == "Darwin" ]]; then
            # macOS: UTC 시간대로 파싱 (토큰 만료시간은 UTC, Z 형식만 지원)
            exp_epoch=$(TZ=UTC date -j -f '%Y-%m-%dT%H:%M:%SZ' "$exp_time" '+%s' 2>/dev/null) || return 1
        else
            exp_epoch=$(date -d "$exp_time" '+%s' 2>/dev/null) || return 1
        fi
    fi
    now_epoch=$(date '+%s')

    local remaining=$((exp_epoch - now_epoch))
    debug "Token expires in ${remaining}s (cluster: $CLUSTER_NAME)"

    [[ $remaining -gt $SAFETY_MARGIN ]]
}

umask 077
mkdir -p "$CACHE_DIR"
chmod 700 "$CACHE_DIR" 2>/dev/null || {
    echo "Warning: Failed to set permissions on $CACHE_DIR" >&2
}

# stale 임시 파일 정리 (5분 이상 된 .tmp.* 파일)
find "$CACHE_DIR" -name "*.tmp.*" -mmin +5 -delete 2>/dev/null || true

if is_cache_valid; then
    debug "Using cached token"
    cat "$CACHE_FILE"
    exit 0
fi

debug "Fetching new token for $CLUSTER_NAME"

# 새 토큰 발급
cmd=(aws eks get-token --cluster-name "$CLUSTER_NAME" --region "$REGION" --output json)
[[ -n "$PROFILE_ARG" ]] && cmd+=(--profile "$PROFILE_ARG")

tmp_file=$(mktemp "${CACHE_FILE}.tmp.XXXXXX")
cleanup() { rm -f "$tmp_file"; }
trap cleanup EXIT TERM PIPE

if ! "${cmd[@]}" > "$tmp_file"; then
    echo "Failed to get EKS token for $CLUSTER_NAME" >&2
    rm -f "$tmp_file"
    exit 1
fi

# 결과 검증
if ! jq -e '.status.token' "$tmp_file" >/dev/null 2>&1; then
    echo "Invalid token response for $CLUSTER_NAME" >&2
    rm -f "$tmp_file"
    exit 1
fi

mv -f "$tmp_file" "$CACHE_FILE"
chmod 600 "$CACHE_FILE" 2>/dev/null || {
    echo "Warning: Failed to set permissions on $CACHE_FILE" >&2
}

# credential fingerprint 저장
get_credential_fingerprint > "$META_FILE"
chmod 600 "$META_FILE" 2>/dev/null || true

trap - EXIT

cat "$CACHE_FILE"

#!/bin/bash
# EKS 토큰 캐싱 스크립트 v2
# 토큰 내부 expirationTimestamp 기반 캐시 검증

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

debug() { [[ "${EKS_TOKEN_DEBUG:-}" == "1" ]] && echo "[DEBUG] $*" >&2 || true; }

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "Missing required command: $1" >&2
        exit 127
    }
}

require_cmd aws
require_cmd jq

# 캐시 유효성: 토큰 내부 expirationTimestamp 기준
is_cache_valid() {
    [[ ! -f "$CACHE_FILE" || ! -s "$CACHE_FILE" ]] && return 1

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
chmod 700 "$CACHE_DIR" 2>/dev/null || true

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
trap cleanup EXIT

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
chmod 600 "$CACHE_FILE" 2>/dev/null || true
trap - EXIT

cat "$CACHE_FILE"

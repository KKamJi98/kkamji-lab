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
ERROR_CACHE_TTL="${EKS_TOKEN_ERROR_TTL:-30}"  # 에러 네거티브 캐시 TTL (초)

CACHE_DIR="${HOME}/.kube/cache/eks-tokens"
# 캐시 키: 클러스터명 + 리전 + 프로파일 (프로파일별 토큰 분리)
CACHE_KEY="${CLUSTER_NAME}_${REGION}${PROFILE_KEY:+_${PROFILE_KEY}}"
CACHE_FILE="${CACHE_DIR}/${CACHE_KEY}.json"
META_FILE="${CACHE_FILE}.meta"
ERROR_FILE="${CACHE_FILE}.error"

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

# AWS CLI stderr → 에러 유형 분류 + 사용자 조치 안내
classify_aws_error() {
    local stderr_text="$1"
    local error_type="unknown"
    local suggested_action="Run 'aws sts get-caller-identity' to check credentials"

    case "$stderr_text" in
        *"session has expired"*|*"token has expired"*|*"Token has expired"*|*"ExpiredToken"*)
            error_type="session_expired"
            if [[ -n "$PROFILE_KEY" ]]; then
                suggested_action="Run 'aws sso login --profile ${PROFILE_KEY}'"
            else
                suggested_action="Run 'aws sso login'"
            fi
            ;;
        *"profile"*"could not be found"*|*"profile"*"not found"*)
            error_type="profile_not_found"
            suggested_action="Check profile name in ~/.aws/config"
            ;;
        *"Unable to locate credentials"*|*"NoCredentialProviders"*|*"no credentials"*)
            error_type="no_credentials"
            if [[ -n "$PROFILE_KEY" ]]; then
                suggested_action="Run 'aws sso login --profile ${PROFILE_KEY}'"
            else
                suggested_action="Run 'aws configure' or 'aws sso login'"
            fi
            ;;
        *"AccessDenied"*|*"access denied"*|*"not authorized"*|*"UnauthorizedAccess"*)
            error_type="access_denied"
            suggested_action="Check IAM permissions for EKS cluster '${CLUSTER_NAME}'"
            ;;
        *"ResourceNotFoundException"*|*"cluster"*"not found"*)
            error_type="cluster_not_found"
            suggested_action="Verify cluster name '${CLUSTER_NAME}' and region '${REGION}'"
            ;;
        *"Could not connect"*|*"Connection refused"*|*"timed out"*|*"Network"*)
            error_type="network_error"
            suggested_action="Check network connectivity and AWS endpoint access"
            ;;
    esac

    echo "$error_type"
    echo "$suggested_action"
}

# 에러 네거티브 캐시 유효성 검증
is_error_cache_valid() {
    [[ ! -f "$ERROR_FILE" ]] && return 1

    # credential fingerprint 비교 → 변경 시 에러 캐시 삭제 (로그인 후 즉시 재시도)
    local saved_fp current_fp
    saved_fp=$(jq -r '.credential_fingerprint // empty' "$ERROR_FILE" 2>/dev/null) || return 1
    current_fp=$(get_credential_fingerprint)
    if [[ -n "$saved_fp" && "$saved_fp" != "$current_fp" ]]; then
        debug "Credential fingerprint changed, clearing error cache"
        rm -f "$ERROR_FILE"
        return 1
    fi

    # TTL 검증
    local cached_ts now_epoch age
    cached_ts=$(jq -r '.timestamp // 0' "$ERROR_FILE" 2>/dev/null) || return 1
    now_epoch=$(date '+%s')
    age=$((now_epoch - cached_ts))
    if [[ $age -gt $ERROR_CACHE_TTL ]]; then
        debug "Error cache expired (${age}s > ${ERROR_CACHE_TTL}s)"
        rm -f "$ERROR_FILE"
        return 1
    fi

    return 0
}

# 에러 캐시 저장
write_error_cache() {
    local error_type="$1"
    local error_message="$2"
    local suggested_action="$3"
    local now_epoch
    now_epoch=$(date '+%s')
    local fp
    fp=$(get_credential_fingerprint)

    jq -n \
        --argjson ts "$now_epoch" \
        --arg et "$error_type" \
        --arg em "$error_message" \
        --arg sa "$suggested_action" \
        --arg fp "$fp" \
        '{timestamp: $ts, error_type: $et, error_message: $em, suggested_action: $sa, credential_fingerprint: $fp}' \
        > "$ERROR_FILE" 2>/dev/null || return 0
    chmod 600 "$ERROR_FILE" 2>/dev/null || true
}

# 캐시된 에러 간략 출력
emit_cached_error() {
    local error_type suggested_action cached_ts now_epoch age
    error_type=$(jq -r '.error_type // "unknown"' "$ERROR_FILE" 2>/dev/null)
    suggested_action=$(jq -r '.suggested_action // ""' "$ERROR_FILE" 2>/dev/null)
    cached_ts=$(jq -r '.timestamp // 0' "$ERROR_FILE" 2>/dev/null)
    now_epoch=$(date '+%s')
    age=$((now_epoch - cached_ts))

    echo "[eks-token-cache] Auth failed for '${CLUSTER_NAME}' (${error_type} ${age}s ago). Run: ${suggested_action}" >&2
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

# stale 파일 정리: 임시 파일 (5분+), 에러 캐시 (10분+)
find "$CACHE_DIR" -name "*.tmp.*" -mmin +5 -delete 2>/dev/null || true
find "$CACHE_DIR" -name "*.error" -mmin +10 -delete 2>/dev/null || true

# 에러 캐시 hit → 중복 에러 억제
if is_error_cache_valid; then
    debug "Error cache hit, suppressing duplicate"
    emit_cached_error
    exit 1
fi

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
err_tmp=$(mktemp "${CACHE_FILE}.tmp.XXXXXX")
cleanup() { rm -f "$tmp_file" "$err_tmp"; }
trap cleanup EXIT TERM PIPE

if ! "${cmd[@]}" > "$tmp_file" 2>"$err_tmp"; then
    local_stderr=$(cat "$err_tmp" 2>/dev/null || true)
    debug "AWS CLI failed: $local_stderr"

    # 에러 분류
    {
        read -r error_type
        read -r suggested_action
    } < <(classify_aws_error "$local_stderr")

    # 에러 캐시 저장
    write_error_cache "$error_type" "$local_stderr" "$suggested_action"

    # 상세 에러 출력 (첫 실패)
    echo "[eks-token-cache] Auth failed for cluster '${CLUSTER_NAME}'" >&2
    if [[ -n "$local_stderr" ]]; then
        echo "  Error: ${local_stderr}" >&2
    fi
    echo "  Action: ${suggested_action}" >&2

    rm -f "$tmp_file" "$err_tmp"
    exit 1
fi
rm -f "$err_tmp"

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

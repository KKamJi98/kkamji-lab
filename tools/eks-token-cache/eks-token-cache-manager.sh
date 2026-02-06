#!/bin/bash
# EKS 토큰 캐시 관리 스크립트
# 사용법: eks-token-cache-manager.sh [--dry-run] [status|apply|apply-all|revert]

set -euo pipefail

# 절대 경로 사용 (kubectl이 상대경로로 저장하는 문제 방지)
CACHE_SCRIPT="${HOME}/.kube/eks-token-cache.sh"
CACHE_STATE_DIR="${HOME}/.kube/cache/eks-token-cache"
BACKUP_DIR="${CACHE_STATE_DIR}/backups"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
JQ_BUILD_NEW_ARGS_FILTER="[ \$c, \$r ] + (if (\$p | length) > 0 then [\$p] else [] end)"
DRY_RUN=0
ACTION=""

require_cmd() {
    command -v "$1" >/dev/null 2>&1 || {
        echo -e "${RED}Missing required command: $1${NC}" >&2
        exit 127
    }
}

require_cmds_for_action() {
    local action="$1"
    require_cmd kubectl
    require_cmd jq
    case "$action" in
        apply|apply-all)
            if [[ "$DRY_RUN" -eq 0 ]]; then
                require_cmd yq
            fi
            validate_jq_filters
            ;;
        revert)
            require_cmd yq
            ;;
    esac
}

validate_jq_filters() {
    if ! jq -c -n --arg c "cluster" --arg r "region" --arg p "profile" "$JQ_BUILD_NEW_ARGS_FILTER" >/dev/null 2>&1; then
        echo -e "${RED}Error: 내부 jq 필터 검증에 실패했습니다. 스크립트의 jq 구문을 확인하세요.${NC}" >&2
        exit 1
    fi
}

usage() {
    cat <<EOF
EKS 토큰 캐시 관리자

사용법:
  $(basename "$0") [--dry-run|-n] status
  $(basename "$0") [--dry-run|-n] apply
  $(basename "$0") [--dry-run|-n] apply-all
  $(basename "$0") revert

옵션:
  -n, --dry-run  kubeconfig 변경 없이 적용 예정 내용만 출력 (apply/apply-all 전용)

EOF
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -n|--dry-run) DRY_RUN=1 ;;
            -h|--help|help) ACTION="help" ;;
            status|apply|apply-all|revert)
                if [[ -n "$ACTION" && "$ACTION" != "help" ]]; then
                    echo -e "${RED}Error: action은 하나만 지정할 수 있습니다.${NC}" >&2
                    usage
                    exit 1
                fi
                ACTION="$1"
                ;;
            *)
                echo -e "${RED}Error: 알 수 없는 인자: $1${NC}" >&2
                usage
                exit 1
                ;;
        esac
        shift
    done

    [[ -z "$ACTION" ]] && ACTION="status"

    if [[ "$DRY_RUN" -eq 1 && "$ACTION" != "apply" && "$ACTION" != "apply-all" && "$ACTION" != "help" ]]; then
        echo -e "${YELLOW}Warning: --dry-run은 apply/apply-all에서만 의미가 있습니다.${NC}" >&2
    fi
}

# kubeconfig를 JSON으로 (캐시하여 재사용, --raw로 exec 트리거 방지)
KUBECONFIG_JSON=""
get_kubeconfig_json() {
    if [[ -z "$KUBECONFIG_JSON" ]]; then
        KUBECONFIG_JSON=$(kubectl config view --raw -o json 2>/dev/null)
    fi
    echo "$KUBECONFIG_JSON"
}

get_kubeconfig_files() {
    local raw="${KUBECONFIG:-${HOME}/.kube/config}"
    local IFS=':'
    for cfg in $raw; do
        [[ -z "$cfg" ]] && continue
        cfg="${cfg/#\~/$HOME}"
        echo "$cfg"
    done
}

# EKS context 목록 추출
get_eks_contexts() {
    get_kubeconfig_json | jq -r '
        .contexts[] |
        select(.context.cluster | test("arn:aws:eks:|eks")) |
        .name
    ' 2>/dev/null || true
}

# context의 user 정보 가져오기
get_context_user() {
    local ctx="$1"
    get_kubeconfig_json | jq -r --arg ctx "$ctx" '
        .contexts[] | select(.name == $ctx) | .context.user
    '
}

# user의 exec command 확인
get_user_exec_command() {
    local user="$1"
    get_kubeconfig_json | jq -r --arg user "$user" '
        .users[] | select(.name == $user) | .user.exec.command // empty
    '
}

# user의 exec args 확인
get_user_exec_args() {
    local user="$1"
    get_kubeconfig_json | jq -r --arg user "$user" '
        .users[] | select(.name == $user) | .user.exec.args // [] | join(" ")
    '
}

get_user_exec_args_json() {
    local user="$1"
    get_kubeconfig_json | jq -c --arg user "$user" '
        .users[] | select(.name == $user) | .user.exec.args // []
    '
}

# 캐시 스크립트 적용 여부 확인
is_cache_enabled() {
    local user="$1"
    local cmd
    cmd=$(get_user_exec_command "$user")
    # 전체 경로 또는 스크립트명만 있는 경우 모두 체크
    [[ "$cmd" == "$CACHE_SCRIPT" || "$cmd" == "$(basename "$CACHE_SCRIPT")" ]]
}

# 상태 출력
cmd_status() {
    echo -e "${BLUE}=== EKS Context 상태 ===${NC}\n"

    local contexts
    contexts=$(get_eks_contexts)

    if [[ -z "$contexts" ]]; then
        echo "EKS context를 찾을 수 없습니다."
        return
    fi

    local applied=0
    local not_applied=0

    printf "%-40s %-15s %s\n" "CONTEXT" "STATUS" "CLUSTER/PROFILE"
    printf "%-40s %-15s %s\n" "-------" "------" "---------------"

    while IFS= read -r ctx; do
        local user
        user=$(get_context_user "$ctx")

        local exec_cmd
        exec_cmd=$(get_user_exec_command "$user")

        local exec_args
        exec_args=$(get_user_exec_args "$user")

        if [[ "$exec_cmd" == "$CACHE_SCRIPT" || "$exec_cmd" == "$(basename "$CACHE_SCRIPT")" ]]; then
            printf "%-40s ${GREEN}%-15s${NC} %s\n" "$ctx" "캐시 적용됨" "$exec_args"
            ((applied++)) || true
        elif [[ "$exec_cmd" == "aws" ]] || [[ -z "$exec_cmd" ]]; then
            printf "%-40s ${YELLOW}%-15s${NC} %s\n" "$ctx" "미적용" "$exec_args"
            ((not_applied++)) || true
        else
            printf "%-40s ${RED}%-15s${NC} %s\n" "$ctx" "기타" "$exec_cmd"
        fi
    done <<< "$contexts"

    echo ""
    echo -e "적용: ${GREEN}${applied}${NC}, 미적용: ${YELLOW}${not_applied}${NC}"
}

# args 배열에서 특정 플래그 다음 값 추출
get_arg_value() {
    local args_json="$1"
    local flag="$2"
    echo "$args_json" | jq -r --arg flag "$flag" '
        . as $arr |
        [ range(0; $arr|length) as $i |
            $arr[$i] |
            if . == $flag then ($arr[$i + 1] // empty)
            elif startswith($flag + "=") then (sub("^" + $flag + "="; ""))
            else empty end
        ] | map(select(length > 0)) | .[0] // empty
    ' 2>/dev/null
}

get_positional_arg() {
    local args_json="$1"
    local idx="$2"
    echo "$args_json" | jq -r --argjson idx "$idx" '.[ $idx ] // empty' 2>/dev/null
}

# user의 exec env에서 AWS_PROFILE 추출
get_user_aws_profile_env() {
    local user="$1"
    get_kubeconfig_json | jq -r --arg user "$user" '
        .users[] | select(.name == $user) |
        .user.exec.env // [] |
        map(select(.name == "AWS_PROFILE")) |
        .[0].value // empty
    '
}

ensure_state_dirs() {
    mkdir -p "$BACKUP_DIR"
    chmod 700 "$CACHE_STATE_DIR" "$BACKUP_DIR" 2>/dev/null || true
}

sanitize_id() {
    echo "$1" | tr '/:@' '____' | tr -c 'A-Za-z0-9_.-' '_'
}

backup_file_for_user() {
    local user="$1"
    echo "${BACKUP_DIR}/$(sanitize_id "$user").json"
}

write_backup() {
    local user="$1"
    local target_cfg="$2"
    local exec_json="$3"
    local backup_file

    ensure_state_dirs
    backup_file=$(backup_file_for_user "$user")

    printf '%s' "$exec_json" | jq -c --arg cfg "$target_cfg" '{kubeconfig: $cfg, exec: .}' > "$backup_file"
    chmod 600 "$backup_file" 2>/dev/null || true
}

# user가 속한 kubeconfig 파일 찾기
find_kubeconfig_for_user() {
    local user="$1"
    local cfg
    local found=""
    while IFS= read -r cfg; do
        [[ -f "$cfg" ]] || continue
        if kubectl config view --raw --kubeconfig "$cfg" -o json 2>/dev/null \
            | jq -e --arg user "$user" '.users[]? | select(.name == $user)' >/dev/null; then
            found="$cfg"
        fi
    done < <(get_kubeconfig_files)
    echo "$found"
}

# 단일 context에 캐시 적용
apply_to_context() {
    local ctx="$1"
    local user
    user=$(get_context_user "$ctx")

    # exec 정보 가져오기
    local exec_json
    exec_json=$(get_kubeconfig_json | jq -c --arg user "$user" '
        .users[] | select(.name == $user) | .user.exec // {}
    ')

    local args_json
    args_json=$(echo "$exec_json" | jq -c '.args // []')
    local exec_cmd
    exec_cmd=$(echo "$exec_json" | jq -r '.command // empty')
    local uses_cache_positional=0
    if [[ "$exec_cmd" == "$CACHE_SCRIPT" || "$exec_cmd" == "$(basename "$CACHE_SCRIPT")" ]]; then
        uses_cache_positional=1
    fi

    # cluster_name: --cluster-name 플래그 값 또는 ARN에서 추출
    local cluster_name
    cluster_name=$(get_arg_value "$args_json" "--cluster-name")
    if [[ -z "$cluster_name" && "$uses_cache_positional" -eq 1 ]]; then
        cluster_name=$(get_positional_arg "$args_json" 0)
    fi

    if [[ -z "$cluster_name" ]]; then
        # EKS ARN에서 추출 (arn:aws:eks:region:account:cluster/name)
        cluster_name=$(get_kubeconfig_json | jq -r --arg ctx "$ctx" '
            .contexts[] | select(.name == $ctx) | .context.cluster
        ' | sed 's|.*/||')
    fi

    # region: --region 플래그 값
    local region
    region=$(get_arg_value "$args_json" "--region")
    if [[ -z "$region" && "$uses_cache_positional" -eq 1 ]]; then
        region=$(get_positional_arg "$args_json" 1)
    fi
    region="${region:-ap-northeast-2}"

    # profile: --profile 플래그 값 또는 env의 AWS_PROFILE
    local profile
    profile=$(get_arg_value "$args_json" "--profile")
    if [[ -z "$profile" && "$uses_cache_positional" -eq 1 ]]; then
        profile=$(get_positional_arg "$args_json" 2)
    fi
    if [[ -z "$profile" ]]; then
        profile=$(get_user_aws_profile_env "$user")
    fi

    if [[ -z "$cluster_name" ]]; then
        echo -e "${RED}Error: $ctx 의 cluster name을 찾을 수 없습니다${NC}"
        return 1
    fi

    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo -e "점검 중(DRY-RUN): ${BLUE}$ctx${NC}"
    else
        echo -e "적용 중: ${BLUE}$ctx${NC}"
    fi
    echo "  cluster: $cluster_name, region: $region, profile: ${profile:-default}"

    # 해당 user가 있는 kubeconfig 파일 찾기
    local target_cfg
    target_cfg=$(find_kubeconfig_for_user "$user")
    if [[ -z "$target_cfg" ]]; then
        echo -e "${RED}Error: $ctx 의 kubeconfig 파일을 찾을 수 없습니다${NC}"
        return 1
    fi
    if [[ ! -f "$CACHE_SCRIPT" ]]; then
        echo -e "${RED}Error: 캐시 스크립트를 찾을 수 없습니다: $CACHE_SCRIPT${NC}"
        return 1
    fi

    # yq로 직접 수정 (kubectl의 상대경로 변환 문제 회피)
    local new_args_json
    if ! new_args_json=$(jq -c -n --arg c "$cluster_name" --arg r "$region" --arg p "$profile" \
        "$JQ_BUILD_NEW_ARGS_FILTER"); then
        echo -e "${RED}Error: $ctx 의 exec args 생성에 실패했습니다 (jq 필터 구문 확인 필요)${NC}"
        return 1
    fi

    if [[ "$DRY_RUN" -eq 1 ]]; then
        local new_args_preview
        new_args_preview=$(echo "$new_args_json" | jq -r 'join(" ")')
        echo "  kubeconfig: $target_cfg"
        echo "  user: $user"
        echo "  exec command: $CACHE_SCRIPT"
        echo "  exec args: $new_args_preview"
        echo -e "  ${YELLOW}DRY-RUN: 실제 파일 변경 없음${NC}"
        return 0
    fi

    write_backup "$user" "$target_cfg" "$exec_json"

    USER_NAME="$user" CACHE_SCRIPT="$CACHE_SCRIPT" EXEC_JSON="$exec_json" NEW_ARGS_JSON="$new_args_json" \
        yq e -i '
            (.users[] | select(.name == strenv(USER_NAME)) | .user.exec) = (
                (strenv(EXEC_JSON) | from_json) // {} |
                .apiVersion = "client.authentication.k8s.io/v1beta1" |
                .command = strenv(CACHE_SCRIPT) |
                .args = (strenv(NEW_ARGS_JSON) | from_json) |
                .interactiveMode = (.interactiveMode // "IfAvailable")
            )
        ' "$target_cfg"

    echo -e "  ${GREEN}완료${NC}"
}

# 선택 적용
cmd_apply() {
    local contexts
    contexts=$(get_eks_contexts)

    local not_applied=()
    while IFS= read -r ctx; do
        local user
        user=$(get_context_user "$ctx")
        if ! is_cache_enabled "$user"; then
            not_applied+=("$ctx")
        fi
    done <<< "$contexts"

    if [[ ${#not_applied[@]} -eq 0 ]]; then
        echo -e "${GREEN}모든 EKS context에 캐시가 적용되어 있습니다.${NC}"
        return
    fi

    echo -e "${BLUE}미적용 context 목록:${NC}\n"
    local i=1
    for ctx in "${not_applied[@]}"; do
        echo "  $i) $ctx"
        ((i++)) || true
    done
    echo "  a) 전체 적용"
    echo "  q) 취소"
    echo ""

    read -rp "선택 (번호/a/q): " choice

    case "$choice" in
        q|Q) echo "취소됨"; return ;;
        a|A)
            for ctx in "${not_applied[@]}"; do
                apply_to_context "$ctx"
            done
            ;;
        [0-9]*)
            if [[ $choice -ge 1 && $choice -le ${#not_applied[@]} ]]; then
                apply_to_context "${not_applied[$((choice-1))]}"
            else
                echo "잘못된 선택"
                return 1
            fi
            ;;
        *) echo "잘못된 선택"; return 1 ;;
    esac

    echo ""
    if [[ "$DRY_RUN" -eq 1 ]]; then
        echo -e "${YELLOW}DRY-RUN 완료: 실제 변경은 수행하지 않았습니다.${NC}"
    else
        echo -e "${GREEN}적용 완료!${NC} 'EKS_TOKEN_DEBUG=1 kubectl get nodes'로 확인하세요."
    fi
}

# 전체 적용
cmd_apply_all() {
    local contexts
    contexts=$(get_eks_contexts)

    local count=0
    while IFS= read -r ctx; do
        local user
        user=$(get_context_user "$ctx")
        if ! is_cache_enabled "$user"; then
            apply_to_context "$ctx"
            ((count++)) || true
        fi
    done <<< "$contexts"

    if [[ $count -eq 0 ]]; then
        if [[ "$DRY_RUN" -eq 1 ]]; then
            echo -e "${GREEN}모든 EKS context에 이미 캐시가 적용되어 있습니다 (DRY-RUN).${NC}"
        else
            echo -e "${GREEN}모든 EKS context에 이미 캐시가 적용되어 있습니다.${NC}"
        fi
    else
        echo ""
        if [[ "$DRY_RUN" -eq 1 ]]; then
            echo -e "${YELLOW}${count}개 context 점검 완료 (DRY-RUN, 실제 변경 없음)!${NC}"
        else
            echo -e "${GREEN}${count}개 context에 적용 완료!${NC}"
        fi
    fi
}

# 캐시 해제 (원본 복원)
cmd_revert() {
    local contexts
    contexts=$(get_eks_contexts)

    local applied=()
    while IFS= read -r ctx; do
        local user
        user=$(get_context_user "$ctx")
        if is_cache_enabled "$user"; then
            applied+=("$ctx")
        fi
    done <<< "$contexts"

    if [[ ${#applied[@]} -eq 0 ]]; then
        echo "캐시가 적용된 context가 없습니다."
        return
    fi

    echo -e "${BLUE}캐시 적용된 context 목록:${NC}\n"
    local i=1
    for ctx in "${applied[@]}"; do
        echo "  $i) $ctx"
        ((i++)) || true
    done
    echo "  a) 전체 해제"
    echo "  q) 취소"
    echo ""

    read -rp "선택 (번호/a/q): " choice

    revert_context() {
        local ctx="$1"
        local user
        user=$(get_context_user "$ctx")

        echo -e "복원 중: ${BLUE}$ctx${NC}"

        local backup_file
        backup_file=$(backup_file_for_user "$user")

        if [[ -f "$backup_file" ]]; then
            local target_cfg exec_json
            target_cfg=$(jq -r '.kubeconfig // empty' "$backup_file")
            exec_json=$(jq -c '.exec' "$backup_file")

            if [[ -z "$target_cfg" ]]; then
                target_cfg=$(find_kubeconfig_for_user "$user")
            fi

            if [[ -z "$target_cfg" ]]; then
                echo -e "${RED}Error: $ctx 의 kubeconfig 파일을 찾을 수 없습니다${NC}"
                return 1
            fi

            if [[ -z "$exec_json" || "$exec_json" == "null" ]]; then
                USER_NAME="$user" \
                    yq e -i 'del(.users[] | select(.name == strenv(USER_NAME)) | .user.exec)' "$target_cfg"
            else
                USER_NAME="$user" EXEC_JSON="$exec_json" \
                    yq e -i '(.users[] | select(.name == strenv(USER_NAME)) | .user.exec) = (strenv(EXEC_JSON) | from_json)' "$target_cfg"
            fi
        else
            echo -e "${YELLOW}Warning: 백업이 없어 현재 설정으로 복원합니다.${NC}"

            local args_json
            args_json=$(get_user_exec_args_json "$user")
            local exec_cmd
            exec_cmd=$(get_user_exec_command "$user")
            local uses_cache_positional=0
            if [[ "$exec_cmd" == "$CACHE_SCRIPT" || "$exec_cmd" == "$(basename "$CACHE_SCRIPT")" ]]; then
                uses_cache_positional=1
            fi

            local cluster_name region profile
            cluster_name=$(get_arg_value "$args_json" "--cluster-name")
            [[ -z "$cluster_name" && "$uses_cache_positional" -eq 1 ]] && cluster_name=$(get_positional_arg "$args_json" 0)

            if [[ -z "$cluster_name" ]]; then
                cluster_name=$(get_kubeconfig_json | jq -r --arg ctx "$ctx" '
                    .contexts[] | select(.name == $ctx) | .context.cluster
                ' | sed 's|.*/||')
            fi

            region=$(get_arg_value "$args_json" "--region")
            [[ -z "$region" && "$uses_cache_positional" -eq 1 ]] && region=$(get_positional_arg "$args_json" 1)
            region="${region:-ap-northeast-2}"

            profile=$(get_arg_value "$args_json" "--profile")
            [[ -z "$profile" && "$uses_cache_positional" -eq 1 ]] && profile=$(get_positional_arg "$args_json" 2)
            [[ -z "$profile" ]] && profile=$(get_user_aws_profile_env "$user")

            local target_cfg
            target_cfg=$(find_kubeconfig_for_user "$user")
            if [[ -z "$target_cfg" ]]; then
                echo -e "${RED}Error: $ctx 의 kubeconfig 파일을 찾을 수 없습니다${NC}"
                return 1
            fi

            kubectl config set-credentials "$user" \
                --kubeconfig "$target_cfg" \
                --exec-api-version=client.authentication.k8s.io/v1beta1 \
                --exec-command=aws \
                --exec-arg=eks \
                --exec-arg=get-token \
                --exec-arg=--cluster-name \
                --exec-arg="$cluster_name" \
                --exec-arg=--region \
                --exec-arg="$region" \
                --exec-arg=--output \
                --exec-arg=json \
                ${profile:+--exec-arg=--profile} \
                ${profile:+--exec-arg="$profile"} \
                >/dev/null
        fi

        echo -e "  ${GREEN}완료${NC}"
    }

    case "$choice" in
        q|Q) echo "취소됨"; return ;;
        a|A)
            for ctx in "${applied[@]}"; do
                revert_context "$ctx"
            done
            ;;
        [0-9]*)
            if [[ $choice -ge 1 && $choice -le ${#applied[@]} ]]; then
                revert_context "${applied[$((choice-1))]}"
            else
                echo "잘못된 선택"
                return 1
            fi
            ;;
        *) echo "잘못된 선택"; return 1 ;;
    esac
}

# 메인
parse_args "$@"

case "$ACTION" in
    status) require_cmds_for_action status; cmd_status ;;
    apply) require_cmds_for_action apply; cmd_apply ;;
    apply-all) require_cmds_for_action apply-all; cmd_apply_all ;;
    revert) require_cmds_for_action revert; cmd_revert ;;
    help) usage ;;
    *) usage; exit 1 ;;
esac

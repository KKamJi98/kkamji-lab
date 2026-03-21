#!/bin/bash
set -euo pipefail

# 전역 임시 디렉터리 (trap cleanup 대상)
_MIRROR_TMP_DIR=""

# 종료 시 임시 디렉터리 정리
cleanup() {
  local exit_code=$?
  if [ -n "$_MIRROR_TMP_DIR" ] && [ -d "$_MIRROR_TMP_DIR" ]; then
    rm -rf "$_MIRROR_TMP_DIR"
  fi
  exit "$exit_code"
}
trap cleanup EXIT

#######################################
# Container Image Mirror Tool (crane-based)
#
# crane을 사용하여 컨테이너 이미지를 Private ECR로 미러링합니다.
# docker buildx보다 가볍고 빠르며, 레지스트리 전용 도구입니다.
#
# 사용법:
#   ./mirror-images.sh [옵션]
#
# 옵션:
#   --dry-run       실제 실행 없이 명령어만 출력
#   --skip-login    ECR 로그인 단계 건너뛰기
#   --verify        미러링 후 검증만 실행
#   --parallel N    N개의 이미지를 병렬 처리 (기본: 순차)
#   --force         이미 존재하는 이미지도 덮어쓰기
#   --config FILE   설정 파일 지정 (기본: config.env)
#   --images FILE   이미지 목록 파일 지정 (기본: images.yaml)
#######################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 기본 설정 (config.env로 오버라이드 가능)
ECR_ACCOUNT="${ECR_ACCOUNT:-123456789012}"
ECR_REGION="${ECR_REGION:-ap-northeast-2}"
PLATFORMS="${PLATFORMS:-linux/amd64,linux/arm64}"
MAX_RETRIES="${MAX_RETRIES:-5}"
INITIAL_DELAY="${INITIAL_DELAY:-10}"
DELAY_BETWEEN="${DELAY_BETWEEN:-5}"
PARALLEL_JOBS="${PARALLEL_JOBS:-1}"

# 런타임 옵션
DRY_RUN=false
SKIP_LOGIN=false
VERIFY_ONLY=false
FORCE_COPY=false
CONFIG_FILE="${SCRIPT_DIR}/config.env"
IMAGES_FILE="${SCRIPT_DIR}/images.yaml"

# 결과 디렉터리 및 타임스탬프
RESULT_DIR="${SCRIPT_DIR}/results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_FILE="${RESULT_DIR}/mirror_${TIMESTAMP}.log"

# 이미지별 상태 저장 (indexed arrays for bash 3.2 compatibility)
RESULT_STATUS=()
IMAGE_SIZES=()

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# 로깅 함수
log() {
  local level=$1
  shift
  local msg="$*"
  local ts
  ts=$(date '+%Y-%m-%d %H:%M:%S')

  case "$level" in
    INFO)  echo -e "${GREEN}[INFO]${NC} $msg" ;;
    WARN)  echo -e "${YELLOW}[WARN]${NC} $msg" ;;
    ERROR) echo -e "${RED}[ERROR]${NC} $msg" ;;
    RETRY) echo -e "${BLUE}[RETRY]${NC} $msg" ;;
    DEBUG) echo -e "${CYAN}[DEBUG]${NC} $msg" ;;
  esac

  # 로그 파일에 기록 (색상 코드 제거)
  if [ -f "$LOG_FILE" ] 2>/dev/null; then
    echo "[$ts] [$level] $msg" >> "$LOG_FILE"
  fi
}

log_info()  { log INFO "$@"; }
log_warn()  { log WARN "$@"; }
log_error() { log ERROR "$@"; }
log_retry() { log RETRY "$@"; }
log_debug() { log DEBUG "$@"; }

# 사용법 출력
usage() {
  cat << EOF
Usage: $(basename "$0") [OPTIONS]

Container Image Mirror Tool - crane 기반 ECR 미러링

OPTIONS:
    --dry-run           실제 실행 없이 명령어만 출력
    --skip-login        ECR 로그인 단계 건너뛰기
    --verify            미러링 없이 검증만 실행
    --parallel N        N개의 이미지를 병렬 처리 (기본: 순차)
    --force             이미 존재하는 이미지도 덮어쓰기
    --config FILE       설정 파일 지정 (기본: config.env)
    --images FILE       이미지 목록 파일 지정 (기본: images.yaml)
    -h, --help          이 도움말 출력

EXAMPLES:
    # Dry-run으로 확인
    ./mirror-images.sh --dry-run

    # 4개 병렬 처리로 미러링
    ./mirror-images.sh --parallel 4

    # 검증만 실행
    ./mirror-images.sh --verify

    # 커스텀 설정 파일 사용
    ./mirror-images.sh --config my-config.env --images my-images.yaml

EOF
  exit 0
}

# 의존성 확인
check_dependencies() {
  local missing=()

  if ! command -v crane &> /dev/null; then
    missing+=("crane (brew install crane)")
  fi

  if ! command -v yq &> /dev/null; then
    missing+=("yq (brew install yq)")
  fi

  if ! command -v aws &> /dev/null; then
    missing+=("aws-cli (brew install awscli)")
  fi

  if [ ${#missing[@]} -gt 0 ]; then
    log_error "필수 도구가 설치되어 있지 않습니다:"
    for dep in "${missing[@]}"; do
      echo "  - $dep"
    done
    exit 1
  fi

  # crane 버전 출력
  local crane_version
  crane_version=$(crane version 2>/dev/null || echo "unknown")
  log_info "crane version: ${crane_version}"
}

# 인자 파싱
parse_args() {
  while [[ $# -gt 0 ]]; do
    case $1 in
      --dry-run)
        DRY_RUN=true
        shift
        ;;
      --skip-login)
        SKIP_LOGIN=true
        shift
        ;;
      --verify)
        VERIFY_ONLY=true
        shift
        ;;
      --parallel)
        PARALLEL_JOBS="$2"
        shift 2
        ;;
      --force)
        FORCE_COPY=true
        shift
        ;;
      --config)
        CONFIG_FILE="$2"
        shift 2
        ;;
      --images)
        IMAGES_FILE="$2"
        shift 2
        ;;
      -h|--help)
        usage
        ;;
      *)
        log_error "Unknown option: $1"
        usage
        ;;
    esac
  done
}

# 설정 파일 로드
load_config() {
  if [ -f "$CONFIG_FILE" ]; then
    log_info "설정 파일 로드: ${CONFIG_FILE}"
    # shellcheck source=/dev/null
    source "$CONFIG_FILE"
  else
    log_warn "설정 파일 없음: ${CONFIG_FILE} (기본값 사용)"
  fi

  # ECR_PREFIX 계산
  ECR_PREFIX="${ECR_ACCOUNT}.dkr.ecr.${ECR_REGION}.amazonaws.com"
}

# 이미지 목록 로드 (YAML 파싱)
load_images() {
  if [ ! -f "$IMAGES_FILE" ]; then
    log_error "이미지 목록 파일을 찾을 수 없습니다: ${IMAGES_FILE}"
    exit 1
  fi

  log_info "이미지 목록 로드: ${IMAGES_FILE}"

  # yq로 YAML 파싱하여 배열로 변환
  IMAGES=()
  local count
  count=$(yq '.images | length' "$IMAGES_FILE") || { log_error "yq 파싱 실패: ${IMAGES_FILE}"; exit 1; }

  if [ -z "$count" ] || [ "$count" -eq 0 ]; then
    log_error "이미지 목록이 비어있습니다"
    exit 1
  fi

  for ((i=0; i<count; i++)); do
    local chart source dest
    chart=$(yq ".images[$i].chart" "$IMAGES_FILE") || { log_error "이미지 #$((i+1)): chart 파싱 실패"; exit 1; }
    source=$(yq ".images[$i].source" "$IMAGES_FILE") || { log_error "이미지 #$((i+1)): source 파싱 실패"; exit 1; }
    dest=$(yq ".images[$i].dest" "$IMAGES_FILE") || { log_error "이미지 #$((i+1)): dest 파싱 실패"; exit 1; }

    if [ -z "$source" ] || [ -z "$dest" ]; then
      log_error "이미지 #$((i+1)): source 또는 dest가 비어있습니다 (source='${source}', dest='${dest}')"
      continue
    fi

    IMAGES+=("${chart}|${source}|${dest}")
  done

  log_info "로드된 이미지 수: ${#IMAGES[@]}"
}

# 결과 디렉터리 초기화
init_result_dir() {
  if [ ! -d "$RESULT_DIR" ]; then
    mkdir -p "$RESULT_DIR"
    log_info "결과 디렉터리 생성: ${RESULT_DIR}"
  fi

  # 로그 파일 초기화
  touch "$LOG_FILE"
  log_info "로그 파일: ${LOG_FILE}"
}

# ECR 로그인 (crane 사용)
ecr_login() {
  if [ "$SKIP_LOGIN" = true ]; then
    log_warn "ECR 로그인 건너뛰기"
    return
  fi

  log_info "ECR 로그인 중... (crane auth)"

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY-RUN] aws ecr get-login-password --region ${ECR_REGION} | crane auth login ${ECR_PREFIX} -u AWS --password-stdin"
    return
  fi

  if aws ecr get-login-password --region "${ECR_REGION}" | \
     crane auth login "${ECR_PREFIX}" -u AWS --password-stdin; then
    log_info "ECR 로그인 성공"
  else
    log_error "ECR 로그인 실패"
    exit 1
  fi
}

# ECR 리포지토리 생성
create_repository() {
  local repo_name=$1

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY-RUN] aws ecr create-repository --region ${ECR_REGION} --repository-name ${repo_name}"
    return 0
  fi

  if aws ecr describe-repositories --region "${ECR_REGION}" \
       --repository-names "${repo_name}" &>/dev/null; then
    log_debug "리포지토리 존재: ${repo_name}"
    return 0
  fi

  if aws ecr create-repository --region "${ECR_REGION}" \
       --repository-name "${repo_name}" &>/dev/null; then
    log_info "리포지토리 생성: ${repo_name}"
  else
    log_warn "리포지토리 생성 실패 (이미 존재할 수 있음): ${repo_name}"
  fi
}

# ECR 리포지토리 일괄 생성
create_repositories() {
  log_info "ECR 리포지토리 확인/생성 중..."

  local repos=()
  for entry in "${IMAGES[@]}"; do
    IFS='|' read -r _ _ dest <<< "$entry"
    local repo_name="${dest%%:*}"
    repos+=("$repo_name")
  done

  # 중복 제거
  local sorted_repos=()
  while IFS= read -r repo; do
    sorted_repos+=("$repo")
  done < <(printf '%s\n' "${repos[@]}" | sort -u)

  for repo in "${sorted_repos[@]}"; do
    create_repository "$repo"
  done
}

# 이미지 사이즈 조회 (bytes -> human readable)
get_image_size() {
  local image=$1
  local size_bytes

  size_bytes=$(crane manifest "$image" 2>/dev/null | \
    yq -p json '.config.size + ([.layers[].size] | add)' 2>/dev/null || echo "0")

  if [ "$size_bytes" = "0" ] || [ -z "$size_bytes" ]; then
    echo "N/A"
    return
  fi

  # Human readable 변환
  if [ "$size_bytes" -ge 1073741824 ]; then
    printf "%.2f GB" "$(echo "scale=2; $size_bytes/1073741824" | bc)"
  elif [ "$size_bytes" -ge 1048576 ]; then
    printf "%.2f MB" "$(echo "scale=2; $size_bytes/1048576" | bc)"
  elif [ "$size_bytes" -ge 1024 ]; then
    printf "%.2f KB" "$(echo "scale=2; $size_bytes/1024" | bc)"
  else
    printf "%d B" "$size_bytes"
  fi
}

# 이미지 존재 여부 확인
image_exists() {
  local image=$1
  crane manifest "$image" &>/dev/null
}

# 플랫폼별 digest 가져오기
# manifest list인 경우 해당 플랫폼의 digest, 단일 manifest인 경우 전체 digest 반환
get_platform_digest() {
  local image=$1
  local platform=$2

  local manifest
  manifest=$(crane manifest "$image" 2>/dev/null) || return 1

  # manifest list (mediaType에 manifest.list 또는 index 포함)인지 확인
  local media_type
  media_type=$(echo "$manifest" | jq -r '.mediaType // ""' 2>/dev/null)

  if [[ "$media_type" == *"manifest.list"* ]] || [[ "$media_type" == *"image.index"* ]]; then
    # manifest list인 경우: 해당 플랫폼의 digest 반환
    echo "$manifest" | jq -r --arg platform "$platform" \
      '.manifests[] | select(.platform.os + "/" + .platform.architecture == $platform) | .digest' 2>/dev/null
  else
    # 단일 manifest인 경우: 이미지 전체 digest 반환
    crane digest "$image" 2>/dev/null
  fi
}

# 이미지가 멀티플랫폼인지 확인
is_multiplatform() {
  local image=$1
  local manifest
  manifest=$(crane manifest "$image" 2>/dev/null) || return 1

  local media_type
  media_type=$(echo "$manifest" | jq -r '.mediaType // ""' 2>/dev/null)

  [[ "$media_type" == *"manifest.list"* ]] || [[ "$media_type" == *"image.index"* ]]
}

# 재시도 로직이 포함된 이미지 복사
# 멀티플랫폼 이미지는 crane index filter로 지정된 플랫폼만 복사
# 단일 플랫폼 이미지는 crane copy로 그대로 복사
copy_image_with_retry() {
  local source=$1
  local dest=$2
  local attempt=1
  local delay=$INITIAL_DELAY

  # 플랫폼 옵션 구성 (crane index filter용)
  local platform_args=()
  IFS=',' read -ra platforms <<< "$PLATFORMS"
  for p in "${platforms[@]}"; do
    platform_args+=("--platform=$p")
  done

  while [ "$attempt" -le "$MAX_RETRIES" ]; do
    log_debug "복사 시도 ${attempt}/${MAX_RETRIES}: ${source} -> ${dest}"

    local output
    if is_multiplatform "$source"; then
      # 멀티플랫폼: crane index filter로 지정된 플랫폼만 복사
      log_debug "멀티플랫폼 이미지 - crane index filter 사용 (${PLATFORMS})"
      if output=$(crane index filter "$source" "${platform_args[@]}" -t "$dest" 2>&1); then
        return 0
      fi
    else
      # 단일 플랫폼: crane copy로 그대로 복사
      log_debug "단일 플랫폼 이미지 - crane copy 사용"
      if output=$(crane copy "$source" "$dest" 2>&1); then
        return 0
      fi
    fi

    log_debug "crane 출력: ${output}"

    if [ "$attempt" -lt "$MAX_RETRIES" ]; then
      log_retry "시도 ${attempt}/${MAX_RETRIES} 실패. ${delay}초 후 재시도..."
      sleep "$delay"
      # Exponential backoff (최대 60초)
      delay=$((delay * 2))
      [ "$delay" -gt 60 ] && delay=60
    fi
    ((attempt++))
  done

  return 1
}

# 단일 이미지 미러링
mirror_single_image() {
  local entry=$1
  local idx=$2
  local total=$3

  IFS='|' read -r chart source dest <<< "$entry"
  local dest_full="${ECR_PREFIX}/${dest}"

  echo ""
  log_info "[${idx}/${total}] ${BOLD}${chart}${NC}"
  log_info "  Source: ${source}"
  log_info "  Dest:   ${dest_full}"

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY-RUN] crane index filter ${source} --platform=${PLATFORMS} -t ${dest_full}"
    RESULT_STATUS["$idx"]="DRY_RUN"
    return 0
  fi

  # 이미지 사이즈 조회
  local size
  size=$(get_image_size "$source")
  log_info "  Size:   ${size}"
  IMAGE_SIZES["$idx"]="$size"

  # 이미 존재하는지 확인
  if [ "$FORCE_COPY" = false ] && image_exists "$dest_full"; then
    log_warn "  이미 존재함 - 스킵 (--force로 덮어쓰기 가능)"
    RESULT_STATUS["$idx"]="SKIPPED"
    return 0
  fi

  # 리포지토리 생성
  local repo_name="${dest%%:*}"
  create_repository "$repo_name"

  # 이미지 복사
  if copy_image_with_retry "$source" "$dest_full"; then
    log_info "  ${GREEN}✓ 복사 성공${NC}"
    RESULT_STATUS["$idx"]="SUCCESS"
    return 0
  else
    log_error "  ${RED}✗ 복사 실패${NC} (${MAX_RETRIES}회 재시도 후)"
    RESULT_STATUS["$idx"]="FAILED"
    return 1
  fi
}

# 이미지 미러링 (순차)
mirror_images_sequential() {
  log_info "이미지 미러링 시작 (순차 처리)..."
  log_info "Rate limit 대응: 이미지 간 ${DELAY_BETWEEN}초 대기, 최대 ${MAX_RETRIES}회 재시도"

  local success=0
  local failed=0
  local skipped=0
  local total=${#IMAGES[@]}
  local current=0

  for entry in "${IMAGES[@]}"; do
    ((current++))

    if mirror_single_image "$entry" "$current" "$total"; then
      case "${RESULT_STATUS[$current]}" in
        SUCCESS|DRY_RUN) ((success++)) ;;
        SKIPPED) ((skipped++)); ((success++)) ;;
      esac
    else
      ((failed++))
    fi

    # Rate limit 방지
    if [ "$current" -lt "$total" ] && [ "$DRY_RUN" = false ]; then
      log_info "  ${DELAY_BETWEEN}초 대기..."
      sleep "$DELAY_BETWEEN"
    fi
  done

  print_summary "$success" "$failed" "$skipped" "$total"
}

# 이미지 미러링 (병렬)
mirror_images_parallel() {
  log_info "이미지 미러링 시작 (병렬 처리: ${PARALLEL_JOBS}개)..."

  local total=${#IMAGES[@]}
  _MIRROR_TMP_DIR=$(mktemp -d)
  local tmp_dir="$_MIRROR_TMP_DIR"

  # 이미지 목록을 파일로 저장
  local idx=1
  for entry in "${IMAGES[@]}"; do
    echo "${idx}|${entry}" >> "${tmp_dir}/images.txt"
    ((idx++))
  done

  # 병렬 처리 함수
  export ECR_PREFIX PLATFORMS MAX_RETRIES INITIAL_DELAY DRY_RUN FORCE_COPY
  export -f copy_image_with_retry image_exists create_repository get_image_size
  export -f log log_info log_warn log_error log_retry log_debug
  export RED GREEN YELLOW BLUE CYAN BOLD NC
  export ECR_REGION LOG_FILE

  # xargs로 병렬 실행
  cat "${tmp_dir}/images.txt" | xargs -P "$PARALLEL_JOBS" -I {} bash -c '
    line="{}"
    idx="${line%%|*}"
    rest="${line#*|}"
    IFS="|" read -r chart source dest <<< "$rest"
    dest_full="${ECR_PREFIX}/${dest}"

    echo "[${idx}] ${chart}: ${source} -> ${dest_full}"

    if [ "$DRY_RUN" = true ]; then
      echo "  [DRY-RUN] crane index filter ${source} --platform=${PLATFORMS} -t ${dest_full}"
      echo "SUCCESS" > "'"${tmp_dir}"'/result_${idx}"
    elif [ "$FORCE_COPY" = false ] && crane manifest "$dest_full" &>/dev/null; then
      echo "  스킵 (이미 존재)"
      echo "SKIPPED" > "'"${tmp_dir}"'/result_${idx}"
    else
      # 플랫폼 옵션 구성
      IFS="," read -ra platforms <<< "$PLATFORMS"
      platform_args=""
      for p in "${platforms[@]}"; do
        platform_args="$platform_args --platform=$p"
      done

      # 멀티플랫폼 여부 확인
      media_type=$(crane manifest "$source" 2>/dev/null | jq -r ".mediaType // \"\"" 2>/dev/null)
      if [[ "$media_type" == *"manifest.list"* ]] || [[ "$media_type" == *"image.index"* ]]; then
        # 멀티플랫폼: crane index filter
        if crane index filter "$source" $platform_args -t "$dest_full" >/dev/null 2>&1; then
          echo "  ✓ 성공 (멀티플랫폼)"
          echo "SUCCESS" > "'"${tmp_dir}"'/result_${idx}"
        else
          echo "  ✗ 실패"
          echo "FAILED" > "'"${tmp_dir}"'/result_${idx}"
        fi
      else
        # 단일 플랫폼: crane copy
        if crane copy "$source" "$dest_full" >/dev/null 2>&1; then
          echo "  ✓ 성공 (단일)"
          echo "SUCCESS" > "'"${tmp_dir}"'/result_${idx}"
        else
          echo "  ✗ 실패"
          echo "FAILED" > "'"${tmp_dir}"'/result_${idx}"
        fi
      fi
    fi
  '

  # 결과 수집
  local success=0 failed=0 skipped=0
  for ((i=1; i<=total; i++)); do
    if [ -f "${tmp_dir}/result_${i}" ]; then
      local result
      result=$(cat "${tmp_dir}/result_${i}")
      RESULT_STATUS[$i]="$result"
      case "$result" in
        SUCCESS|DRY_RUN) ((success++)) ;;
        SKIPPED) ((skipped++)); ((success++)) ;;
        FAILED) ((failed++)) ;;
      esac
    else
      RESULT_STATUS[$i]="FAILED"
      ((failed++))
    fi
  done

  rm -rf "$tmp_dir"
  print_summary "$success" "$failed" "$skipped" "$total"
}

# 결과 요약 출력
print_summary() {
  local success=$1
  local failed=$2
  local skipped=$3
  local total=$4

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log_info "미러링 완료"
  log_info "  성공: ${success}/${total} (스킵: ${skipped})"
  [ "$failed" -gt 0 ] && log_error "  실패: ${failed}/${total}"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

# 이미지 검증
verify_images() {
  log_info "이미지 검증 중... (플랫폼별 digest 비교)"

  local verified=0
  local failed=0
  local total=${#IMAGES[@]}
  local current=0

  IFS=',' read -ra platforms <<< "$PLATFORMS"

  for entry in "${IMAGES[@]}"; do
    ((current++))
    IFS='|' read -r chart source dest <<< "$entry"
    local dest_full="${ECR_PREFIX}/${dest}"

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "[${current}/${total}] ${BOLD}${chart}${NC}"
    echo "  Source: ${source}"
    echo "  ECR:    ${dest_full}"
    echo ""

    if [ "$DRY_RUN" = true ]; then
      echo "  [DRY-RUN] 검증 스킵"
      ((verified++))
      continue
    fi

    # ECR에 이미지가 존재하는지 확인
    if ! image_exists "$dest_full"; then
      log_error "  ECR에 이미지가 존재하지 않음"
      ((failed++))
      continue
    fi

    # 소스가 멀티플랫폼인지 확인
    local source_multiplatform=false
    local ecr_multiplatform=false
    is_multiplatform "$source" && source_multiplatform=true
    is_multiplatform "$dest_full" && ecr_multiplatform=true

    local all_match=true

    if [ "$source_multiplatform" = true ]; then
      # 멀티플랫폼: 플랫폼별 digest 비교
      printf "  %-12s %-20s %-20s %s\n" "PLATFORM" "SOURCE" "ECR" "MATCH"
      printf "  %s\n" "──────────────────────────────────────────────────────────"

      for platform in "${platforms[@]}"; do
        local source_digest ecr_digest
        source_digest=$(get_platform_digest "$source" "$platform")
        ecr_digest=$(get_platform_digest "$dest_full" "$platform")

        # digest 축약
        local source_short="N/A"
        local ecr_short="N/A"
        [ -n "$source_digest" ] && [ "$source_digest" != "null" ] && source_short="${source_digest:0:19}"
        [ -n "$ecr_digest" ] && [ "$ecr_digest" != "null" ] && ecr_short="${ecr_digest:0:19}"

        if [ -z "$source_digest" ] || [ "$source_digest" = "null" ]; then
          printf "  %-12s %-20s %-20s ${YELLOW}%s${NC}\n" "$platform" "N/A" "$ecr_short" "SKIP"
        elif [ -z "$ecr_digest" ] || [ "$ecr_digest" = "null" ]; then
          printf "  %-12s %-20s %-20s ${RED}%s${NC}\n" "$platform" "$source_short" "N/A" "MISSING"
          all_match=false
        elif [ "$source_digest" = "$ecr_digest" ]; then
          printf "  %-12s %-20s %-20s ${GREEN}%s${NC}\n" "$platform" "$source_short" "$ecr_short" "✓"
        else
          printf "  %-12s %-20s %-20s ${RED}%s${NC}\n" "$platform" "$source_short" "$ecr_short" "✗"
          all_match=false
        fi
      done
    else
      # 단일 플랫폼: 전체 digest 비교
      printf "  %-12s %-20s %-20s %s\n" "TYPE" "SOURCE" "ECR" "MATCH"
      printf "  %s\n" "──────────────────────────────────────────────────────────"

      local source_digest ecr_digest
      source_digest=$(crane digest "$source" 2>/dev/null)
      ecr_digest=$(crane digest "$dest_full" 2>/dev/null)

      local source_short="N/A"
      local ecr_short="N/A"
      [ -n "$source_digest" ] && source_short="${source_digest:0:19}"
      [ -n "$ecr_digest" ] && ecr_short="${ecr_digest:0:19}"

      if [ "$source_digest" = "$ecr_digest" ]; then
        printf "  %-12s %-20s %-20s ${GREEN}%s${NC}\n" "single" "$source_short" "$ecr_short" "✓"
      else
        printf "  %-12s %-20s %-20s ${RED}%s${NC}\n" "single" "$source_short" "$ecr_short" "✗"
        all_match=false
      fi
    fi

    if [ "$all_match" = true ]; then
      log_info "  결과: ${GREEN}digest 일치 ✓${NC}"
      ((verified++))
    else
      log_error "  결과: ${RED}digest 불일치 ✗${NC}"
      ((failed++))
    fi
  done

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  log_info "검증 완료: 성공 ${verified}/${total}, 실패 ${failed}/${total}"

  [ "$failed" -gt 0 ] && return 1
  return 0
}

# CSV 결과 내보내기
export_csv() {
  local csv_file="${RESULT_DIR}/images_${TIMESTAMP}.csv"

  log_info "CSV 파일 생성: ${csv_file}"

  echo "Chart,Source,Destination,Status,Size" > "$csv_file"

  local idx=1
  for entry in "${IMAGES[@]}"; do
    IFS='|' read -r chart source dest <<< "$entry"
    local dest_full="${ECR_PREFIX}/${dest}"
    local status="${RESULT_STATUS[$idx]:-PENDING}"
    local size="${IMAGE_SIZES[$idx]:-N/A}"
    echo "${chart},${source},${dest_full},${status},${size}" >> "$csv_file"
    ((idx++))
  done
}

# Markdown 결과 내보내기
export_md() {
  local md_file="${RESULT_DIR}/images_${TIMESTAMP}.md"
  local success_count=0
  local failed_count=0
  local skipped_count=0
  local total=${#IMAGES[@]}

  for status in "${RESULT_STATUS[@]}"; do
    case "$status" in
      SUCCESS|DRY_RUN) ((success_count++)) ;;
      SKIPPED) ((skipped_count++)); ((success_count++)) ;;
      FAILED) ((failed_count++)) ;;
    esac
  done

  log_info "Markdown 파일 생성: ${md_file}"

  cat > "$md_file" << EOF
# Container Image Mirror Results

## 실행 정보

| 항목 | 값 |
|------|-----|
| 실행 시간 | $(date '+%Y-%m-%d %H:%M:%S') |
| ECR Prefix | \`${ECR_PREFIX}\` |
| 플랫폼 | ${PLATFORMS} |
| 병렬 처리 | ${PARALLEL_JOBS} |
| 총 이미지 | ${total} |
| 성공 | ${success_count} (스킵: ${skipped_count}) |
| 실패 | ${failed_count} |

## 이미지 목록

| Chart | Source | Destination | Status | Size |
|-------|--------|-------------|--------|------|
EOF

  local idx=1
  for entry in "${IMAGES[@]}"; do
    IFS='|' read -r chart source dest <<< "$entry"
    local dest_full="${ECR_PREFIX}/${dest}"
    local status="${RESULT_STATUS[$idx]:-PENDING}"
    local size="${IMAGE_SIZES[$idx]:-N/A}"
    local status_emoji=""
    case "$status" in
      SUCCESS) status_emoji="✓" ;;
      SKIPPED) status_emoji="⏭" ;;
      FAILED) status_emoji="✗" ;;
      DRY_RUN) status_emoji="🔍" ;;
      *) status_emoji="-" ;;
    esac
    echo "| ${chart} | \`${source}\` | \`${dest_full}\` | ${status_emoji} ${status} | ${size} |" >> "$md_file"
    ((idx++))
  done
}

# 배너 출력
print_banner() {
  echo ""
  echo "╔═══════════════════════════════════════════════════════════╗"
  echo "║       Container Image Mirror Tool (crane-based)           ║"
  echo "╚═══════════════════════════════════════════════════════════╝"
  echo ""
  echo "  ECR:        ${ECR_PREFIX}"
  echo "  Images:     ${#IMAGES[@]}"
  echo "  Platforms:  ${PLATFORMS}"
  echo "  Parallel:   ${PARALLEL_JOBS}"
  echo "  Results:    ${RESULT_DIR}"
  [ "$DRY_RUN" = true ] && echo "  Mode:       ${YELLOW}DRY-RUN${NC}"
  [ "$VERIFY_ONLY" = true ] && echo "  Mode:       ${CYAN}VERIFY ONLY${NC}"
  [ "$FORCE_COPY" = true ] && echo "  Force:      ${YELLOW}ENABLED${NC}"
  echo ""
}

# 메인 함수
main() {
  parse_args "$@"
  load_config
  load_images
  init_result_dir
  check_dependencies

  print_banner

  if [ "$VERIFY_ONLY" = true ]; then
    ecr_login
    verify_images
    export_csv
    export_md
    exit $?
  fi

  ecr_login

  if [ "$PARALLEL_JOBS" -gt 1 ]; then
    mirror_images_parallel
  else
    mirror_images_sequential
  fi

  verify_images

  echo ""
  export_csv
  export_md

  echo ""
  log_info "결과 파일:"
  log_info "  - ${RESULT_DIR}/images_${TIMESTAMP}.csv"
  log_info "  - ${RESULT_DIR}/images_${TIMESTAMP}.md"
  log_info "  - ${LOG_FILE}"
}

main "$@"

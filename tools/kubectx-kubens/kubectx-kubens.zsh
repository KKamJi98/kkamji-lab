# kubectx/kubens - Shell functions with TTL cache
# Replaces kubectx/kubens binaries with direct kubectl calls + fzf
#
# Usage: source this file in ~/.zshrc or ~/.zsh_functions
#   source /path/to/kubectx-kubens.zsh

# ============================================================
# Configuration
# ============================================================
: ${KCTX_CACHE_TTL:=300}       # Default: 5 minutes
: ${KCTX_CACHE_DIR:="${XDG_CACHE_HOME:-$HOME/.cache}/kubectx-fzf"}

# ============================================================
# Internal Helper Functions
# ============================================================

# Get kubeconfig file modification time (for cache invalidation)
_kctx_kubeconfig_mtime() {
  local cfg="${KUBECONFIG:-$HOME/.kube/config}"
  local -a files mtimes
  files=("${(@s/:/)cfg}")
  for f in "${files[@]}"; do
    [[ -f "$f" ]] && mtimes+=($(stat -f %m "$f" 2>/dev/null))
  done
  echo "${(j/:/)mtimes:-0}"
}

# Get cached data if valid (checks TTL and kubeconfig mtime)
# Usage: _kctx_cache_get <cache_file> <ttl_seconds>
# Returns: 0 if cache hit (prints cached data), 1 if cache miss
_kctx_cache_get() {
  local cache_file="$1" ttl="$2"
  [[ -f "$cache_file" ]] || return 1

  # Read file into array (zsh native, no external commands)
  local -a lines
  lines=("${(@f)$(< "$cache_file")}")

  # Extract mtime from first line (format: "mtime:1234567890")
  local cached_mtime="${lines[1]#mtime:}"
  local current_mtime=$(_kctx_kubeconfig_mtime)

  # Invalidate if kubeconfig changed
  [[ "$cached_mtime" != "$current_mtime" ]] && return 1

  # Check TTL
  local cache_time now
  cache_time=$(stat -f %m "$cache_file" 2>/dev/null) || return 1
  now=$(date +%s)
  (( now - cache_time > ttl )) && return 1

  # Cache hit: output data (skip first metadata line)
  (( ${#lines[@]} > 1 )) && print -l "${lines[@]:1}"
  return 0
}

# Save data to cache with kubeconfig mtime
# Usage: _kctx_cache_set <cache_file> <data>
_kctx_cache_set() {
  local cache_file="$1"
  local data="$2"

  # Don't cache empty results
  [[ -z "$data" ]] && return 1

  mkdir -p "${cache_file:h}" 2>/dev/null
  local mtime=$(_kctx_kubeconfig_mtime)
  printf "mtime:%s\n%s\n" "$mtime" "$data" > "$cache_file"
}

# Clear all kubectx/kubens caches
_kctx_cache_clear() {
  rm -rf "${KCTX_CACHE_DIR}" 2>/dev/null
  echo "Cache cleared: ${KCTX_CACHE_DIR}"
}

# ============================================================
# kubens Internal Helpers (direct kubectl, no subprocess)
# ============================================================

# Get current namespace without spawning kubens subprocess
_kubens_current() {
  local ns
  ns=$(command kubectl config view --minify -o jsonpath='{..namespace}' 2>/dev/null)
  [[ -z "$ns" ]] && ns="default"
  echo "$ns"
}

# Switch namespace directly via kubectl (no kubens subprocess)
# Saves previous namespace for `kubens -` support
_kubens_switch() {
  local target="$1"
  local prev_file="${KCTX_CACHE_DIR}/kubens-prev"

  # Save current namespace as "previous" before switching
  local current
  current=$(_kubens_current)

  mkdir -p "${KCTX_CACHE_DIR}" 2>/dev/null
  echo "$current" > "$prev_file"

  command kubectl config set-context --current --namespace="$target" >/dev/null 2>&1 || {
    echo "Error: Failed to set namespace '$target'" >&2
    return 1
  }
  echo "Active namespace is \"$target\"."
}

# Validate namespace exists (check cache first, fallback to API)
_kubens_validate() {
  local target="$1"
  local context namespaces safe_context cache_file

  context=$(command kubectl config current-context 2>/dev/null) || return 1
  safe_context="${context//[\/:]/_}"
  cache_file="${KCTX_CACHE_DIR}/namespaces-${safe_context}"

  # Try cache first
  if namespaces=$(_kctx_cache_get "$cache_file" "$KCTX_CACHE_TTL"); then
    echo "$namespaces" | command grep -qx "$target" && return 0
  fi

  # Cache miss or not found in cache: fetch from API
  namespaces=$(command kubectl get namespaces -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | tr ' ' '\n') || return 1
  [[ -n "$namespaces" ]] && _kctx_cache_set "$cache_file" "$namespaces"

  echo "$namespaces" | command grep -qx "$target"
}

# ============================================================
# kubectx Internal Helpers (direct kubectl, no subprocess)
# ============================================================

# Switch context directly via kubectl (no kubectx subprocess)
# Saves previous context for `kubectx -` support
_kubectx_switch() {
  local target="$1"
  local prev_file="${KCTX_CACHE_DIR}/kubectx-prev"

  # Save current context as "previous" before switching
  local current
  current=$(command kubectl config current-context 2>/dev/null)

  mkdir -p "${KCTX_CACHE_DIR}" 2>/dev/null
  [[ -n "$current" ]] && echo "$current" > "$prev_file"

  command kubectl config use-context "$target" >/dev/null 2>&1 || {
    echo "Error: Failed to switch to context '$target'" >&2
    return 1
  }
  echo "Switched to context \"$target\"."
}

# Get context list (cache first, fallback to kubectl)
_kctx_list_contexts() {
  local cache_file="${KCTX_CACHE_DIR}/contexts"
  local contexts

  if ! contexts=$(_kctx_cache_get "$cache_file" "$KCTX_CACHE_TTL"); then
    contexts=$(command kubectl config get-contexts -o name 2>/dev/null) || return 1
    [[ -n "$contexts" ]] && _kctx_cache_set "$cache_file" "$contexts"
  fi

  [[ -n "$contexts" ]] || return 1
  print -l "${(@f)contexts}"
}

# Get namespace list for current context (cache first, fallback to API)
_kctx_list_namespaces() {
  local context safe_context cache_file namespaces

  context=$(command kubectl config current-context 2>/dev/null) || return 1
  [[ -n "$context" ]] || return 1

  safe_context="${context//[\/:]/_}"
  cache_file="${KCTX_CACHE_DIR}/namespaces-${safe_context}"

  if ! namespaces=$(_kctx_cache_get "$cache_file" "$KCTX_CACHE_TTL"); then
    namespaces=$(command kubectl get namespaces -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | tr ' ' '\n') || return 1
    [[ -n "$namespaces" ]] && _kctx_cache_set "$cache_file" "$namespaces"
  fi

  [[ -n "$namespaces" ]] || return 1
  print -l "${(@f)namespaces}"
}

# ============================================================
# kubectx - Kubernetes context switcher with fzf + cache
# ============================================================
kubectx() {
  local cache_file="${KCTX_CACHE_DIR}/contexts"
  local refresh=0

  # Parse options
  case "$1" in
    -r|--refresh)
      refresh=1
      shift
      ;;
    -)
      # Switch to previous context (direct, no subprocess)
      local prev_file="${KCTX_CACHE_DIR}/kubectx-prev"
      if [[ -f "$prev_file" ]]; then
        local prev_ctx
        prev_ctx=$(< "$prev_file")
        [[ -n "$prev_ctx" ]] && _kubectx_switch "$prev_ctx" && return
      fi
      echo "Error: No previous context found" >&2
      return 1
      ;;
    -c|--current)
      command kubectl config current-context 2>/dev/null || echo "(none)"
      return
      ;;
    --unset)
      if [[ -n "$2" ]]; then
        echo "Error: --unset takes no arguments. Did you mean '--delete $2'?" >&2
        return 1
      fi
      local _cfg="${KUBECONFIG:-$HOME/.kube/config}"
      local -a _files
      _files=("${(@s/:/)_cfg}")
      local _cleared=0
      for f in "${_files[@]}"; do
        [[ -f "$f" ]] || continue
        if command grep -q '^current-context:' "$f" 2>/dev/null; then
          command kubectl config unset current-context --kubeconfig="$f" >/dev/null 2>&1 && ((_cleared++))
        fi
      done
      rm -f "${KCTX_CACHE_DIR}/contexts" 2>/dev/null
      echo "Context unset. ($_cleared file(s) updated)"
      return
      ;;
    -d|--delete)
      local target="$2"
      if [[ -z "$target" ]]; then
        echo "Error: --delete requires a context name" >&2
        echo "Usage: kubectx --delete <name>" >&2
        return 1
      fi
      command kubectl config delete-context "$target" || return 1
      # Clean up dangling current-context references in all KUBECONFIG files
      local _cfg="${KUBECONFIG:-$HOME/.kube/config}"
      local -a _files
      local _line="current-context: ${target}"
      _files=("${(@s/:/)_cfg}")
      for f in "${_files[@]}"; do
        [[ -f "$f" ]] || continue
        if command grep -qxF "$_line" "$f" 2>/dev/null; then
          command kubectl config unset current-context --kubeconfig="$f" >/dev/null 2>&1
        fi
      done
      rm -f "${KCTX_CACHE_DIR}/contexts" 2>/dev/null
      return
      ;;
    -h|--help)
      cat <<'HELP'
Usage: kubectx                     : fzf로 context 선택
       kubectx <name>              : context 전환
       kubectx -                   : 이전 context로 전환
       kubectx -c, --current       : 현재 context 출력
       kubectx --unset             : 현재 context 해제
       kubectx -d, --delete <name> : context 삭제
       kubectx -r, --refresh       : 캐시 갱신 후 fzf
HELP
      return
      ;;
    "")
      # No argument: fzf mode (continue below)
      ;;
    *)
      # Direct context name: switch directly (no subprocess)
      _kubectx_switch "$1"
      return
      ;;
  esac

  # Force refresh if requested
  (( refresh )) && rm -f "$cache_file"

  # Get current context for header
  local current
  current=$(command kubectl config current-context 2>/dev/null) || current="(none)"

  # Try cache first, then fetch from API
  local contexts
  if ! contexts=$(_kctx_cache_get "$cache_file" "$KCTX_CACHE_TTL"); then
    # Cache miss: fetch from API
    contexts=$(command kubectl config get-contexts -o name 2>/dev/null) || {
      echo "Error: Failed to get contexts from kubectl" >&2
      return 1
    }
    [[ -z "$contexts" ]] && {
      echo "Error: No contexts found" >&2
      return 1
    }
    _kctx_cache_set "$cache_file" "$contexts"
  fi

  # fzf selection (here-string avoids subshell)
  local selected
  selected=$(fzf \
    --height=40% \
    --reverse \
    --header="Current: $current" \
    --prompt="Context > " \
    --preview='kubectl config view --minify --context={} -o jsonpath="{.clusters[0].cluster.server}" 2>/dev/null || echo "No cluster info"' \
    --preview-window=down:1:wrap \
    <<< "$contexts"
  ) || return 0  # User cancelled

  [[ -n "$selected" ]] && _kubectx_switch "$selected"
}

# ============================================================
# kubens - Kubernetes namespace switcher with fzf + cache
# ============================================================
kubens() {
  local context refresh=0

  # Parse options
  case "$1" in
    -r|--refresh)
      refresh=1
      shift
      ;;
    -)
      # Switch to previous namespace (direct, no subprocess)
      local prev_file="${KCTX_CACHE_DIR}/kubens-prev"
      if [[ -f "$prev_file" ]]; then
        local prev_ns
        prev_ns=$(< "$prev_file")
        [[ -n "$prev_ns" ]] && _kubens_switch "$prev_ns" && return
      fi
      echo "Error: No previous namespace found" >&2
      return 1
      ;;
    -c|--current)
      # Direct current namespace query (no subprocess)
      _kubens_current
      return
      ;;
    --unset)
      if ! command kubectl config set-context --current --namespace= >/dev/null 2>&1; then
        echo "Error: Failed to unset namespace (no current context?)" >&2
        return 1
      fi
      local _ctx _safe_ctx
      _ctx=$(command kubectl config current-context 2>/dev/null)
      if [[ -n "$_ctx" ]]; then
        _safe_ctx="${_ctx//[\/:]/_}"
        rm -f "${KCTX_CACHE_DIR}/namespaces-${_safe_ctx}" 2>/dev/null
      fi
      echo "Namespace unset."
      return
      ;;
    -h|--help)
      cat <<'HELP'
Usage: kubens                   : fzf로 namespace 선택
       kubens <name>            : namespace 전환
       kubens -                 : 이전 namespace로 전환
       kubens -c, --current     : 현재 namespace 출력
       kubens --unset           : 현재 namespace 해제
       kubens -r, --refresh     : 캐시 갱신 후 fzf
HELP
      return
      ;;
    "")
      # No argument: fzf mode (continue below)
      ;;
    *)
      # Direct namespace name: validate + switch directly
      if _kubens_validate "$1"; then
        _kubens_switch "$1"
      else
        echo "Error: Namespace '$1' not found" >&2
        return 1
      fi
      return
      ;;
  esac

  # Get current context for context-specific caching
  context=$(command kubectl config current-context 2>/dev/null) || {
    echo "Error: No current context set" >&2
    return 1
  }

  # Sanitize context name for filename (replace / and : with _)
  local safe_context="${context//[\/:]/_}"
  local cache_file="${KCTX_CACHE_DIR}/namespaces-${safe_context}"

  # Force refresh if requested
  (( refresh )) && rm -f "$cache_file"

  # Get current namespace for header (direct, no subprocess)
  local current
  current=$(_kubens_current)

  # Try cache first, then fetch from API
  local namespaces
  if ! namespaces=$(_kctx_cache_get "$cache_file" "$KCTX_CACHE_TTL"); then
    # Cache miss: fetch from API
    namespaces=$(command kubectl get namespaces -o jsonpath='{.items[*].metadata.name}' 2>/dev/null | tr ' ' '\n') || {
      echo "Error: Failed to get namespaces from kubectl" >&2
      return 1
    }
    [[ -z "$namespaces" ]] && {
      echo "Error: No namespaces found" >&2
      return 1
    }
    _kctx_cache_set "$cache_file" "$namespaces"
  fi

  # fzf selection (here-string avoids subshell)
  local selected
  selected=$(fzf \
    --height=40% \
    --reverse \
    --header="Context: $context | Current NS: $current" \
    --prompt="Namespace > " \
    <<< "$namespaces"
  ) || return 0  # User cancelled

  [[ -n "$selected" ]] && _kubens_switch "$selected"
}

# ============================================================
# zsh completion
# ============================================================
_kctx_kubectx_completion() {
  local -a options contexts
  options=("-" "-c" "--current" "--unset" "-d" "--delete" "-r" "--refresh" "-h" "--help")

  if (( CURRENT == 2 )); then
    contexts=("${(@f)$(_kctx_list_contexts 2>/dev/null)}")
    if [[ "$PREFIX" == -* ]]; then
      compadd -Q -a options
      return 0
    fi
    compadd -Q -a options
    (( ${#contexts[@]} )) && compadd -Q -a contexts
  elif (( CURRENT == 3 )) && [[ "${words[2]}" == (-d|--delete) ]]; then
    contexts=("${(@f)$(_kctx_list_contexts 2>/dev/null)}")
    (( ${#contexts[@]} )) && compadd -Q -a contexts
  fi
}

_kctx_kubens_completion() {
  local -a options namespaces
  options=("-" "-c" "--current" "--unset" "-r" "--refresh" "-h" "--help")
  namespaces=("${(@f)$(_kctx_list_namespaces 2>/dev/null)}")

  (( CURRENT == 2 )) || return 0

  if [[ "$PREFIX" == -* ]]; then
    compadd -Q -a options
    return 0
  fi

  compadd -Q -a options
  (( ${#namespaces[@]} )) && compadd -Q -a namespaces
}

_kctx_register_completions() {
  (( $+functions[compdef] )) || return 0
  compdef _kctx_kubectx_completion kubectx
  compdef _kctx_kubens_completion kubens
}

_kctx_register_completions

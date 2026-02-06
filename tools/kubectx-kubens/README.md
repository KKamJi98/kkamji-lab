# kubectx/kubens (Shell Functions)

kubectx/kubens 바이너리를 완전 대체하는 zsh shell 함수입니다. `kubectl config` 명령을 직접 실행하고, fzf 목록에 TTL 캐시를 적용하여 빠른 전환을 제공합니다.

## 설치

```bash
# ~/.zshrc 또는 ~/.zsh_functions에 source 추가
source /path/to/kubectx-kubens.zsh
```

symlink 방식도 가능합니다:

```bash
ln -s $(pwd)/kubectx-kubens.zsh ~/.kubectx-kubens.zsh
# ~/.zshrc에 추가:
source ~/.kubectx-kubens.zsh
```

### 의존성

- `kubectl`
- `fzf` (대화형 선택 시)

`brew install kubectx` 불필요.

## 사용법

### kubectx

```bash
kubectx                  # fzf로 context 선택
kubectx <name>           # context 전환
kubectx -                # 이전 context로 전환
kubectx -c, --current    # 현재 context 출력
kubectx --unset          # 현재 context 해제
kubectx -r, --refresh    # 캐시 갱신 후 fzf
```

### kubens

```bash
kubens                   # fzf로 namespace 선택
kubens <name>            # namespace 전환
kubens -                 # 이전 namespace로 전환
kubens -c, --current     # 현재 namespace 출력
kubens --unset           # 현재 namespace 해제
kubens -r, --refresh     # 캐시 갱신 후 fzf
```

## 설정

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `KCTX_CACHE_TTL` | 캐시 유효 시간 (초) | `300` (5분) |
| `KCTX_CACHE_DIR` | 캐시 디렉토리 | `$XDG_CACHE_HOME/kubectx-fzf` |

## 동작 원리

- kubectx/kubens 바이너리 의존성 제거 — `kubectl config` 명령을 직접 실행
- kubens의 `kubectl get namespaces` API 호출을 TTL 캐시로 대체
- 이전 context/namespace를 파일에 저장하여 `-` 전환도 서브프로세스 없이 처리
- kubeconfig mtime 변경 시 캐시 자동 무효화

## 성능 비교

| 시나리오 | 원본 kubectx/kubens | 자체 구현 |
|----------|---------------------|-----------|
| `kubectx <name>` | ~200-500ms | ~50ms |
| `kubectx -` (이전 context) | ~200-500ms | ~50ms |
| `kubectx` (fzf, 캐시 hit) | ~250-350ms | ~100ms |
| `kubens <name>` | ~500-2500ms | ~100ms |
| `kubens -` (이전 ns) | ~500-2500ms | ~100ms |
| `kubens` (fzf, 캐시 hit) | ~250-350ms | ~100ms |

## 라이선스

MIT

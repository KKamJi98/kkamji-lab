# swagger-loadgen

Swagger/OpenAPI 스펙에서 **GET endpoint만 자동 수집**해서
고정 TPS로 요청을 보내는 Python CLI 도구입니다.

특히 Swagger UI에서 `Select a definition`으로 여러 backend를 고르는 구조(예: `backend`, `agent`)를 대상으로,
**여러 definition의 GET endpoint를 한 번에 호출**하는 용도로 설계되었습니다.

## 1. 핵심 목표

- Swagger endpoint를 입력하면 GET endpoint를 자동 발견
- 여러 backend definition을 한 번에 대상으로 부하 요청 수행
- 고정 TPS(rate limit)로 일정한 트래픽 생성
- 실행 중 상태를 실시간 출력하고, 종료 시 요약 통계 제공

## 2. 지원 기능

- OpenAPI 2.0(Swagger), OpenAPI 3.x
- 단일 스펙 URL 실행 (`--url`)
- Swagger config URL 기반 멀티 definition 실행 (`--swagger-config-url`)
- definition 필터링 (`--definition backend,agent` 또는 `-d backend -d agent`)
- GET endpoint 자동 추출
- path parameter 치환 (`/users/{userId}`)
- include/exclude glob 필터
- 요청 헤더 주입 (`Authorization` 등)
- 실시간 결과 출력 + summary (전체/definition별/endpoint별)

## 3. 동작 방식

1. 스펙 소스 수집
- 단일 모드: `--url`
- 멀티 모드: Swagger config의 `urls[]` 또는 `url`을 읽어 소스 목록 생성

2. GET endpoint 추출
- 각 스펙의 `paths`에서 `get` operation만 수집

3. 실행
- endpoint 목록을 round-robin으로 순회
- token bucket 방식으로 고정 TPS 유지

4. 리포트
- 각 요청 결과를 실시간 출력
- 종료 시 p50/p95/p99, 성공률, definition별 통계 출력

## 4. 설치

```bash
uv sync
```

## 5. 빠른 시작

### 5.1 단일 Swagger 스펙

```bash
uv run swagger-loadgen \
  --url https://petstore3.swagger.io/api/v3/openapi.json \
  --tps 5 \
  --duration 30
```

### 5.2 여러 backend definition (Swagger config endpoint)

```bash
uv run swagger-loadgen \
  --swagger-config-url https://api.example.com/swagger-config \
  --tps 10 \
  --duration 60
```

예: `/swagger-config` 응답이 아래와 같은 경우

```json
{
  "urls": [
    { "name": "backend", "url": "/specs/backend.json" },
    { "name": "agent", "url": "/specs/agent.json" }
  ]
}
```

두 definition의 GET endpoint를 모두 수집해서 요청합니다.

### 5.3 특정 definition만 선택

```bash
uv run swagger-loadgen \
  --swagger-config-url https://api.example.com/swagger-config \
  -d backend \
  -d agent \
  --tps 20 \
  --duration 30
```

또는 comma-separated:

```bash
uv run swagger-loadgen \
  --swagger-config-url https://api.example.com/swagger-config \
  --definition backend,agent \
  --tps 20 \
  --duration 30
```

### 5.4 단일 URL + 멀티 config 동시 사용

```bash
uv run swagger-loadgen \
  --url https://api.example.com/openapi-internal.json \
  --url-name internal \
  --swagger-config-url https://api.example.com/swagger-config \
  --tps 30 \
  --duration 45
```

### 5.5 base URL 강제 오버라이드

```bash
uv run swagger-loadgen \
  --swagger-config-url https://api.example.com/swagger-config \
  --base-url http://localhost:8080 \
  --tps 10 \
  --duration 20
```

## 6. CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--url` | 단일 OpenAPI/Swagger spec URL | 없음 |
| `--url-name` | `--url` 소스의 logical name | `single` |
| `--swagger-config-url` | Swagger config endpoint URL | 없음 |
| `--definition`, `-d` | 실행할 definition 필터 (반복/콤마 구분) | 전체 |
| `--tps` | 초당 요청 수 | `1.0` |
| `--duration` | 실행 시간(초) | `30.0` |
| `--config` | YAML 설정 파일 경로 | 없음 |
| `--header` | 요청 헤더 (`Key: Value`, 반복 가능) | 없음 |
| `--base-url` | 스펙 서버 주소 무시하고 강제 URL 사용 | 없음 |

주의:
- `--url` 또는 `--swagger-config-url` 중 최소 1개는 필수입니다.
- 둘 다 입력하면 소스가 합쳐집니다.

## 7. Config 파일

예시(`params.yaml`):

```yaml
params:
  petId: "1"
  userId: "42"

include:
  - "/pet/*"
  - "/users/*"

exclude:
  - "/users/private/*"

headers:
  Authorization: "Bearer my-token"
  X-Custom: "value"
```

필드 설명:
- `params`: path parameter 치환 값
- `include`: 포함할 path glob
- `exclude`: 제외할 path glob
- `headers`: 공통 요청 헤더

CLI `--header`는 config `headers`보다 우선 적용됩니다.

## 8. 출력 예시

실행 중:

```text
[backend] GET /ping 200 12ms
[agent] GET /health 200 18ms
[backend] GET /users/{userId} 404 31ms
```

종료 후:
- Total requests
- Success / Failure
- p50 / p95 / p99 latency
- Per-Definition Stats
- Per-Endpoint Stats

## 9. 실패 처리 정책

- 특정 spec 파싱 실패: 해당 definition만 스킵하고 계속 진행
- 전체 source에서 실행 가능한 GET endpoint가 없으면 종료
- definition 필터가 전부 미매칭이면 종료

## 10. 개발/검증

```bash
uv run ruff check .
uv run ruff format --check .
uv run --with pytest pytest
```

## 11. 제한 사항 (현재)

- GET method만 호출합니다.
- request body/query 조합 생성은 아직 지원하지 않습니다.
- OpenAPI operation-level auth flow 자동 협상은 지원하지 않습니다.

## License

MIT

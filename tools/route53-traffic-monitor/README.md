# Route53 Weighted Traffic Monitor (r53mon)

Route53 가중치(Weighted) 레코드의 **설정 비율 vs 실제 DNS 트래픽 분포**를 실시간으로 비교하는 CLI 도구.

Blue/Green 배포 시 가중치를 조정하면서, 실제 DNS 응답이 의도한 비율대로 분배되는지 터미널에서 바로 확인할 수 있다.

## 동작 원리

```
r53mon watch
  │
  ├─ Route53 API로 Weighted 레코드 목록 조회 (SetIdentifier, Weight, Value)
  ├─ Hosted Zone의 권한 NS(Name Server) 조회
  │
  └─ asyncio 이벤트 루프
       ├─ DNS 조회: 권한 NS에 직접 질의 → 응답 IP를 SetIdentifier에 매핑 → 분포 기록
       ├─ HTTP 요청(선택): 조회된 IP로 실제 HTTP 요청 → 응답 시간 측정
       ├─ Route53 Poller: 30초마다 가중치 설정 변경 감지
       └─ Rich Dashboard: 0.5초마다 실시간 대시보드 갱신
```

- 권한 NS에 직접 질의하므로 DNS 캐시 영향 없이 Route53의 가중치 라우팅 결정을 직접 측정
- A / CNAME / Alias 레코드 모두 지원

## 요구사항

- Python 3.11+
- AWS 자격증명 (Route53 ReadOnly 권한)
  - `route53:ListResourceRecordSets`
  - `route53:GetHostedZone`

## 설치

```bash
# 개발용 (editable)
uv tool install --editable .

# 일반 설치
uv tool install .
```

## 사용법

### 기본 사용

```bash
r53mon watch --endpoint https://app.example.com --zone-id ZXXXXXXXXXX
```

`--endpoint`에서 호스트명(`app.example.com`)을 자동 추출하여 해당 레코드의 가중치 분포를 모니터링한다.

### 전체 옵션

```bash
r53mon watch \
  --endpoint https://app.example.com \
  --zone-id ZXXXXXXXXXX \
  --record-name app.example.com \
  --tps 20 \
  --no-http
```

| 옵션 | 단축 | 환경변수 | 설명 | 기본값 |
|------|------|----------|------|--------|
| `--endpoint` | `-e` | `R53MON_ENDPOINT` | 모니터링 대상 URL | (필수) |
| `--zone-id` | `-z` | `R53MON_HOSTED_ZONE_ID` | Route53 Hosted Zone ID | (필수) |
| `--record-name` | `-r` | `R53MON_RECORD_NAME` | DNS 레코드명 | endpoint에서 추출 |
| `--tps` | `-t` | `R53MON_TPS` | 초당 DNS 조회 횟수 (1~100) | `10` |
| `--no-http` | | `R53MON_NO_HTTP` | HTTP 요청 비활성화 (DNS만 측정) | `false` |
| `--config` | `-c` | | TOML 설정 파일 경로 | `./r53mon.toml` |
| `--env-file` | | | .env 파일 경로 | `./.env` |

### 대시보드 출력 예시

```
🚀 Route53 Weighted Traffic Monitor — app.example.com
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Route53 Configured Weights
┌────────────────┬────────┬───────┐
│ SetIdentifier  │ Weight │ Ratio │
├────────────────┼────────┼───────┤
│ blue-32        │    180 │ 72.0% │
│ green-33       │     70 │ 28.0% │
└────────────────┴────────┴───────┘

📊 Actual Traffic Distribution (Total: 1,234)
┌────────────────┬───────┬───────┬────────┬────────────────────────────┐
│ SetIdentifier  │ Count │ Ratio │  Diff  │ Distribution               │
├────────────────┼───────┼───────┼────────┼────────────────────────────┤
│ blue-32        │   891 │ 72.2% │  +0.2% │ ██████████████████░░░░░░░░ │
│ green-33       │   343 │ 27.8% │  -0.2% │ ███████░░░░░░░░░░░░░░░░░░ │
└────────────────┴───────┴───────┴────────┴────────────────────────────┘

⏱  TPS: 10.1  │  Uptime: 02:03  │  Errors: 0  │  Avg Latency: 45ms
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

- **Configured Weights**: Route53에 설정된 가중치 (30초마다 자동 갱신)
- **Actual Traffic Distribution**: DNS 조회 결과 기반 실제 분포
- **Diff**: 실제 비율 - 설정 비율 (양수=초록, 음수=빨강)
- **Avg Latency**: HTTP 요청 평균 응답 시간 (`--no-http` 시 N/A)

`Ctrl+C`로 종료하면 최종 통계를 출력한다.

## 설정 방법

설정은 여러 소스에서 로딩되며, 우선순위는 다음과 같다:

**CLI args > 환경변수 > .env 파일 > TOML 파일 > 기본값**

### 1. CLI 인자 (최우선)

```bash
r53mon watch --endpoint https://app.example.com --zone-id ZXXXXXXXXXX --tps 20
```

### 2. 환경변수

```bash
export R53MON_ENDPOINT=https://app.example.com
export R53MON_HOSTED_ZONE_ID=ZXXXXXXXXXX
export R53MON_TPS=20
r53mon watch
```

### 3. .env 파일

```bash
cp .env.example .env
# .env 파일 편집 후
r53mon watch
```

```dotenv
R53MON_ENDPOINT=https://app.example.com
R53MON_HOSTED_ZONE_ID=ZXXXXXXXXXX
R53MON_TPS=20
```

### 4. TOML 설정 파일

`r53mon.toml` 파일을 프로젝트 루트에 생성:

```toml
[r53mon]
endpoint = "https://app.example.com"
hosted_zone_id = "ZXXXXXXXXXX"
tps = 20
no_http = false
```

경로 지정: `r53mon watch --config /path/to/config.toml`

## 사용 시나리오

### Blue/Green 배포 모니터링

```bash
# 1. 배포 전: 현재 분포 확인 (blue 100%)
r53mon watch -e https://app.example.com -z ZXXXXXXXXXX

# 2. 가중치 변경 후: 실시간 분포 변화 관찰
#    Route53 콘솔에서 green 10% 설정 → 대시보드에서 자동 감지 (30초 내)

# 3. 점진적 전환 완료 확인 (green 100%)
```

### DNS 전용 측정 (HTTP 없이)

```bash
# HTTP 요청 없이 DNS 분포만 빠르게 확인
r53mon watch -e https://app.example.com -z ZXXXXXXXXXX --no-http --tps 50
```

### 고빈도 측정

```bash
# TPS를 높여서 빠르게 통계적 유의성 확보
r53mon watch -e https://app.example.com -z ZXXXXXXXXXX --tps 100 --no-http
```

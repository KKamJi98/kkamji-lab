# swagger-loadgen

Load generator that parses OpenAPI/Swagger specs and fires GET requests at a fixed TPS.

## Features

- OpenAPI 2.0 (Swagger) and 3.0 support
- GET endpoint auto-discovery with path parameter substitution
- Fixed TPS rate control via async token bucket
- YAML config for params, include/exclude patterns, and auth headers
- Real-time console output with rich + p50/p95/p99 summary on exit

## Install

```bash
uv sync
```

## Usage

```bash
# Basic — hit petstore at 5 TPS for 30 seconds
uv run swagger-loadgen --url https://petstore3.swagger.io/api/v3/openapi.json --tps 5 --duration 30

# With config file for path params and filtering
uv run swagger-loadgen --url https://api.example.com/openapi.json --tps 10 --duration 60 --config params.yaml

# With auth header
uv run swagger-loadgen --url https://api.example.com/openapi.json --tps 10 --header "Authorization: Bearer <token>"

# Override base URL (ignore servers in spec)
uv run swagger-loadgen --url https://api.example.com/openapi.json --base-url http://localhost:8080
```

## Config File

```yaml
params:
  petId: "1"
  orderId: "42"

include:
  - "/pet/*"
  - "/store/*"

exclude:
  - "/user/*"

headers:
  Authorization: "Bearer my-token"
  X-Custom: "value"
```

## License

MIT

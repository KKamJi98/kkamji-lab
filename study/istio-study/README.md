# Istio Study

## 준비

- 기본 컨텍스트: `KUBE_CONTEXT=rancher-desktop` (필요하면 환경변수로 덮어쓰기)
- `01-install-istio` 디렉터리에 kube-prometheus-stack 차트(`kube-prometheus-stack-79.12.0.tgz`), Kiali 매니페스트, Istio CNI 오버레이(`istio-cni.yaml`)가 포함되어 있습니다.
- `make help`로 모든 타깃을 확인할 수 있습니다.

## Istio 설치/삭제 (Makefile 기반)

- Init 모드 설치: `make istio-install-init` (또는 `make istio-install`/`make istio`)
  - 프로파일 `$(ISTIO_PROFILE)` 기본값은 `default`, pilot CPU/MEM 요청은 Makefile 변수로 관리합니다.
- CNI 모드 설치: `make istio-install-cni`
  - `ISTIO_OVERLAY_CNI` 파일을 함께 적용하고 `istiod`, `istio-cni-node` 롤아웃까지 대기합니다.
- 검증: `make istio-verify`
- 삭제: `make istio-uninstall` (CRD까지 제거하려면 `ISTIO_PURGE=true make istio-uninstall`)

## 모니터링 스택

- 설치: `make monitoring-install` (kube-prometheus-stack + Kiali)
- 삭제: `make monitoring-delete`
- Kiali 단독 적용/삭제는 `make kiali` / `make kiali-delete`, kube-prometheus-stack만 관리하려면 `make kube-prometheus-stack` / `make kube-prometheus-stack-uninstall`을 사용할 수 있습니다.

## 참고

- 실습 예제, Bookinfo 배포, Gateway 설정 등 상세한 수동 절차는 `01-install-istio/README.md`를 참고하세요.

# Request Routing

[KubeOPS - [아는 만큼 힘이 되는 트래픽 관리]](https://cafe.naver.com/kubeops/822)

## 1. Request Routing이란?
서비스 메시 내에서 트래픽을 제어하고 관리하는 기능입니다. Istio는 다양한 라우팅 규칙을 설정하여 트래픽을 특정 서비스 버전으로 분산시키거나, A/B 테스트, 카나리 배포 등을 지원합니다. 이를 통해 개발자는 애플리케이션의 가용성과 안정성을 높일 수 있습니다.

## 2. 실습

01-istio-overview 실습에서 Bookinfo 애플리케이션이 이미 배포되어 있습니다. 이 애플리케이션은 여러 마이크로서비스로 구성되어 있으며, 각 서비스는 서로 다른 기능을 담당합니다.

### 2.1. DestinationRule, VirtualService 생성

```shell
kubectl apply -f bookstore-app/destination-rule.yaml
kubectl apply -f bookstore-app/virtual-service.yaml
```
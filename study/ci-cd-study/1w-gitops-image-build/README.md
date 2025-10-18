# 1주차: 컨테이너 이미지 빌드 및 로컬 쿠버네티스 환경 구성

본 문서는 로컬 환경에 `kind`를 사용하여 쿠버네티스 클러스터를 구축하고, `Docker`를 이용해 컨테이너 이미지를 빌드 및 실행하는 과정을 안내합니다.

## 1. 개발 환경 구성

실습을 위해 필요한 도구들을 설치합니다.

### 필수 도구

| 도구 | 설치 명령어 (macOS, [Homebrew](https://brew.sh/) 기준) | 설명 |
| --- | --- | --- |
| `kind` | `brew install kind` | 로컬 쿠버네티스 클러스터 |
| `kubectl` | `brew install kubernetes-cli` | 쿠버네티스 CLI |
| `helm` | `brew install helm` | 쿠버네티스 패키지 매니저 |

**kubectl 단축키 설정 (선택 사항)**

```shell
# `k`를 kubectl의 alias로 등록
echo "alias k=kubectl" >> ~/.zshrc
```

### 권장 도구

| 도구 | 설치 명령어 | 설명 |
| --- | --- | --- |
| `krew` | `brew install krew` | kubectl 플러그인 매니저 |
| `kube-ps1` | `brew install kube-ps1` | 프롬프트에 현재 컨텍스트 표시 |
| `kubectx` | `brew install kubectx` | 컨텍스트 및 네임스페이스 전환 |
| `k9s` | `brew install k9s` | 터미널 기반 쿠버네티스 UI |
| `kubecolor` | `brew install kubecolor` | kubectl 출력 하이라이트 |

**kubecolor 및 krew 환경 변수 설정**

```shell
# kubecolor 적용
echo "alias kubectl=kubecolor" >> ~/.zshrc
echo "compdef kubecolor=kubectl" >> ~/.zshrc

# krew 경로 추가
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"
```

---

## 2. `kind`를 이용한 로컬 클러스터 생성

`Docker`가 실행 중인지 확인한 후, 다음 명령어로 `kind` 클러스터를 생성합니다.

```shell
# kind 클러스터 생성 (컨트롤 플레인 1, 워커 1)
kind create cluster --name myk8s --image kindest/node:v1.32.8 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  - containerPort: 30000
    hostPort: 30000
  - containerPort: 30001
    hostPort: 30001
- role: worker
EOF
```

### 클러스터 생성 확인

```shell
# 노드 목록 확인
kubectl get nodes -o wide

# 전체 파드 확인
kubectl get pods -A -o wide

# 클러스터 정보 및 Kubeconfig 확인
kubectl cluster-info
kubectl config view
```

---

## 3. Docker를 사용한 컨테이너 이미지 빌드

`Dockerfile`을 사용하여 애플리케이션을 컨테이너 이미지로 빌드합니다. 본 실습에서는 `chapters/ch03/python-app`의 샘플 코드를 사용합니다.

### 빌드 과정

```shell
# 실습 디렉토리로 이동
cd chapters/chapters/ch03/python-app

# Docker Hub 사용자 이름 설정
MYUSER="본인의 Docker Hub 계정명"
MYREGISTRY="docker.io"

# Docker 이미지 빌드
docker build -f Dockerfile -t $MYREGISTRY/$MYUSER/pythonapp:latest .

# 빌드된 이미지 확인
docker images
```

### 이미지 레이어 확인

`docker inspect` 명령어를 사용하면 이미지의 레이어 구조를 확인할 수 있으며, 베이스 이미지 위에 `Dockerfile`의 각 명령어가 새로운 레이어로 추가된 것을 볼 수 있습니다.

---

## 4. 컨테이너 실행 및 배포

빌드한 이미지를 `Docker Hub`에 푸시하고, 로컬에서 컨테이너를 실행하여 정상 동작하는지 확인합니다.

```shell
# Docker Hub 로그인
docker login $MYREGISTRY

# 이미지 푸시
docker push $MYREGISTRY/$MYUSER/pythonapp:latest

# 컨테이너 실행 (포트 8080 포워딩)
docker run -d --name myweb -p 8080:8080 $MYREGISTRY/$MYUSER/pythonapp:latest

# 애플리케이션 접속 테스트
curl http://127.0.0.1:8080
# 예상 출력: Hello, World!

# 컨테이너 로그 확인
docker logs myweb

# 실습 완료 후 컨테이너 삭제
docker rm -f myweb
```

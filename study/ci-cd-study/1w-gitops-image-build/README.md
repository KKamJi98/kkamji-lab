# 1주차: 컨테이너 이미지 빌드 및 로컬 Kubernetes 환경 구성

로컬 환경에 `kind`를 사용하여 Kubernetes 클러스터를 구축하고, `Docker`를 이용해 컨테이너 이미지를 빌드 및 실행하는 방법을 학습합니다.

---

## 1. 학습 목표

- Docker를 활용한 컨테이너 이미지 빌드 이해
- kind를 사용한 로컬 Kubernetes 클러스터 구축
- 다양한 언어(Python, Node.js)의 애플리케이션 컨테이너화
- 이미지 레이어 구조 및 최적화 이해

---

## 2. 개발 환경 구성

실습을 위해 필요한 도구들을 설치합니다.

### 2.1. 필수 도구

| 도구 | 용도 | 설치 (macOS) |
|------|------|--------------|
| Docker | 컨테이너 런타임 | `brew install --cask docker` |
| kind | 로컬 K8s 클러스터 | `brew install kind` |
| kubectl | K8s CLI | `brew install kubernetes-cli` |
| Helm | 패키지 관리자 | `brew install helm` |

### 2.2. kubectl 단축키 설정 (선택)

```bash
# zsh 사용자
echo "alias k=kubectl" >> ~/.zshrc
echo "complete -F __start_kubectl k" >> ~/.zshrc
source ~/.zshrc
```

### 2.3. 권장 도구

| 도구 | 용도 | 설치 |
|------|------|------|
| krew | kubectl 플러그인 관리 | `brew install krew` |
| kube-ps1 | 프롬프트에 컨텍스트 표시 | `brew install kube-ps1` |
| kubectx | 컨텍스트/네임스페이스 전환 | `brew install kubectx` |
| k9s | 터미널 기반 K8s UI | `brew install k9s` |
| kubecolor | kubectl 출력 하이라이트 | `brew install kubecolor` |

**kubecolor 설정:**

```bash
# kubectl을 kubecolor로 대체
echo "alias kubectl=kubecolor" >> ~/.zshrc
echo "compdef kubecolor=kubectl" >> ~/.zshrc

# krew 경로 추가
export PATH="${KREW_ROOT:-$HOME/.krew}/bin:$PATH"
```

---

## 3. kind를 이용한 로컬 클러스터 생성

### 3.1. kind란?

**kind**(Kubernetes IN Docker)는 Docker 컨테이너를 노드로 사용하여 로컬에서 Kubernetes 클러스터를 실행하는 도구입니다.

**장점:**

- 빠른 클러스터 생성/삭제
- 로컬 개발 및 테스트에 적합
- CI/CD 파이프라인 통합 용이

### 3.2. 클러스터 생성

```bash
# 기본 클러스터 생성
kind create cluster --name myk8s

# 특정 버전 및 설정으로 생성
kind create cluster --name myk8s --image kindest/node:v1.32.8 --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  extraPortMappings:
  # NodePort 서비스 접근용 포트 매핑
  - containerPort: 30000
    hostPort: 30000
  - containerPort: 30001
    hostPort: 30001
- role: worker
EOF
```

### 3.3. 클러스터 확인

```bash
# 노드 목록 확인
kubectl get nodes -o wide

# 전체 Pod 확인
kubectl get pods -A -o wide

# 클러스터 정보
kubectl cluster-info

# Kubeconfig 확인
kubectl config view --minify
```

### 3.4. kind 관리 명령어

```bash
# 클러스터 목록
kind get clusters

# 클러스터 삭제
kind delete cluster --name myk8s

# kubeconfig 내보내기
kind export kubeconfig --name myk8s
```

---

## 4. Docker를 사용한 컨테이너 이미지 빌드

### 4.1. Dockerfile 구조

```dockerfile
# 베이스 이미지 지정
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사 및 설치 (캐시 최적화)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# 컨테이너 실행 시 노출할 포트
EXPOSE 8080

# 실행 명령
CMD ["python", "app.py"]
```

### 4.2. 빌드 과정

```bash
# 실습 디렉토리로 이동
cd chapters/ch03/python-app

# 환경 변수 설정
export MYUSER="your-dockerhub-username"
export MYREGISTRY="docker.io"

# Docker 이미지 빌드
docker build -f Dockerfile -t $MYREGISTRY/$MYUSER/pythonapp:latest .

# 빌드된 이미지 확인
docker images | grep pythonapp
```

### 4.3. 이미지 레이어 확인

Docker 이미지는 여러 레이어로 구성됩니다:

```bash
# 이미지 히스토리 확인
docker history $MYREGISTRY/$MYUSER/pythonapp:latest

# 이미지 상세 정보
docker inspect $MYREGISTRY/$MYUSER/pythonapp:latest

# 레이어 정보 (jq 필요)
docker inspect $MYREGISTRY/$MYUSER/pythonapp:latest | jq '.[0].RootFS.Layers'
```

**레이어 구조 예시:**

```
┌─────────────────────────────────────┐
│  Layer 5: COPY . .                  │  ← 애플리케이션 코드
├─────────────────────────────────────┤
│  Layer 4: RUN pip install           │  ← 의존성
├─────────────────────────────────────┤
│  Layer 3: COPY requirements.txt     │  ← 의존성 파일
├─────────────────────────────────────┤
│  Layer 2: WORKDIR /app              │  ← 작업 디렉토리
├─────────────────────────────────────┤
│  Layer 1: python:3.11-slim          │  ← 베이스 이미지
└─────────────────────────────────────┘
```

---

## 5. 컨테이너 실행 및 배포

### 5.1. 로컬에서 컨테이너 실행

```bash
# Docker Hub 로그인
docker login $MYREGISTRY

# 이미지 푸시
docker push $MYREGISTRY/$MYUSER/pythonapp:latest

# 컨테이너 실행
docker run -d --name myweb -p 8080:8080 $MYREGISTRY/$MYUSER/pythonapp:latest

# 애플리케이션 테스트
curl http://127.0.0.1:8080
# 예상 출력: Hello, World!

# 컨테이너 로그 확인
docker logs myweb

# 컨테이너 내부 접속
docker exec -it myweb /bin/bash
```

### 5.2. 정리

```bash
# 컨테이너 중지 및 삭제
docker rm -f myweb

# 로컬 이미지 삭제
docker rmi $MYREGISTRY/$MYUSER/pythonapp:latest
```

---

## 6. Kubernetes에 배포

### 6.1. 매니페스트 작성

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: pythonapp
spec:
  replicas: 2
  selector:
    matchLabels:
      app: pythonapp
  template:
    metadata:
      labels:
        app: pythonapp
    spec:
      containers:
      - name: pythonapp
        image: docker.io/myuser/pythonapp:latest
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: pythonapp
spec:
  type: NodePort
  selector:
    app: pythonapp
  ports:
  - port: 80
    targetPort: 8080
    nodePort: 30000
```

### 6.2. 배포 및 확인

```bash
# 배포
kubectl apply -f deployment.yaml

# Pod 상태 확인
kubectl get pods -l app=pythonapp

# 서비스 확인
kubectl get svc pythonapp

# 접근 테스트 (kind 포트 매핑 설정 필요)
curl http://localhost:30000
```

---

## 7. 이미지 최적화 팁

### 7.1. 멀티 스테이지 빌드

```dockerfile
# 빌드 스테이지
FROM python:3.11 AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# 런타임 스테이지
FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /root/.local /root/.local
COPY . .
ENV PATH=/root/.local/bin:$PATH
CMD ["python", "app.py"]
```

### 7.2. 레이어 캐시 활용

```dockerfile
# 나쁜 예 - 코드 변경 시 모든 레이어 재빌드
COPY . .
RUN pip install -r requirements.txt

# 좋은 예 - 의존성 변경 시에만 pip install 재실행
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
```

### 7.3. .dockerignore 활용

```
# .dockerignore
.git
.gitignore
*.md
__pycache__
*.pyc
.env
node_modules
```

---

## 8. 실습 자료

- [`chapters/ch03/python-app/`](./chapters/ch03/python-app/) - Python 샘플 앱
- [`chapters/ch03/nodejs-app/`](./chapters/ch03/nodejs-app/) - Node.js 샘플 앱
- [`practice.md`](./practice.md) - 상세 실습 명령어 모음

---

## 9. 참고 자료

- [Docker 공식 문서](https://docs.docker.com/)
- [kind 공식 문서](https://kind.sigs.k8s.io/)
- [Dockerfile Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)

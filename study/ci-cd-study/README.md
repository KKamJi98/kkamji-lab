# `CloudNet@` CI/CD 스터디 - 1기 (ArgoCD)

`CloudNet@` 커뮤니티의 Gasida님이 진행한 CI/CD 스터디 1기 내용을 정리한 저장소입니다.

## 프로젝트 구조

스터디 자료는 "GitOps Cookbook"의 내용을 기반으로 구성되어 있으며, 주차별 학습 내용과 실습 코드를 포함합니다.

```
.
├── 1w-gitops-image-build/
│   ├── README.md          # 1주차 실습 가이드
│   ├── practice.md        # 실습 상세 명령어 모음
│   └── chapters/          # "GitOps Cookbook" 관련 실습 자료
│       ├── ch03/          # 3장: 다양한 애플리케이션 배포
│       └── ch06/          # 6장: RBAC 설정
└── README.md              # 본 파일
```

## 주차별 학습 내용

### [1주차: 컨테이너 이미지 빌드 및 로컬 쿠버네티스 환경 구성](./1w-gitops-image-build/README.md)

- `kind`를 사용하여 로컬 쿠버네티스 클러스터를 구축합니다.
- `Docker`를 이용해 다양한 애플리케이션(`python`, `nodejs` 등)의 컨테이너 이미지를 빌드하고, `Docker Hub`에 푸시하는 과정을 실습합니다.
- "GitOps Cookbook" 3장의 내용을 기반으로 실습을 진행합니다.

## 시작하기

각 주차별 디렉토리의 `README.md` 파일을 참고하여 실습을 진행할 수 있습니다.

- **1주차 실습**: [`1w-gitops-image-build/README.md`](./1w-gitops-image-build/README.md)

## 관련 자료

- **[GitOps Cookbook](https://www.packtpub.com/product/gitops-cookbook/9781801072360)**: 스터디의 기반이 된 원서입니다
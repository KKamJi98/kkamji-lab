# Packer EKS Custom AMI

EKS 최적화 커스텀 AMI를 빌드하는 Packer 프로젝트입니다. Amazon Linux 2023 기반의 x86, arm64 아키텍처를 지원합니다.

## Packer란?

[Packer](https://www.packer.io/)는 HashiCorp에서 개발한 오픈소스 도구로, 단일 소스 설정에서 여러 플랫폼용 동일한 머신 이미지를 자동으로 생성합니다.

**주요 특징:**
- Infrastructure as Code로 AMI 관리
- 여러 아키텍처/플랫폼 동시 빌드
- Provisioner를 통한 이미지 커스터마이징
- 반복 가능하고 일관된 이미지 생성

## 설치

### macOS
```bash
brew tap hashicorp/tap
brew install hashicorp/tap/packer
```

### Linux (Ubuntu/Debian)
```bash
curl -fsSL https://apt.releases.hashicorp.com/gpg | sudo apt-key add -
sudo apt-add-repository "deb [arch=amd64] https://apt.releases.hashicorp.com $(lsb_release -cs) main"
sudo apt-get update && sudo apt-get install packer
```

### 설치 확인
```bash
packer version
```

## 프로젝트 구조

```
.
├── build.pkr.hcl           # 빌드 블록 및 provisioner 정의
├── sources.pkr.hcl         # AMI source 설정 (x86, arm64)
├── variables.pkr.hcl       # 변수 선언
├── data.pkr.hcl            # AMI 자동 조회 data source
├── vars/
│   └── eks-1.34.pkrvars.hcl  # EKS 버전별 변수 값
├── scripts/
│   └── bootstrap.sh        # Golden Image 설정 (보안 예시)
└── tools/
    └── verify-ami-ssm.sh   # AMI SSM 연결 검증 스크립트
```

## 빠른 시작

```bash
# 1. 플러그인 초기화
packer init .

# 2. 설정 검증
packer validate .

# 3. AMI 빌드 (x86, arm64만)
packer build -only="amazon-ebs.x86,amazon-ebs.arm64" .
```

## 사용법

### 초기화
Packer 플러그인을 다운로드합니다. 최초 1회 또는 플러그인 버전 변경 시 실행합니다.
```bash
packer init .
```

### 포맷팅
HCL 파일을 표준 형식으로 정리합니다.
```bash
packer fmt .
```

### 검증
설정 파일의 문법 및 구성을 검증합니다.
```bash
packer validate .

# 변수 파일과 함께 검증
packer validate -var-file=vars/eks-1.34.pkrvars.hcl .
```

### 빌드
AMI를 빌드합니다.
```bash
# 전체 빌드 (x86, arm64)
packer build .

# 변수 오버라이드
packer build \
  -var 'subnet_id=subnet-xxxx' \
  -var 'security_group_id=sg-xxxx' \
  -var 'iam_instance_profile=packer-eks-ssm' \
  .
```

## 빌드 타겟

사용 가능한 타겟: `amazon-ebs.x86`, `amazon-ebs.arm64`

```bash
# 특정 타겟만 빌드
packer build -only="amazon-ebs.x86" .
```

## AMI 자동 조회

Base AMI는 `data.pkr.hcl`의 data source를 통해 **빌드 시점에 자동으로 최신 AMI를 조회**합니다.

| 아키텍처 | AMI Name Pattern |
|---------|------------------|
| x86     | `amazon-eks-node-al2023-x86_64-standard-{eks_version}-*` |
| arm64   | `amazon-eks-node-al2023-arm64-standard-{eks_version}-*` |

EKS 버전 변경 시 `vars/eks-1.34.pkrvars.hcl`의 `eks_version`만 수정하면 됩니다.

## 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `region` | AWS 리전 | `ap-northeast-2` |
| `eks_version` | EKS 버전 | `1.34` |
| `subnet_id` | 빌드용 서브넷 ID | - |
| `security_group_id` | 빌드용 보안 그룹 ID | - |
| `iam_instance_profile` | EC2 인스턴스 프로파일 | - |
| `instance_type_x86` | x86 빌드 인스턴스 타입 | `t3.large` |
| `instance_type_arm64` | arm64 빌드 인스턴스 타입 | `t4g.large` |

## 요구사항

### IAM Instance Profile
`iam_instance_profile`에 지정된 프로파일에 다음 정책이 필요합니다:
- `AmazonSSMManagedInstanceCore` - SSM Session Manager 연결용

### 네트워크
SSM Session Manager를 통해 SSH 연결하므로:
- **Inbound**: 필요 없음
- **Outbound**: 443 포트 (SSM endpoints)

Private Subnet 사용 시 다음 중 하나 필요:
- NAT Gateway
- SSM VPC Endpoints (`ssm`, `ssmmessages`, `ec2messages`)

## AMI 명명 규칙

```
custom-eks-{eks_version}-amazon-linux-2023-{variant}-v{YYYYMMDD}
```

예시:
- `custom-eks-1.34-amazon-linux-2023-x86-v20260112`
- `custom-eks-1.34-amazon-linux-2023-arm64-v20260112`

## 검증 도구

빌드된 AMI의 SSM 연결을 검증합니다:
```bash
./tools/verify-ami-ssm.sh -i <instance-id> -r ap-northeast-2
```
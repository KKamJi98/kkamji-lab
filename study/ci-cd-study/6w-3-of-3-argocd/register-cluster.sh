# ==========================================
# 1. 환경 변수 설정
# ==========================================
# 대상 클러스터 (Argo CD에 등록될 클러스터 및 주소)
TARGET_CONTEXT="kind-prd"
TARGET_INTERNAL_URL="https://prd-control-plane:6443" # ArgoCD가 접속할 내부 주소
CLUSTER_NAME_IN_ARGO="prd-cluster"

# ArgoCD가 설치된 클러스터
ARGOCD_CONTEXT="kind-mgmt"
ARGOCD_NAMESPACE="argocd"

echo "[${TARGET_CONTEXT}] 클러스터를 [${ARGOCD_CONTEXT}]의 ArgoCD에 등록을 시작합니다..."

# ==========================================
# 2. 대상 클러스터에 ServiceAccount 및 RBAC 생성
# ==========================================
cat <<EOF | kubectl --context="${TARGET_CONTEXT}" apply -f -
apiVersion: v1
kind: ServiceAccount
metadata:
  name: argocd-manager
  namespace: kube-system
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argocd-manager-role
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
- nonResourceURLs: ["*"]
  verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argocd-manager-role-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: argocd-manager-role
subjects:
- kind: ServiceAccount
  name: argocd-manager
  namespace: kube-system
EOF

# ==========================================
# 3. 토큰 시크릿 생성 (Long Live Token)
# ==========================================
cat <<EOF | kubectl --context="${TARGET_CONTEXT}" apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: argocd-manager-token
  namespace: kube-system
  annotations:
    kubernetes.io/service-account.name: argocd-manager
type: kubernetes.io/service-account-token
EOF

echo "⏳ 토큰 생성을 대기 중..."
sleep 2

# ==========================================
# 4. 토큰 및 CA 인증서 추출
# ==========================================
BEARER_TOKEN=$(kubectl --context="${TARGET_CONTEXT}" -n kube-system get secret argocd-manager-token -o jsonpath='{.data.token}' | base64 -d)
CA_DATA=$(kubectl --context="${TARGET_CONTEXT}" -n kube-system get secret argocd-manager-token -o jsonpath='{.data.ca\.crt}')

# ==========================================
# 5. ArgoCD 클러스터(mgmt)에 Secret 등록
# ==========================================
cat <<EOF | kubectl --context="${ARGOCD_CONTEXT}" apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: cluster-${CLUSTER_NAME_IN_ARGO}
  namespace: ${ARGOCD_NAMESPACE}
  labels:
    argocd.argoproj.io/secret-type: cluster
    name: ${CLUSTER_NAME_IN_ARGO}
type: Opaque
stringData:
  name: ${CLUSTER_NAME_IN_ARGO}
  server: ${TARGET_INTERNAL_URL}
  config: |
    {
      "bearerToken": "${BEARER_TOKEN}",
      "tlsClientConfig": {
        "insecure": false,
        "caData": "${CA_DATA}"
      }
    }
EOF

echo "등록 완료! ArgoCD에서 확인해주세요."
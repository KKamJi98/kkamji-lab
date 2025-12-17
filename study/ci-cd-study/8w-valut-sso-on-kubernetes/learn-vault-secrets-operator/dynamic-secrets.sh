set -xe
export VAULT_NAMESPACE=us-west-org

vault secrets enable -path=demo-db database
sleep 20
vault write demo-db/config/demo-db \
   plugin_name=postgresql-database-plugin \
   allowed_roles="dev-postgres" \
   connection_url="postgresql://{{username}}:{{password}}@postgres-postgresql.postgres.svc.cluster.local:5432/postgres?sslmode=disable" \
   username="postgres" \
   password="secret-pass"

vault write demo-db/roles/dev-postgres \
   db_name=demo-db \
   creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
      GRANT ALL PRIVILEGES ON DATABASE postgres TO \"{{name}}\";" \
   revocation_statements="REVOKE ALL ON DATABASE postgres FROM  \"{{name}}\";" \
   backend=demo-db \
   name=dev-postgres \
   default_ttl="1m" \
   max_ttl="1m"

vault policy write demo-auth-policy-db - <<EOF
path "demo-db/creds/dev-postgres" {
   capabilities = ["read"]
}
EOF

vault secrets enable -path=demo-transit transit
sleep 20

vault write -force demo-transit/keys/vso-client-cache
vault policy write demo-auth-policy-operator - <<EOF
path "demo-transit/encrypt/vso-client-cache" {
   capabilities = ["create", "update"]
}
path "demo-transit/decrypt/vso-client-cache" {
   capabilities = ["create", "update"]
}
EOF

vault write auth/demo-auth-mount/role/auth-role-operator \
      bound_service_account_names=vault-secrets-operator-controller-manager \
      bound_service_account_namespaces=vault-secrets-operator-system \
      token_ttl=0 \
      token_period=120 \
      token_policies=demo-auth-policy-operator \
      audience=vault

vault write auth/demo-auth-mount/role/auth-role \
   bound_service_account_names=demo-dynamic-app \
   bound_service_account_namespaces=demo-ns \
   token_ttl=0 \
   token_period=120 \
   token_policies=demo-auth-policy-db \
   audience=vault
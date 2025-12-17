VAULT_LICENSE?="bob"
KBCTL_BIN?=$(shell which kubectl)
KBCTL_EXEC_VAULT?=$(KBCTL_BIN) exec -it vault-0 -n vault -- 
VAULT_NAMESPACE := us-west-org
ENT_ARGS :=--namespace $(VAULT_NAMESPACE)

all-ent: start-minikube install-vault-ent-cluster config-vault install-vault-secrets-operator deploy-and-sync-a-secret rotate-the-secret install-postgresql-pod setup-postgresql transit-encryption setup-dynamic-secrets create-the-application
# svc-health config-vault vso-install deploy-static-secret dynamic-secrets
define header
	$(info Running >>> $(1)$(END))
endef

## list all targets
.PHONY: no_targets__ list
no_targets__:
list:
	sh -c "$(MAKE) -p no_targets__ | awk -F':' '/^[a-zA-Z0-9][^\$$#\/\\t=]*:([^=]|$$)/ {split(\$$1,A,/ /);for(i in A)print A[i]}' | grep -v '__\$$' | sort"

.PHONY: test
test: 
	$(call header,$@)
	@echo $(VAULT_LICENSE)
	@echo $(KBCTL_EXEC_VAULT)
	kubectl get pods -n vault
	kubectl get secrets -n app
	echo "username: $$(kubectl get secrets -n app secretkv -o jsonpath="{.data.username}" | base64 -d), pass: $$(kubectl get secrets -n app secretkv -o jsonpath="{.data.password}" | base64 -d)"
	@$(KBCTL_EXEC_VAULT) vault write $(ENT_ARGS) demo-db/config/demo-db \
		plugin_name=postgresql-database-plugin \
  		allowed_roles="dev-postgres" \
  		connection_url="postgresql://{{username}}:{{password}}@postgres-postgresql.postgres.svc.cluster.local:5432/postgres?sslmode=disable" \
  		username="postgres" \
  		password="secret-pass"
	@echo "dynamic username: $$(kubectl get secrets -n demo-ns -o jsonpath="{.items[1].data.username}" | base64 -d), pass: $$(kubectl get secrets -n demo-ns -o jsonpath="{.items[1].data.password}" | base64 -d)"

.PHONY: start-minikube
start-minikube:
	$(call header,$@)
	@minikube start 
	@sleep 5


.PHONY: destroy clean-up
destroy:
clean-up:
	$(call header,$@)
	@minikube delete
	@sleep 30


.PHONY: kill-ns
kill-ns:
	$(call header,$@)
	@kubectl delete ns vault app vault-secrets-operator-system demo-ns postgres
	sleep 5

# .PHONY: 
# vault-prereqs:
# 	$(call header,$@)
# 	@kubectl create ns vault
#	@kubectl create secret generic vault-license --from-literal license=$(VAULT_LICENSE) -n vault
#	@kubectl create secret generic vault-license --from-file license=vault-ent/vault-license.lic -n vault

.PHONY: prep-cluster-install
prep-cluster-install:
	$(call header,$@)
	helm repo add hashicorp https://helm.releases.hashicorp.com
	helm repo update
	helm search repo hashicorp/vault


.PHONY: install-vault-cluster
install-vault-cluster: prep-cluster-install
	$(call header,$@)
	helm install vault hashicorp/vault -n vault --create-namespace --values vault/vault-values.yaml
	kubectl get pods -n vault


.PHONY: install-vault-ent-cluster
install-vault-ent-cluster: prep-cluster-install
	$(call header,$@)
	kubectl create ns vault
	sleep 10
	kubectl create secret generic vault-license --from-literal license=$(VAULT_LICENSE) -n vault
	helm install vault hashicorp/vault -n vault --values vault-ent/vault-values.yaml
	kubectl wait --for=jsonpath='{.status.phase}'=Running pod --all --namespace vault --timeout=1m
	kubectl get pods -n vault


# .PHONY: vault-upgrade
# vault-upgrade:
# 	$(call header,$@)
# 	@helm upgrade vault hashicorp/vault -n vault --values vault/my-values.yaml
# 	@sleep 10
# 	@kubectl wait --for=jsonpath='{.status.phase}'=Running pod --all --namespace vault --timeout=1m
# 	@kubectl get all -n vault

.PHONY: uninstall-vault
uninstall-vault:
	$(call header,$@)
	@helm uninstall vault -n vault
	$(KBCTL_BIN) delete ns vault
	@sleep 10

.PHONY: reinstall-vault
reinstall-vault: uninstall-vault install-vault

.PHONY: status
status:
	$(call header,$@)
	@kubectl exec -n vault -ti vault-0 -- vault status

.PHONY: logs
logs:
	$(call header,$@)
	@kubectl logs -n vault sts/vault -f

.PHONY: events
events:
	$(call header,$@)
	@kubectl get events --all-namespaces --sort-by='.metadata.creationTimestamp' -w

# need set up - kb proxy
.PHONY: svc-health
svc-health:
	$(call header,$@)
	@curl -s http://localhost:8200/v1/sys/health | jq

.PHONY: health
health:
	$(call header,$@)
	@kubectl exec -n vault -ti vault-0 -- wget -qO - http://localhost:8200/v1/sys/health

.PHONY: vars
vars:
	@echo "export VAULT_ADDR=http://127.0.0.1:8200"
	@echo "export VAULT_TOKEN=root"

.PHONY: install-vault-secrets-operator
install-vault-secrets-operator:
	$(call header,$@)
	@helm install vault-secrets-operator hashicorp/vault-secrets-operator \
		-n vault-secrets-operator-system \
		--create-namespace \
		--values vault-ent/vault-operator-values.yaml \
		--version 0.8.0
	@sleep 10
	@kubectl wait --for=jsonpath='{.status.phase}'=Running pod \
		--all --namespace vault-secrets-operator-system --timeout=1m
	@kubectl wait --for=jsonpath='{.status.phase}'=Running pod --all --namespace vault-secrets-operator-system --timeout=1m
	@sleep 10

.PHONY: uninstall-vso
uninstall-vso:
	$(call header,$@)
	@helm uninstall vault-secrets-operator -n vault-secrets-operator-system

.PHONY: vso-logs
vso-logs:
	$(call header,$@)
	@kubectl logs -n vault-secrets-operator-system -l app.kubernetes.io/name=vault-secrets-operator -f

# .PHONY: static-secrets
# static-secrets:
.PHONY: config-vault
config-vault:
	$(call header,$@)
	$(KBCTL_EXEC_VAULT) vault namespace create us-west-org
	$(KBCTL_EXEC_VAULT) vault auth enable $(ENT_ARGS) -path demo-auth-mount kubernetes
		$(KBCTL_EXEC_VAULT) vault write $(ENT_ARGS) auth/demo-auth-mount/config \
			kubernetes_host=https://$$(kubectl exec vault-0 -n vault --  printenv KUBERNETES_PORT_443_TCP_ADDR):443
	$(KBCTL_EXEC_VAULT) vault secrets enable  $(ENT_ARGS) -path=kvv2 kv-v2
	$(KBCTL_BIN) cp -n vault support/webapp.hcl vault-0:/tmp/webapp.hcl 
	$(KBCTL_EXEC_VAULT) vault policy write  $(ENT_ARGS) webapp /tmp/webapp.hcl
	$(KBCTL_EXEC_VAULT) vault write  $(ENT_ARGS) auth/demo-auth-mount/role/role1 \
   		bound_service_account_names=demo-static-app \
   		bound_service_account_namespaces=app \
   		policies=webapp \
   		audience=vault \
   		token_period=2m
	$(KBCTL_EXEC_VAULT) vault kv put $(ENT_ARGS) kvv2/webapp/config username="static-user" password="static-password"
	
# @kubectl cp -n vault ./static-secrets.sh vault-0:/tmp/static-secrets.sh
# @kubectl exec -n vault -ti vault-0 -- /bin/sh -c '/tmp/static-secrets.sh'

.PHONY: deploy-and-sync-a-secret
deploy-and-sync-a-secret:
	$(call header,$@)
	@kubectl create ns app
	@sleep 5
	@kubectl apply -f vault-ent/vault-auth-static.yaml
	@kubectl apply -f vault-ent/static-secret.yaml
	@sleep 3
	@echo "username: $$(kubectl get secrets -n app secretkv -o jsonpath="{.data.username}" | base64 -d), pass: $$(kubectl get secrets -n app secretkv -o jsonpath="{.data.password}" | base64 -d)"

.PHONY: rotate-the-secret
rotate-the-secret:
	$(call header,$@)
		@echo "username: $$(kubectl get secrets -n app secretkv -o jsonpath="{.data.username}" | base64 -d), pass: $$(kubectl get secrets -n app secretkv -o jsonpath="{.data.password}" | base64 -d)"
		$(KBCTL_EXEC_VAULT) vault kv put $(ENT_ARGS) kvv2/webapp/config username="static-user2" password="static-password2"
				@echo "username: $$(kubectl get secrets -n app secretkv -o jsonpath="{.data.username}" | base64 -d), pass: $$(kubectl get secrets -n app secretkv -o jsonpath="{.data.password}" | base64 -d)"

.PHONY: uninstall-secret
uninstall-secret:
	$(call header,$@)
	kubectl delete ns app

.PHONY: install-postgresql-pod
install-postgresql-pod:
	$(call header,$@)
	@kubectl create ns postgres
	@sleep 10
	helm repo add bitnami https://charts.bitnami.com/bitnami
	helm upgrade --install postgres bitnami/postgresql --namespace postgres --set auth.audit.logConnections=true  --set auth.postgresPassword=secret-pass
	@kubectl wait --for=jsonpath='{.status.phase}'=Running pod --all --namespace postgres --timeout=1m
## need a pause to let connection be available - is there a way to test it?
	sleep 5

.PHONY: uninstall-postgresql-pod
uninstall-postgresql-pod:
	$(call header,$@)
	@kubectl delete ns postgres
	@$(KBCTL_EXEC_VAULT) vault secrets disable $(ENT_ARGS) demo-db
	sleep 10

.PHONY: setup-postgresql
setup-postgresql:
	$(call header,$@)
	$(KBCTL_EXEC_VAULT) vault secrets enable $(ENT_ARGS) -path=demo-db database
	sleep 10
	$(KBCTL_EXEC_VAULT) vault write $(ENT_ARGS) demo-db/config/demo-db \
		plugin_name=postgresql-database-plugin \
  		allowed_roles="dev-postgres" \
  		connection_url="postgresql://{{username}}:{{password}}@postgres-postgresql.postgres.svc.cluster.local:5432/postgres?sslmode=disable" \
  		username="postgres" \
  		password="secret-pass"
	$(KBCTL_EXEC_VAULT) vault write $(ENT_ARGS) demo-db/roles/dev-postgres db_name=demo-db \
		creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
      	GRANT ALL PRIVILEGES ON DATABASE postgres TO \"{{name}}\";" \
   		revocation_statements="REVOKE ALL ON DATABASE postgres FROM  \"{{name}}\";" \
   		backend=demo-db \
   		name=dev-postgres \
   		default_ttl="1m" \
   		max_ttl="1m"
	$(KBCTL_BIN) cp -n vault support/postgresql.hcl vault-0:/tmp/postgresql.hcl
	$(KBCTL_EXEC_VAULT) vault policy write $(ENT_ARGS) demo-auth-policy-db /tmp/postgresql.hcl

.PHONY: transit-encryption
transit-encryption:
	$(call header,$@)
	$(KBCTL_EXEC_VAULT) vault secrets enable $(ENT_ARGS) -path=demo-transit transit
	$(KBCTL_EXEC_VAULT) vault write  $(ENT_ARGS) -force demo-transit/keys/vso-client-cache
	$(KBCTL_BIN) cp -n vault support/demo-auth-policy-operator.hcl vault-0:/tmp/demo-auth-policy-operator.hcl
	$(KBCTL_EXEC_VAULT) vault policy write $(ENT_ARGS) demo-auth-policy-operator /tmp/demo-auth-policy-operator.hcl
	$(KBCTL_EXEC_VAULT) vault write $(ENT_ARGS) auth/demo-auth-mount/role/auth-role-operator \
		bound_service_account_names=vault-secrets-operator-controller-manager \
		bound_service_account_namespaces=vault-secrets-operator-system \
		token_ttl=0 \
		token_period=120 \
		token_policies=demo-auth-policy-operator \
		audience=vault

.PHONY: setup-dynamic-secrets
setup-dynamic-secrets:
	$(call header,$@)
	$(KBCTL_EXEC_VAULT) vault write $(ENT_ARGS) auth/demo-auth-mount/role/auth-role \
   		bound_service_account_names=demo-dynamic-app \
   		bound_service_account_namespaces=demo-ns \
   		token_ttl=0 \
   		token_period=120 \
   		token_policies=demo-auth-policy-db \
		audience=vault

.PHONY: create-the-application
create-the-application:
	$(call header,$@)
	@kubectl create ns demo-ns
	@sleep 10
	@kubectl apply -f vault-ent/dynamic-secrets/.
	@sleep 10
	echo "dynamic username: $(kubectl get secrets -n demo-ns -o jsonpath="{.items[1].data.username}" | base64 -d), pass: $(kubectl get secrets -n demo-ns -o jsonpath="{.items[1].data.password}" | base64 -d)"


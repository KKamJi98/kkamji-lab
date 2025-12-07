KUBE_CONTEXT ?= rancher-desktop
KUBECTL ?= kubectl
HELM ?= helm
ISTIOCTL ?= istioctl
ISTIO_PROFILE ?= default
ISTIO_PILOT_CPU ?= 250m
ISTIO_PILOT_MEM ?= 512Mi
ISTIO_NAMESPACE ?= istio-system
ISTIO_OVERLAY_CNI ?= ./01-install-istio/istio-cni.yaml
ISTIO_ROLLOUT_TIMEOUT ?= 180s
ISTIO_PURGE ?= false

ISTIO_BASE_DIR ?= ./01-install-istio
KPS_RELEASE ?= monitoring
KPS_NAMESPACE ?= monitoring
KPS_CHART_VERSION ?= 79.12.0
KPS_CHART ?= $(ISTIO_BASE_DIR)/kube-prometheus-stack-$(KPS_CHART_VERSION).tgz
KPS_VALUES ?= $(ISTIO_BASE_DIR)/kube-prometheus-stack/kkamji_values.yaml

KIALI_MANIFEST ?= $(ISTIO_BASE_DIR)/kiali/kiali.yaml
KIALI_NAMESPACE ?= istio-system

.DEFAULT_GOAL := help

.PHONY: help info contexts \
	istio istio-install istio-install-init istio-install-cni \
	istio-uninstall istio-delete istio-verify \
	kube-prometheus-stack kube-prometheus-stack-uninstall \
	kiali kiali-delete monitoring-install monitoring-delete \
	check-kubectl check-istioctl check-helm check-context check-kps-chart \
	check-istio-overlay

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  help            Show this help"
	@echo "  info            Show current context and nodes"
	@echo "  contexts        List kubeconfig contexts"
	@echo "  istio           Alias of istio-install (init mode)"
	@echo "  istio-install   Alias of istio-install-init"
	@echo "  istio-install-init Install Istio (init mode, profile=$(ISTIO_PROFILE))"
	@echo "  istio-install-cni  Install Istio with CNI overlay"
	@echo "  istio-uninstall Uninstall Istio (set ISTIO_PURGE=true to purge CRDs)"
	@echo "  istio-delete    Alias of istio-uninstall"
	@echo "  istio-verify    Run istioctl verify-install"
	@echo "  kube-prometheus-stack         Install kube-prometheus-stack via Helm"
	@echo "  kube-prometheus-stack-uninstall Uninstall kube-prometheus-stack release"
	@echo "  kiali            Apply Kiali manifest to $(KIALI_NAMESPACE)"
	@echo "  kiali-delete     Delete Kiali manifest from $(KIALI_NAMESPACE)"
	@echo "  monitoring-install Install kube-prometheus-stack and Kiali"
	@echo "  monitoring-delete  Delete Kiali and uninstall kube-prometheus-stack"

ISTIO_INSTALL_FLAGS = --set profile=$(ISTIO_PROFILE) -y \
	--set values.pilot.resources.requests.cpu=$(ISTIO_PILOT_CPU) \
	--set values.pilot.resources.requests.memory=$(ISTIO_PILOT_MEM)

info: check-kubectl
	@echo "Current context: $$($(KUBECTL) config current-context)"
	@$(KUBECTL) get nodes

contexts: check-kubectl
	@$(KUBECTL) config get-contexts

istio: istio-install

istio-install: istio-install-init

istio-install-init: check-kubectl check-istioctl check-context
	@$(ISTIOCTL) install $(ISTIO_INSTALL_FLAGS)
	@$(KUBECTL) -n $(ISTIO_NAMESPACE) rollout status deploy/istiod --timeout=$(ISTIO_ROLLOUT_TIMEOUT)

istio-install-cni: check-kubectl check-istioctl check-context check-istio-overlay
	@$(ISTIOCTL) install $(ISTIO_INSTALL_FLAGS) -f $(ISTIO_OVERLAY_CNI)
	@$(KUBECTL) -n $(ISTIO_NAMESPACE) rollout status deploy/istiod --timeout=$(ISTIO_ROLLOUT_TIMEOUT)
	@$(KUBECTL) -n $(ISTIO_NAMESPACE) rollout status ds/istio-cni-node --timeout=$(ISTIO_ROLLOUT_TIMEOUT)

istio-uninstall: check-kubectl check-istioctl check-context
	@if [ "$(ISTIO_PURGE)" = "true" ]; then \
		$(ISTIOCTL) uninstall -y --purge; \
	else \
		$(ISTIOCTL) uninstall -y; \
	fi
	@$(KUBECTL) delete namespace $(ISTIO_NAMESPACE) --ignore-not-found=true

istio-delete: istio-uninstall

istio-verify: check-kubectl check-istioctl check-context
	@$(ISTIOCTL) verify-install

kube-prometheus-stack: check-helm check-kubectl check-context check-kps-chart
	@$(HELM) upgrade -i $(KPS_RELEASE) $(KPS_CHART) \
		--namespace $(KPS_NAMESPACE) \
		--create-namespace \
		--values $(KPS_VALUES) \
		--version $(KPS_CHART_VERSION)

kube-prometheus-stack-uninstall: check-helm check-kubectl check-context
	@$(HELM) uninstall $(KPS_RELEASE) --namespace $(KPS_NAMESPACE) || true

kiali: check-kubectl check-context
	@$(KUBECTL) apply -n $(KIALI_NAMESPACE) -f $(KIALI_MANIFEST)

kiali-delete: check-kubectl check-context
	@$(KUBECTL) delete -n $(KIALI_NAMESPACE) -f $(KIALI_MANIFEST) --ignore-not-found

monitoring-install: kube-prometheus-stack kiali

monitoring-delete: kiali-delete kube-prometheus-stack-uninstall

check-kubectl:
	@command -v $(KUBECTL) >/dev/null 2>&1 || { echo "$(KUBECTL) binary not found in PATH"; exit 1; }

check-istioctl:
	@command -v $(ISTIOCTL) >/dev/null 2>&1 || { echo "$(ISTIOCTL) binary not found in PATH"; exit 1; }

check-helm:
	@command -v $(HELM) >/dev/null 2>&1 || { echo "$(HELM) binary not found in PATH"; exit 1; }

check-context: check-kubectl
	@current=$$($(KUBECTL) config current-context); \
		test "$${current}" = "$(KUBE_CONTEXT)" || { \
			echo "Current context '$${current}' does not match expected '$(KUBE_CONTEXT)'."; \
			echo "Override with KUBE_CONTEXT=<context> if intentional."; \
			exit 1; \
		}

check-kps-chart:
	@test -f $(KPS_CHART) || { echo "Chart file $(KPS_CHART) not found"; exit 1; }

check-istio-overlay:
	@test -f $(ISTIO_OVERLAY_CNI) || { echo "Istio CNI overlay $(ISTIO_OVERLAY_CNI) not found"; exit 1; }

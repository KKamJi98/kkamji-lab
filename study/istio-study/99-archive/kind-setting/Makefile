CLUSTER_NAME ?= kkamji
CONFIG_FILE ?= kind-config.yaml
NETWORK_NAME ?= kind
CONTAINER_RUNTIME ?= docker
KIND ?= kind
METALLB_VERSION ?= v0.15.3
METALLB_MANIFEST ?= https://raw.githubusercontent.com/metallb/metallb/$(METALLB_VERSION)/config/manifests/metallb-native.yaml
METALLB_CONFIG ?= metallb-config.yaml
ISTIOCTL ?= istioctl
ISTIO_PROFILE ?= default
ISTIO_PILOT_CPU ?= 250m
ISTIO_PILOT_MEM ?= 512Mi

.DEFAULT_GOAL := help

.PHONY: help setup setup-metallb setup-istio up info delete restart network metallb \
	istio check-kind check-config check-runtime check-kubectl check-metallb-config \
	check-istioctl check-cluster

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Targets:"
	@echo "  help    Show this help"
	@echo "  setup   Create cluster and show cluster info"
	@echo "  setup-metallb Create cluster, install MetalLB, and show cluster info"
	@echo "  setup-istio Create cluster, install MetalLB and Istio, then show cluster info"
	@echo "  up      Create a kind cluster named $(CLUSTER_NAME) with $(CONFIG_FILE) (ensures network $(NETWORK_NAME) exists)"
	@echo "  network Create container network $(NETWORK_NAME) (podman) if it does not exist"
	@echo "  metallb Install MetalLB $(METALLB_VERSION) manifest and address pool"
	@echo "  istio   Install Istio ($(ISTIO_PROFILE)) with pilot resource requests"
	@echo "  info    Show clusters and nodes for $(CLUSTER_NAME)"
	@echo "  delete  Delete the cluster named $(CLUSTER_NAME)"
	@echo "  restart Delete and recreate the cluster named $(CLUSTER_NAME)"

setup: up info

setup-metallb: up metallb info

setup-istio: up istio info

up: check-kind check-config network
	@$(KIND) get clusters | grep -q "^$(CLUSTER_NAME)$$" \
		&& echo "Cluster '$(CLUSTER_NAME)' already exists. Skipping create." \
		|| $(KIND) create cluster --name $(CLUSTER_NAME) --config $(CONFIG_FILE)

network: check-runtime
	@$(CONTAINER_RUNTIME) network inspect $(NETWORK_NAME) >/dev/null 2>&1 \
		&& echo "Network '$(NETWORK_NAME)' already exists. Skipping create." \
		|| $(CONTAINER_RUNTIME) network create --subnet 172.20.0.0/16 --gateway 172.20.0.1 $(NETWORK_NAME)

info: check-kind
	@$(KIND) get clusters
	@$(KIND) get nodes --name $(CLUSTER_NAME) || true

delete: check-kind
	@$(KIND) get clusters | grep -q "^$(CLUSTER_NAME)$$" \
		&& $(KIND) delete cluster --name $(CLUSTER_NAME) \
		|| echo "Cluster '$(CLUSTER_NAME)' not found. Nothing to delete."

restart: check-kind
	@$(MAKE) delete
	@$(MAKE) up

metallb: check-kubectl check-metallb-config
	@kubectl apply -f $(METALLB_MANIFEST)
	@kubectl -n metallb-system rollout status deploy/controller --timeout=30s
	@kubectl -n metallb-system rollout status daemonset/speaker --timeout=30s
	@kubectl apply -f $(METALLB_CONFIG)

istio: check-kubectl check-istioctl check-cluster
	@$(ISTIOCTL) install --set profile=$(ISTIO_PROFILE) -y \
		--set values.pilot.resources.requests.cpu=$(ISTIO_PILOT_CPU) \
		--set values.pilot.resources.requests.memory=$(ISTIO_PILOT_MEM)

check-kind:
	@command -v $(KIND) >/dev/null 2>&1 || { echo "kind binary not found in PATH"; exit 1; }

check-config:
	@test -f $(CONFIG_FILE) || { echo "Config file '$(CONFIG_FILE)' not found"; exit 1; }

check-runtime:
	@command -v $(CONTAINER_RUNTIME) >/dev/null 2>&1 || { echo "$(CONTAINER_RUNTIME) binary not found in PATH"; exit 1; }

check-kubectl:
	@command -v kubectl >/dev/null 2>&1 || { echo "kubectl binary not found in PATH"; exit 1; }

check-metallb-config:
	@test -f $(METALLB_CONFIG) || { echo "MetalLB config file '$(METALLB_CONFIG)' not found"; exit 1; }

check-istioctl:
	@command -v $(ISTIOCTL) >/dev/null 2>&1 || { echo "$(ISTIOCTL) binary not found in PATH"; exit 1; }

check-cluster:
	@kubectl version --short >/dev/null 2>&1 || { echo "kubectl cannot reach the current cluster"; exit 1; }

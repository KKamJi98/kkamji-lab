# cert-manager

cert-manager is a Kubernetes addon to automate the management and issuance of
TLS certificates from various issuing sources.

It will ensure certificates are valid and up to date periodically, and attempt
to renew certificates at an appropriate time before expiry.

---

## 1. Prerequisites

- Kubernetes 1.22+

---

## 2. Installing the Chart

Full installation instructions, including details on how to configure extra
functionality in cert-manager can be found in the [installation docs](https://cert-manager.io/docs/installation/kubernetes/).

Before installing the chart, you must first install the cert-manager CustomResourceDefinition resources.
This is performed in a separate step to allow you to easily uninstall and reinstall cert-manager without deleting your installed custom resources.

```bash
$ kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.2/cert-manager.crds.yaml
```

To install the chart with the release name `my-release`:

```console
## Add the Jetstack Helm repository
$ helm repo add jetstack https://charts.jetstack.io

## Install the cert-manager helm chart
$ helm install my-release --namespace cert-manager --version v1.14.2 jetstack/cert-manager
```

In order to begin issuing certificates, you will need to set up a ClusterIssuer
or Issuer resource (for example, by creating a 'letsencrypt-staging' issuer).

More information on the different types of issuers and how to configure them
can be found in [our documentation](https://cert-manager.io/docs/configuration/).

For information on how to configure cert-manager to automatically provision
Certificates for Ingress resources, take a look at the
[Securing Ingresses documentation](https://cert-manager.io/docs/usage/ingress/).

> **Tip**: List all releases using `helm list`

---

## 3. Upgrading the Chart

Special considerations may be required when upgrading the Helm chart, and these
are documented in our full [upgrading guide](https://cert-manager.io/docs/installation/upgrading/).

**Please check here before performing upgrades!**

---

## 4. Uninstalling the Chart

To uninstall/delete the `my-release` deployment:

```console
$ helm delete my-release
```

The command removes all the Kubernetes components associated with the chart and deletes the release.

If you want to completely uninstall cert-manager from your cluster, you will also need to
delete the previously installed CustomResourceDefinition resources:

```console
$ kubectl delete -f https://github.com/cert-manager/cert-manager/releases/download/v1.14.2/cert-manager.crds.yaml
```

---

## 5. Configuration
<!-- AUTO-GENERATED -->

### 5.1. Global

#### 5.1.1. **global.imagePullSecrets** ~ `array`
> Default value:
> ```yaml
> []
> ```

Reference to one or more secrets to be used when pulling images  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/pull-image-private-registry/  
  
For example:

```yaml
imagePullSecrets:
  - name: "image-pull-secret"
```
#### 5.1.2. **global.commonLabels** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Labels to apply to all resources  
Please note that this does not add labels to the resources created dynamically by the controllers. For these resources, you have to add the labels in the template in the cert-manager custom resource: eg. podTemplate/ ingressTemplate in ACMEChallengeSolverHTTP01Ingress  
   ref: https://cert-manager.io/docs/reference/api-docs/#acme.cert-manager.io/v1.ACMEChallengeSolverHTTP01Ingress  
eg. secretTemplate in CertificateSpec  
   ref: https://cert-manager.io/docs/reference/api-docs/#cert-manager.io/v1.CertificateSpec
#### 5.1.3. **global.revisionHistoryLimit** ~ `number`

The number of old ReplicaSets to retain to allow rollback (If not set, default Kubernetes value is set to 10)

#### 5.1.4. **global.priorityClassName** ~ `string`
> Default value:
> ```yaml
> ""
> ```

Optional priority class to be used for the cert-manager pods
#### 5.1.5. **global.rbac.create** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Create required ClusterRoles and ClusterRoleBindings for cert-manager
#### 5.1.6. **global.rbac.aggregateClusterRoles** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Aggregate ClusterRoles to Kubernetes default user-facing roles. Ref: https://kubernetes.io/docs/reference/access-authn-authz/rbac/#user-facing-roles
#### 5.1.7. **global.podSecurityPolicy.enabled** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Create PodSecurityPolicy for cert-manager  
  
NOTE: PodSecurityPolicy was deprecated in Kubernetes 1.21 and removed in 1.25
#### 5.1.8. **global.podSecurityPolicy.useAppArmor** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Configure the PodSecurityPolicy to use AppArmor
#### 5.1.9. **global.logLevel** ~ `number`
> Default value:
> ```yaml
> 2
> ```

Set the verbosity of cert-manager. Range of 0 - 6 with 6 being the most verbose.
#### 5.1.10. **global.leaderElection.namespace** ~ `string`
> Default value:
> ```yaml
> kube-system
> ```

Override the namespace used for the leader election lease
#### 5.1.11. **global.leaderElection.leaseDuration** ~ `string`

The duration that non-leader candidates will wait after observing a leadership renewal until attempting to acquire leadership of a led but unrenewed leader slot. This is effectively the maximum duration that a leader can be stopped before it is replaced by another candidate.

#### 5.1.12. **global.leaderElection.renewDeadline** ~ `string`

The interval between attempts by the acting master to renew a leadership slot before it stops leading. This must be less than or equal to the lease duration.

#### 5.1.13. **global.leaderElection.retryPeriod** ~ `string`

The duration the clients should wait between attempting acquisition and renewal of a leadership.

#### 5.1.14. **installCRDs** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Install the cert-manager CRDs, it is recommended to not use Helm to manage the CRDs
### 5.2. Controller

#### 5.2.1. **replicaCount** ~ `number`
> Default value:
> ```yaml
> 1
> ```

Number of replicas of the cert-manager controller to run.  
  
The default is 1, but in production you should set this to 2 or 3 to provide high availability.  
  
If `replicas > 1` you should also consider setting `podDisruptionBudget.enabled=true`.  
  
Note: cert-manager uses leader election to ensure that there can only be a single instance active at a time.
#### 5.2.2. **strategy** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Deployment update strategy for the cert-manager controller deployment. See https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy  
  
For example:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 0
    maxUnavailable: 1
```
#### 5.2.3. **podDisruptionBudget.enabled** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Enable or disable the PodDisruptionBudget resource  
  
This prevents downtime during voluntary disruptions such as during a Node upgrade. For example, the PodDisruptionBudget will block `kubectl drain` if it is used on the Node where the only remaining cert-manager  
Pod is currently running.
#### 5.2.4. **podDisruptionBudget.minAvailable** ~ `number`

Configures the minimum available pods for disruptions. Can either be set to an integer (e.g. 1) or a percentage value (e.g. 25%).  
Cannot be used if `maxUnavailable` is set.

#### 5.2.5. **podDisruptionBudget.maxUnavailable** ~ `number`

Configures the maximum unavailable pods for disruptions. Can either be set to an integer (e.g. 1) or a percentage value (e.g. 25%).  
Cannot be used if `minAvailable` is set.

#### 5.2.6. **featureGates** ~ `string`
> Default value:
> ```yaml
> ""
> ```

Comma separated list of feature gates that should be enabled on the controller pod.
#### 5.2.7. **maxConcurrentChallenges** ~ `number`
> Default value:
> ```yaml
> 60
> ```

The maximum number of challenges that can be scheduled as 'processing' at once
#### 5.2.8. **image.registry** ~ `string`

The container registry to pull the manager image from

#### 5.2.9. **image.repository** ~ `string`
> Default value:
> ```yaml
> quay.io/jetstack/cert-manager-controller
> ```

The container image for the cert-manager controller

#### 5.2.10. **image.tag** ~ `string`

Override the image tag to deploy by setting this variable. If no value is set, the chart's appVersion will be used.

#### 5.2.11. **image.digest** ~ `string`

Setting a digest will override any tag

#### 5.2.12. **image.pullPolicy** ~ `string`
> Default value:
> ```yaml
> IfNotPresent
> ```

Kubernetes imagePullPolicy on Deployment.
#### 5.2.13. **clusterResourceNamespace** ~ `string`
> Default value:
> ```yaml
> ""
> ```

Override the namespace used to store DNS provider credentials etc. for ClusterIssuer resources. By default, the same namespace as cert-manager is deployed within is used. This namespace will not be automatically created by the Helm chart.
#### 5.2.14. **namespace** ~ `string`
> Default value:
> ```yaml
> ""
> ```

This namespace allows you to define where the services will be installed into if not set then they will use the namespace of the release. This is helpful when installing cert manager as a chart dependency (sub chart)
#### 5.2.15. **serviceAccount.create** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Specifies whether a service account should be created
#### 5.2.16. **serviceAccount.name** ~ `string`

The name of the service account to use.  
If not set and create is true, a name is generated using the fullname template

#### 5.2.17. **serviceAccount.annotations** ~ `object`

Optional additional annotations to add to the controller's ServiceAccount

#### 5.2.18. **serviceAccount.labels** ~ `object`

Optional additional labels to add to the controller's ServiceAccount

#### 5.2.19. **serviceAccount.automountServiceAccountToken** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Automount API credentials for a Service Account.
#### 5.2.20. **automountServiceAccountToken** ~ `bool`

Automounting API credentials for a particular pod

#### 5.2.21. **enableCertificateOwnerRef** ~ `bool`
> Default value:
> ```yaml
> false
> ```

When this flag is enabled, secrets will be automatically removed when the certificate resource is deleted
#### 5.2.22. **config** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Used to configure options for the controller pod.  
This allows setting options that'd usually be provided via flags. An APIVersion and Kind must be specified in your values.yaml file.  
Flags will override options that are set here.  
  
For example:

```yaml
config:
  apiVersion: controller.config.cert-manager.io/v1alpha1
  kind: ControllerConfiguration
  logging:
    verbosity: 2
    format: text
  leaderElectionConfig:
    namespace: kube-system
  kubernetesAPIQPS: 9000
  kubernetesAPIBurst: 9000
  numberOfConcurrentWorkers: 200
  featureGates:
    AdditionalCertificateOutputFormats: true
    DisallowInsecureCSRUsageDefinition: true
    ExperimentalCertificateSigningRequestControllers: true
    ExperimentalGatewayAPISupport: true
    LiteralCertificateSubject: true
    SecretsFilteredCaching: true
    ServerSideApply: true
    StableCertificateRequestName: true
    UseCertificateRequestBasicConstraints: true
    ValidateCAA: true
  metricsTLSConfig:
    dynamic:
      secretNamespace: "cert-manager"
      secretName: "cert-manager-metrics-ca"
      dnsNames:
      - cert-manager-metrics
      - cert-manager-metrics.cert-manager
      - cert-manager-metrics.cert-manager.svc
```
#### 5.2.23. **dns01RecursiveNameservers** ~ `string`
> Default value:
> ```yaml
> ""
> ```

Comma separated string with host and port of the recursive nameservers cert-manager should query
#### 5.2.24. **dns01RecursiveNameserversOnly** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Forces cert-manager to only use the recursive nameservers for verification. Enabling this option could cause the DNS01 self check to take longer due to caching performed by the recursive nameservers
#### 5.2.25. **extraArgs** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional command line flags to pass to cert-manager controller binary. To see all available flags run docker run quay.io/jetstack/cert-manager-controller:<version> --help  
  
Use this flag to enable or disable arbitrary controllers, for example, disable the CertificiateRequests approver  
  
For example:

```yaml
extraArgs:
  - --controllers=*,-certificaterequests-approver
```
#### 5.2.26. **extraEnv** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional environment variables to pass to cert-manager controller binary.
#### 5.2.27. **resources** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Resources to provide to the cert-manager controller pod  
  
For example:

```yaml
requests:
  cpu: 10m
  memory: 32Mi
```

ref: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
#### 5.2.28. **securityContext** ~ `object`
> Default value:
> ```yaml
> runAsNonRoot: true
> seccompProfile:
>   type: RuntimeDefault
> ```

Pod Security Context  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

#### 5.2.29. **containerSecurityContext** ~ `object`
> Default value:
> ```yaml
> allowPrivilegeEscalation: false
> capabilities:
>   drop:
>     - ALL
> readOnlyRootFilesystem: true
> ```

Container Security Context to be set on the controller component container  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

#### 5.2.30. **volumes** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional volumes to add to the cert-manager controller pod.
#### 5.2.31. **volumeMounts** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional volume mounts to add to the cert-manager controller container.
#### 5.2.32. **deploymentAnnotations** ~ `object`

Optional additional annotations to add to the controller Deployment

#### 5.2.33. **podAnnotations** ~ `object`

Optional additional annotations to add to the controller Pods

#### 5.2.34. **podLabels** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Optional additional labels to add to the controller Pods
#### 5.2.35. **serviceAnnotations** ~ `object`

Optional annotations to add to the controller Service

#### 5.2.36. **serviceLabels** ~ `object`

Optional additional labels to add to the controller Service

#### 5.2.37. **podDnsPolicy** ~ `string`

Pod DNS policy  
ref: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#pod-s-dns-policy

#### 5.2.38. **podDnsConfig** ~ `object`

Pod DNS config, podDnsConfig field is optional and it can work with any podDnsPolicy settings. However, when a Pod's dnsPolicy is set to "None", the dnsConfig field has to be specified.  
ref: https://kubernetes.io/docs/concepts/services-networking/dns-pod-service/#pod-dns-config

#### 5.2.39. **nodeSelector** ~ `object`
> Default value:
> ```yaml
> kubernetes.io/os: linux
> ```

The nodeSelector on Pods tells Kubernetes to schedule Pods on the nodes with matching labels. See https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/  
  
This default ensures that Pods are only scheduled to Linux nodes. It prevents Pods being scheduled to Windows nodes in a mixed OS cluster.

#### 5.2.40. **ingressShim.defaultIssuerName** ~ `string`

Optional default issuer to use for ingress resources

#### 5.2.41. **ingressShim.defaultIssuerKind** ~ `string`

Optional default issuer kind to use for ingress resources

#### 5.2.42. **ingressShim.defaultIssuerGroup** ~ `string`

Optional default issuer group to use for ingress resources

#### 5.2.43. **http_proxy** ~ `string`

Configures the HTTP_PROXY environment variable for where a HTTP proxy is required

#### 5.2.44. **https_proxy** ~ `string`

Configures the HTTPS_PROXY environment variable for where a HTTP proxy is required

#### 5.2.45. **no_proxy** ~ `string`

Configures the NO_PROXY environment variable for where a HTTP proxy is required, but certain domains should be excluded

#### 5.2.46. **affinity** ~ `object`
> Default value:
> ```yaml
> {}
> ```

A Kubernetes Affinity, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#affinity-v1-core  
  
For example:

```yaml
affinity:
  nodeAffinity:
   requiredDuringSchedulingIgnoredDuringExecution:
     nodeSelectorTerms:
     - matchExpressions:
       - key: foo.bar.com/role
         operator: In
         values:
         - master
```
#### 5.2.47. **tolerations** ~ `array`
> Default value:
> ```yaml
> []
> ```

A list of Kubernetes Tolerations, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#toleration-v1-core  
  
For example:

```yaml
tolerations:
- key: foo.bar.com/role
  operator: Equal
  value: master
  effect: NoSchedule
```
#### 5.2.48. **topologySpreadConstraints** ~ `array`
> Default value:
> ```yaml
> []
> ```

A list of Kubernetes TopologySpreadConstraints, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#topologyspreadconstraint-v1-core  
  
For example:

```yaml
topologySpreadConstraints:
- maxSkew: 2
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: ScheduleAnyway
  labelSelector:
    matchLabels:
      app.kubernetes.io/instance: cert-manager
      app.kubernetes.io/component: controller
```
#### 5.2.49. **livenessProbe** ~ `object`
> Default value:
> ```yaml
> enabled: true
> failureThreshold: 8
> initialDelaySeconds: 10
> periodSeconds: 10
> successThreshold: 1
> timeoutSeconds: 15
> ```

LivenessProbe settings for the controller container of the controller Pod.  
  
Enabled by default, because we want to enable the clock-skew liveness probe that restarts the controller in case of a skew between the system clock and the monotonic clock. LivenessProbe durations and thresholds are based on those used for the Kubernetes controller-manager. See: https://github.com/kubernetes/kubernetes/blob/806b30170c61a38fedd54cc9ede4cd6275a1ad3b/cmd/kubeadm/app/util/staticpod/utils.go#L241-L245

#### 5.2.50. **enableServiceLinks** ~ `bool`
> Default value:
> ```yaml
> false
> ```

enableServiceLinks indicates whether information about services should be injected into pod's environment variables, matching the syntax of Docker links.
### 5.3. Prometheus

#### 5.3.1. **prometheus.enabled** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Enable Prometheus monitoring for the cert-manager controller to use with the. Prometheus Operator. If this option is enabled without enabling `prometheus.servicemonitor.enabled` or  
`prometheus.podmonitor.enabled`, 'prometheus.io' annotations are added to the cert-manager Deployment  
resources. Additionally, a service is created which can be used together with your own ServiceMonitor (managed outside of this Helm chart). Otherwise, a ServiceMonitor/ PodMonitor is created.
#### 5.3.2. **prometheus.servicemonitor.enabled** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Create a ServiceMonitor to add cert-manager to Prometheus
#### 5.3.3. **prometheus.servicemonitor.prometheusInstance** ~ `string`
> Default value:
> ```yaml
> default
> ```

Specifies the `prometheus` label on the created ServiceMonitor, this is used when different Prometheus instances have label selectors matching different ServiceMonitors.
#### 5.3.4. **prometheus.servicemonitor.targetPort** ~ `number`
> Default value:
> ```yaml
> 9402
> ```

The target port to set on the ServiceMonitor, should match the port that cert-manager controller is listening on for metrics
#### 5.3.5. **prometheus.servicemonitor.path** ~ `string`
> Default value:
> ```yaml
> /metrics
> ```

The path to scrape for metrics
#### 5.3.6. **prometheus.servicemonitor.interval** ~ `string`
> Default value:
> ```yaml
> 60s
> ```

The interval to scrape metrics
#### 5.3.7. **prometheus.servicemonitor.scrapeTimeout** ~ `string`
> Default value:
> ```yaml
> 30s
> ```

The timeout before a metrics scrape fails
#### 5.3.8. **prometheus.servicemonitor.labels** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Additional labels to add to the ServiceMonitor
#### 5.3.9. **prometheus.servicemonitor.annotations** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Additional annotations to add to the ServiceMonitor
#### 5.3.10. **prometheus.servicemonitor.honorLabels** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Keep labels from scraped data, overriding server-side labels.
#### 5.3.11. **prometheus.servicemonitor.endpointAdditionalProperties** ~ `object`
> Default value:
> ```yaml
> {}
> ```

EndpointAdditionalProperties allows setting additional properties on the endpoint such as relabelings, metricRelabelings etc.  
  
For example:

```yaml
endpointAdditionalProperties:
 relabelings:
 - action: replace
   sourceLabels:
   - __meta_kubernetes_pod_node_name
   targetLabel: instance
```



#### 5.3.12. **prometheus.podmonitor.enabled** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Create a PodMonitor to add cert-manager to Prometheus
#### 5.3.13. **prometheus.podmonitor.prometheusInstance** ~ `string`
> Default value:
> ```yaml
> default
> ```

Specifies the `prometheus` label on the created PodMonitor, this is used when different Prometheus instances have label selectors matching different PodMonitor.
#### 5.3.14. **prometheus.podmonitor.path** ~ `string`
> Default value:
> ```yaml
> /metrics
> ```

The path to scrape for metrics
#### 5.3.15. **prometheus.podmonitor.interval** ~ `string`
> Default value:
> ```yaml
> 60s
> ```

The interval to scrape metrics
#### 5.3.16. **prometheus.podmonitor.scrapeTimeout** ~ `string`
> Default value:
> ```yaml
> 30s
> ```

The timeout before a metrics scrape fails
#### 5.3.17. **prometheus.podmonitor.labels** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Additional labels to add to the PodMonitor
#### 5.3.18. **prometheus.podmonitor.annotations** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Additional annotations to add to the PodMonitor
#### 5.3.19. **prometheus.podmonitor.honorLabels** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Keep labels from scraped data, overriding server-side labels.
#### 5.3.20. **prometheus.podmonitor.endpointAdditionalProperties** ~ `object`
> Default value:
> ```yaml
> {}
> ```

EndpointAdditionalProperties allows setting additional properties on the endpoint such as relabelings, metricRelabelings etc.  
  
For example:

```yaml
endpointAdditionalProperties:
 relabelings:
 - action: replace
   sourceLabels:
   - __meta_kubernetes_pod_node_name
   targetLabel: instance
```



### 5.4. Webhook

#### 5.4.1. **webhook.replicaCount** ~ `number`
> Default value:
> ```yaml
> 1
> ```

Number of replicas of the cert-manager webhook to run.  
  
The default is 1, but in production you should set this to 2 or 3 to provide high availability.  
  
If `replicas > 1` you should also consider setting `webhook.podDisruptionBudget.enabled=true`.
#### 5.4.2. **webhook.timeoutSeconds** ~ `number`
> Default value:
> ```yaml
> 30
> ```

Seconds the API server should wait for the webhook to respond before treating the call as a failure.  
Value must be between 1 and 30 seconds. See:  
https://kubernetes.io/docs/reference/kubernetes-api/extend-resources/validating-webhook-configuration-v1/  
  
We set the default to the maximum value of 30 seconds. Here's why: Users sometimes report that the connection between the K8S API server and the cert-manager webhook server times out. If *this* timeout is reached, the error message will be "context deadline exceeded", which doesn't help the user diagnose what phase of the HTTPS connection timed out. For example, it could be during DNS resolution, TCP connection, TLS negotiation, HTTP negotiation, or slow HTTP response from the webhook server. So by setting this timeout to its maximum value the underlying timeout error message has more chance of being returned to the end user.
#### 5.4.3. **webhook.config** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Used to configure options for the webhook pod.  
This allows setting options that'd usually be provided via flags. An APIVersion and Kind must be specified in your values.yaml file.  
Flags will override options that are set here.  
  
For example:

```yaml
apiVersion: webhook.config.cert-manager.io/v1alpha1
kind: WebhookConfiguration
# The port that the webhook should listen on for requests.
# In GKE private clusters, by default kubernetes apiservers are allowed to
# talk to the cluster nodes only on 443 and 10250. so configuring
# securePort: 10250, will work out of the box without needing to add firewall
# rules or requiring NET_BIND_SERVICE capabilities to bind port numbers < 1000.
# This should be uncommented and set as a default by the chart once we graduate
# the apiVersion of WebhookConfiguration past v1alpha1.
securePort: 10250
```
#### 5.4.4. **webhook.strategy** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Deployment update strategy for the cert-manager webhook deployment. See https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy  
  
For example:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 0
    maxUnavailable: 1
```
#### 5.4.5. **webhook.securityContext** ~ `object`
> Default value:
> ```yaml
> runAsNonRoot: true
> seccompProfile:
>   type: RuntimeDefault
> ```

Pod Security Context to be set on the webhook component Pod  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

#### 5.4.6. **webhook.containerSecurityContext** ~ `object`
> Default value:
> ```yaml
> allowPrivilegeEscalation: false
> capabilities:
>   drop:
>     - ALL
> readOnlyRootFilesystem: true
> ```

Container Security Context to be set on the webhook component container  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

#### 5.4.7. **webhook.podDisruptionBudget.enabled** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Enable or disable the PodDisruptionBudget resource  
  
This prevents downtime during voluntary disruptions such as during a Node upgrade. For example, the PodDisruptionBudget will block `kubectl drain` if it is used on the Node where the only remaining cert-manager  
Pod is currently running.
#### 5.4.8. **webhook.podDisruptionBudget.minAvailable** ~ `number`

Configures the minimum available pods for disruptions. Can either be set to an integer (e.g. 1) or a percentage value (e.g. 25%).  
Cannot be used if `maxUnavailable` is set.

#### 5.4.9. **webhook.podDisruptionBudget.maxUnavailable** ~ `number`

Configures the maximum unavailable pods for disruptions. Can either be set to an integer (e.g. 1) or a percentage value (e.g. 25%).  
Cannot be used if `minAvailable` is set.

#### 5.4.10. **webhook.deploymentAnnotations** ~ `object`

Optional additional annotations to add to the webhook Deployment

#### 5.4.11. **webhook.podAnnotations** ~ `object`

Optional additional annotations to add to the webhook Pods

#### 5.4.12. **webhook.serviceAnnotations** ~ `object`

Optional additional annotations to add to the webhook Service

#### 5.4.13. **webhook.mutatingWebhookConfigurationAnnotations** ~ `object`

Optional additional annotations to add to the webhook MutatingWebhookConfiguration

#### 5.4.14. **webhook.validatingWebhookConfigurationAnnotations** ~ `object`

Optional additional annotations to add to the webhook ValidatingWebhookConfiguration

#### 5.4.15. **webhook.validatingWebhookConfiguration.namespaceSelector** ~ `object`
> Default value:
> ```yaml
> matchExpressions:
>   - key: cert-manager.io/disable-validation
>     operator: NotIn
>     values:
>       - "true"
> ```

Configure spec.namespaceSelector for validating webhooks.

#### 5.4.16. **webhook.mutatingWebhookConfiguration.namespaceSelector** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Configure spec.namespaceSelector for mutating webhooks.

#### 5.4.17. **webhook.extraArgs** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional command line flags to pass to cert-manager webhook binary. To see all available flags run docker run quay.io/jetstack/cert-manager-webhook:<version> --help
#### 5.4.18. **webhook.featureGates** ~ `string`
> Default value:
> ```yaml
> ""
> ```

Comma separated list of feature gates that should be enabled on the webhook pod.
#### 5.4.19. **webhook.resources** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Resources to provide to the cert-manager webhook pod  
  
For example:

```yaml
requests:
  cpu: 10m
  memory: 32Mi
```

ref: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
#### 5.4.20. **webhook.livenessProbe** ~ `object`
> Default value:
> ```yaml
> failureThreshold: 3
> initialDelaySeconds: 60
> periodSeconds: 10
> successThreshold: 1
> timeoutSeconds: 1
> ```

Liveness probe values  
ref: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes

#### 5.4.21. **webhook.readinessProbe** ~ `object`
> Default value:
> ```yaml
> failureThreshold: 3
> initialDelaySeconds: 5
> periodSeconds: 5
> successThreshold: 1
> timeoutSeconds: 1
> ```

Readiness probe values  
ref: https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#container-probes

#### 5.4.22. **webhook.nodeSelector** ~ `object`
> Default value:
> ```yaml
> kubernetes.io/os: linux
> ```

The nodeSelector on Pods tells Kubernetes to schedule Pods on the nodes with matching labels. See https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/  
  
This default ensures that Pods are only scheduled to Linux nodes. It prevents Pods being scheduled to Windows nodes in a mixed OS cluster.

#### 5.4.23. **webhook.affinity** ~ `object`
> Default value:
> ```yaml
> {}
> ```

A Kubernetes Affinity, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#affinity-v1-core  
  
For example:

```yaml
affinity:
  nodeAffinity:
   requiredDuringSchedulingIgnoredDuringExecution:
     nodeSelectorTerms:
     - matchExpressions:
       - key: foo.bar.com/role
         operator: In
         values:
         - master
```
#### 5.4.24. **webhook.tolerations** ~ `array`
> Default value:
> ```yaml
> []
> ```

A list of Kubernetes Tolerations, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#toleration-v1-core  
  
For example:

```yaml
tolerations:
- key: foo.bar.com/role
  operator: Equal
  value: master
  effect: NoSchedule
```
#### 5.4.25. **webhook.topologySpreadConstraints** ~ `array`
> Default value:
> ```yaml
> []
> ```

A list of Kubernetes TopologySpreadConstraints, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#topologyspreadconstraint-v1-core  
  
For example:

```yaml
topologySpreadConstraints:
- maxSkew: 2
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: ScheduleAnyway
  labelSelector:
    matchLabels:
      app.kubernetes.io/instance: cert-manager
      app.kubernetes.io/component: controller
```
#### 5.4.26. **webhook.podLabels** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Optional additional labels to add to the Webhook Pods
#### 5.4.27. **webhook.serviceLabels** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Optional additional labels to add to the Webhook Service
#### 5.4.28. **webhook.image.registry** ~ `string`

The container registry to pull the webhook image from

#### 5.4.29. **webhook.image.repository** ~ `string`
> Default value:
> ```yaml
> quay.io/jetstack/cert-manager-webhook
> ```

The container image for the cert-manager webhook

#### 5.4.30. **webhook.image.tag** ~ `string`

Override the image tag to deploy by setting this variable. If no value is set, the chart's appVersion will be used.

#### 5.4.31. **webhook.image.digest** ~ `string`

Setting a digest will override any tag

#### 5.4.32. **webhook.image.pullPolicy** ~ `string`
> Default value:
> ```yaml
> IfNotPresent
> ```

Kubernetes imagePullPolicy on Deployment.
#### 5.4.33. **webhook.serviceAccount.create** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Specifies whether a service account should be created
#### 5.4.34. **webhook.serviceAccount.name** ~ `string`

The name of the service account to use.  
If not set and create is true, a name is generated using the fullname template

#### 5.4.35. **webhook.serviceAccount.annotations** ~ `object`

Optional additional annotations to add to the controller's ServiceAccount

#### 5.4.36. **webhook.serviceAccount.labels** ~ `object`

Optional additional labels to add to the webhook's ServiceAccount

#### 5.4.37. **webhook.serviceAccount.automountServiceAccountToken** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Automount API credentials for a Service Account.
#### 5.4.38. **webhook.automountServiceAccountToken** ~ `bool`

Automounting API credentials for a particular pod

#### 5.4.39. **webhook.securePort** ~ `number`
> Default value:
> ```yaml
> 10250
> ```

The port that the webhook should listen on for requests. In GKE private clusters, by default kubernetes apiservers are allowed to talk to the cluster nodes only on 443 and 10250. so configuring securePort: 10250, will work out of the box without needing to add firewall rules or requiring NET_BIND_SERVICE capabilities to bind port numbers <1000
#### 5.4.40. **webhook.hostNetwork** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Specifies if the webhook should be started in hostNetwork mode.  
  
Required for use in some managed kubernetes clusters (such as AWS EKS) with custom. CNI (such as calico), because control-plane managed by AWS cannot communicate with pods' IP CIDR and admission webhooks are not working  
  
Since the default port for the webhook conflicts with kubelet on the host network, `webhook.securePort` should be changed to an available port if running in hostNetwork mode.
#### 5.4.41. **webhook.serviceType** ~ `string`
> Default value:
> ```yaml
> ClusterIP
> ```

Specifies how the service should be handled. Useful if you want to expose the webhook to outside of the cluster. In some cases, the control plane cannot reach internal services.
#### 5.4.42. **webhook.loadBalancerIP** ~ `string`

Specify the load balancer IP for the created service

#### 5.4.43. **webhook.url** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Overrides the mutating webhook and validating webhook so they reach the webhook service using the `url` field instead of a service.
#### 5.4.44. **webhook.networkPolicy.enabled** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Create network policies for the webhooks
#### 5.4.45. **webhook.networkPolicy.ingress** ~ `array`
> Default value:
> ```yaml
> - from:
>     - ipBlock:
>         cidr: 0.0.0.0/0
> ```

Ingress rule for the webhook network policy, by default will allow all inbound traffic

#### 5.4.46. **webhook.networkPolicy.egress** ~ `array`
> Default value:
> ```yaml
> - ports:
>     - port: 80
>       protocol: TCP
>     - port: 443
>       protocol: TCP
>     - port: 53
>       protocol: TCP
>     - port: 53
>       protocol: UDP
>     - port: 6443
>       protocol: TCP
>   to:
>     - ipBlock:
>         cidr: 0.0.0.0/0
> ```

Egress rule for the webhook network policy, by default will allow all outbound traffic traffic to ports 80 and 443, as well as DNS ports

#### 5.4.47. **webhook.volumes** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional volumes to add to the cert-manager controller pod.
#### 5.4.48. **webhook.volumeMounts** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional volume mounts to add to the cert-manager controller container.
#### 5.4.49. **webhook.enableServiceLinks** ~ `bool`
> Default value:
> ```yaml
> false
> ```

enableServiceLinks indicates whether information about services should be injected into pod's environment variables, matching the syntax of Docker links.
### 5.5. CA Injector

#### 5.5.1. **cainjector.enabled** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Create the CA Injector deployment
#### 5.5.2. **cainjector.replicaCount** ~ `number`
> Default value:
> ```yaml
> 1
> ```

Number of replicas of the cert-manager cainjector to run.  
  
The default is 1, but in production you should set this to 2 or 3 to provide high availability.  
  
If `replicas > 1` you should also consider setting `cainjector.podDisruptionBudget.enabled=true`.  
  
Note: cert-manager uses leader election to ensure that there can only be a single instance active at a time.
#### 5.5.3. **cainjector.config** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Used to configure options for the cainjector pod.  
This allows setting options that'd usually be provided via flags. An APIVersion and Kind must be specified in your values.yaml file.  
Flags will override options that are set here.  
  
For example:

```yaml
apiVersion: cainjector.config.cert-manager.io/v1alpha1
kind: CAInjectorConfiguration
logging:
 verbosity: 2
 format: text
leaderElectionConfig:
 namespace: kube-system
```
#### 5.5.4. **cainjector.strategy** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Deployment update strategy for the cert-manager cainjector deployment. See https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy  
  
For example:

```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 0
    maxUnavailable: 1
```
#### 5.5.5. **cainjector.securityContext** ~ `object`
> Default value:
> ```yaml
> runAsNonRoot: true
> seccompProfile:
>   type: RuntimeDefault
> ```

Pod Security Context to be set on the cainjector component Pod  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

#### 5.5.6. **cainjector.containerSecurityContext** ~ `object`
> Default value:
> ```yaml
> allowPrivilegeEscalation: false
> capabilities:
>   drop:
>     - ALL
> readOnlyRootFilesystem: true
> ```

Container Security Context to be set on the cainjector component container  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

#### 5.5.7. **cainjector.podDisruptionBudget.enabled** ~ `bool`
> Default value:
> ```yaml
> false
> ```

Enable or disable the PodDisruptionBudget resource  
  
This prevents downtime during voluntary disruptions such as during a Node upgrade. For example, the PodDisruptionBudget will block `kubectl drain` if it is used on the Node where the only remaining cert-manager  
Pod is currently running.
#### 5.5.8. **cainjector.podDisruptionBudget.minAvailable** ~ `number`

Configures the minimum available pods for disruptions. Can either be set to an integer (e.g. 1) or a percentage value (e.g. 25%).  
Cannot be used if `maxUnavailable` is set.

#### 5.5.9. **cainjector.podDisruptionBudget.maxUnavailable** ~ `number`

Configures the maximum unavailable pods for disruptions. Can either be set to an integer (e.g. 1) or a percentage value (e.g. 25%).  
Cannot be used if `minAvailable` is set.

#### 5.5.10. **cainjector.deploymentAnnotations** ~ `object`

Optional additional annotations to add to the cainjector Deployment

#### 5.5.11. **cainjector.podAnnotations** ~ `object`

Optional additional annotations to add to the cainjector Pods

#### 5.5.12. **cainjector.extraArgs** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional command line flags to pass to cert-manager cainjector binary. To see all available flags run docker run quay.io/jetstack/cert-manager-cainjector:<version> --help
#### 5.5.13. **cainjector.featureGates** ~ `string`
> Default value:
> ```yaml
> ""
> ```

Comma separated list of feature gates that should be enabled on the cainjector pod.
#### 5.5.14. **cainjector.resources** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Resources to provide to the cert-manager cainjector pod  
  
For example:

```yaml
requests:
  cpu: 10m
  memory: 32Mi
```

ref: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
#### 5.5.15. **cainjector.nodeSelector** ~ `object`
> Default value:
> ```yaml
> kubernetes.io/os: linux
> ```

The nodeSelector on Pods tells Kubernetes to schedule Pods on the nodes with matching labels. See https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/  
  
This default ensures that Pods are only scheduled to Linux nodes. It prevents Pods being scheduled to Windows nodes in a mixed OS cluster.

#### 5.5.16. **cainjector.affinity** ~ `object`
> Default value:
> ```yaml
> {}
> ```

A Kubernetes Affinity, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#affinity-v1-core  
  
For example:

```yaml
affinity:
  nodeAffinity:
   requiredDuringSchedulingIgnoredDuringExecution:
     nodeSelectorTerms:
     - matchExpressions:
       - key: foo.bar.com/role
         operator: In
         values:
         - master
```
#### 5.5.17. **cainjector.tolerations** ~ `array`
> Default value:
> ```yaml
> []
> ```

A list of Kubernetes Tolerations, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#toleration-v1-core  
  
For example:

```yaml
tolerations:
- key: foo.bar.com/role
  operator: Equal
  value: master
  effect: NoSchedule
```
#### 5.5.18. **cainjector.topologySpreadConstraints** ~ `array`
> Default value:
> ```yaml
> []
> ```

A list of Kubernetes TopologySpreadConstraints, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#topologyspreadconstraint-v1-core  
  
For example:

```yaml
topologySpreadConstraints:
- maxSkew: 2
  topologyKey: topology.kubernetes.io/zone
  whenUnsatisfiable: ScheduleAnyway
  labelSelector:
    matchLabels:
      app.kubernetes.io/instance: cert-manager
      app.kubernetes.io/component: controller
```
#### 5.5.19. **cainjector.podLabels** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Optional additional labels to add to the CA Injector Pods
#### 5.5.20. **cainjector.image.registry** ~ `string`

The container registry to pull the cainjector image from

#### 5.5.21. **cainjector.image.repository** ~ `string`
> Default value:
> ```yaml
> quay.io/jetstack/cert-manager-cainjector
> ```

The container image for the cert-manager cainjector

#### 5.5.22. **cainjector.image.tag** ~ `string`

Override the image tag to deploy by setting this variable. If no value is set, the chart's appVersion will be used.

#### 5.5.23. **cainjector.image.digest** ~ `string`

Setting a digest will override any tag

#### 5.5.24. **cainjector.image.pullPolicy** ~ `string`
> Default value:
> ```yaml
> IfNotPresent
> ```

Kubernetes imagePullPolicy on Deployment.
#### 5.5.25. **cainjector.serviceAccount.create** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Specifies whether a service account should be created
#### 5.5.26. **cainjector.serviceAccount.name** ~ `string`

The name of the service account to use.  
If not set and create is true, a name is generated using the fullname template

#### 5.5.27. **cainjector.serviceAccount.annotations** ~ `object`

Optional additional annotations to add to the controller's ServiceAccount

#### 5.5.28. **cainjector.serviceAccount.labels** ~ `object`

Optional additional labels to add to the cainjector's ServiceAccount

#### 5.5.29. **cainjector.serviceAccount.automountServiceAccountToken** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Automount API credentials for a Service Account.
#### 5.5.30. **cainjector.automountServiceAccountToken** ~ `bool`

Automounting API credentials for a particular pod

#### 5.5.31. **cainjector.volumes** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional volumes to add to the cert-manager controller pod.
#### 5.5.32. **cainjector.volumeMounts** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional volume mounts to add to the cert-manager controller container.
#### 5.5.33. **cainjector.enableServiceLinks** ~ `bool`
> Default value:
> ```yaml
> false
> ```

enableServiceLinks indicates whether information about services should be injected into pod's environment variables, matching the syntax of Docker links.
### 5.6. ACME Solver

#### 5.6.1. **acmesolver.image.registry** ~ `string`

The container registry to pull the acmesolver image from

#### 5.6.2. **acmesolver.image.repository** ~ `string`
> Default value:
> ```yaml
> quay.io/jetstack/cert-manager-acmesolver
> ```

The container image for the cert-manager acmesolver

#### 5.6.3. **acmesolver.image.tag** ~ `string`

Override the image tag to deploy by setting this variable. If no value is set, the chart's appVersion will be used.

#### 5.6.4. **acmesolver.image.digest** ~ `string`

Setting a digest will override any tag

#### 5.6.5. **acmesolver.image.pullPolicy** ~ `string`
> Default value:
> ```yaml
> IfNotPresent
> ```

Kubernetes imagePullPolicy on Deployment.
### 5.7. Startup API Check


This startupapicheck is a Helm post-install hook that waits for the webhook endpoints to become available. The check is implemented using a Kubernetes Job - if you are injecting mesh sidecar proxies into cert-manager pods, you probably want to ensure that they are not injected into this Job's pod. Otherwise the installation may time out due to the Job never being completed because the sidecar proxy does not exit. See https://github.com/cert-manager/cert-manager/pull/4414 for context.
#### 5.7.1. **startupapicheck.enabled** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Enables the startup api check
#### 5.7.2. **startupapicheck.securityContext** ~ `object`
> Default value:
> ```yaml
> runAsNonRoot: true
> seccompProfile:
>   type: RuntimeDefault
> ```

Pod Security Context to be set on the startupapicheck component Pod  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

#### 5.7.3. **startupapicheck.containerSecurityContext** ~ `object`
> Default value:
> ```yaml
> allowPrivilegeEscalation: false
> capabilities:
>   drop:
>     - ALL
> readOnlyRootFilesystem: true
> ```

Container Security Context to be set on the controller component container  
ref: https://kubernetes.io/docs/tasks/configure-pod-container/security-context/

#### 5.7.4. **startupapicheck.timeout** ~ `string`
> Default value:
> ```yaml
> 1m
> ```

Timeout for 'kubectl check api' command
#### 5.7.5. **startupapicheck.backoffLimit** ~ `number`
> Default value:
> ```yaml
> 4
> ```

Job backoffLimit
#### 5.7.6. **startupapicheck.jobAnnotations** ~ `object`
> Default value:
> ```yaml
> helm.sh/hook: post-install
> helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
> helm.sh/hook-weight: "1"
> ```

Optional additional annotations to add to the startupapicheck Job

#### 5.7.7. **startupapicheck.podAnnotations** ~ `object`

Optional additional annotations to add to the startupapicheck Pods

#### 5.7.8. **startupapicheck.extraArgs** ~ `array`
> Default value:
> ```yaml
> - -v
> ```

Additional command line flags to pass to startupapicheck binary. To see all available flags run docker run quay.io/jetstack/cert-manager-ctl:<version> --help  
  
We enable verbose logging by default so that if startupapicheck fails, users can know what exactly caused the failure. Verbose logs include details of the webhook URL, IP address and TCP connect errors for example.

#### 5.7.9. **startupapicheck.resources** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Resources to provide to the cert-manager controller pod  
  
For example:

```yaml
requests:
  cpu: 10m
  memory: 32Mi
```

ref: https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/
#### 5.7.10. **startupapicheck.nodeSelector** ~ `object`
> Default value:
> ```yaml
> kubernetes.io/os: linux
> ```

The nodeSelector on Pods tells Kubernetes to schedule Pods on the nodes with matching labels. See https://kubernetes.io/docs/concepts/scheduling-eviction/assign-pod-node/  
  
This default ensures that Pods are only scheduled to Linux nodes. It prevents Pods being scheduled to Windows nodes in a mixed OS cluster.

#### 5.7.11. **startupapicheck.affinity** ~ `object`
> Default value:
> ```yaml
> {}
> ```

A Kubernetes Affinity, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#affinity-v1-core  
  
For example:

```yaml
affinity:
  nodeAffinity:
   requiredDuringSchedulingIgnoredDuringExecution:
     nodeSelectorTerms:
     - matchExpressions:
       - key: foo.bar.com/role
         operator: In
         values:
         - master
```
#### 5.7.12. **startupapicheck.tolerations** ~ `array`
> Default value:
> ```yaml
> []
> ```

A list of Kubernetes Tolerations, if required; see https://kubernetes.io/docs/reference/generated/kubernetes-api/v1.27/#toleration-v1-core  
  
For example:

```yaml
tolerations:
- key: foo.bar.com/role
  operator: Equal
  value: master
  effect: NoSchedule
```
#### 5.7.13. **startupapicheck.podLabels** ~ `object`
> Default value:
> ```yaml
> {}
> ```

Optional additional labels to add to the startupapicheck Pods
#### 5.7.14. **startupapicheck.image.registry** ~ `string`

The container registry to pull the startupapicheck image from

#### 5.7.15. **startupapicheck.image.repository** ~ `string`
> Default value:
> ```yaml
> quay.io/jetstack/cert-manager-startupapicheck
> ```

The container image for the cert-manager startupapicheck

#### 5.7.16. **startupapicheck.image.tag** ~ `string`

Override the image tag to deploy by setting this variable. If no value is set, the chart's appVersion will be used.

#### 5.7.17. **startupapicheck.image.digest** ~ `string`

Setting a digest will override any tag

#### 5.7.18. **startupapicheck.image.pullPolicy** ~ `string`
> Default value:
> ```yaml
> IfNotPresent
> ```

Kubernetes imagePullPolicy on Deployment.
#### 5.7.19. **startupapicheck.rbac.annotations** ~ `object`
> Default value:
> ```yaml
> helm.sh/hook: post-install
> helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
> helm.sh/hook-weight: "-5"
> ```

annotations for the startup API Check job RBAC and PSP resources

#### 5.7.20. **startupapicheck.automountServiceAccountToken** ~ `bool`

Automounting API credentials for a particular pod

#### 5.7.21. **startupapicheck.serviceAccount.create** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Specifies whether a service account should be created
#### 5.7.22. **startupapicheck.serviceAccount.name** ~ `string`

The name of the service account to use.  
If not set and create is true, a name is generated using the fullname template

#### 5.7.23. **startupapicheck.serviceAccount.annotations** ~ `object`
> Default value:
> ```yaml
> helm.sh/hook: post-install
> helm.sh/hook-delete-policy: before-hook-creation,hook-succeeded
> helm.sh/hook-weight: "-5"
> ```

Optional additional annotations to add to the Job's ServiceAccount

#### 5.7.24. **startupapicheck.serviceAccount.automountServiceAccountToken** ~ `bool`
> Default value:
> ```yaml
> true
> ```

Automount API credentials for a Service Account.

#### 5.7.25. **startupapicheck.serviceAccount.labels** ~ `object`

Optional additional labels to add to the startupapicheck's ServiceAccount

#### 5.7.26. **startupapicheck.volumes** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional volumes to add to the cert-manager controller pod.
#### 5.7.27. **startupapicheck.volumeMounts** ~ `array`
> Default value:
> ```yaml
> []
> ```

Additional volume mounts to add to the cert-manager controller container.
#### 5.7.28. **startupapicheck.enableServiceLinks** ~ `bool`
> Default value:
> ```yaml
> false
> ```

enableServiceLinks indicates whether information about services should be injected into pod's environment variables, matching the syntax of Docker links.

<!-- /AUTO-GENERATED -->
### 5.8. Default Security Contexts

The default pod-level and container-level security contexts, below, adhere to the [restricted](https://kubernetes.io/docs/concepts/security/pod-security-standards/#restricted) Pod Security Standards policies.

Default pod-level securityContext:
```yaml
runAsNonRoot: true
seccompProfile:
  type: RuntimeDefault
```

Default containerSecurityContext:
```yaml
allowPrivilegeEscalation: false
capabilities:
  drop:
  - ALL
```

### 5.9. Assigning Values

Specify each parameter using the `--set key=value[,key=value]` argument to `helm install`.

Alternatively, a YAML file that specifies the values for the above parameters can be provided while installing the chart. For example,

```console
$ helm install my-release -f values.yaml .
```
> **Tip**: You can use the default [values.yaml](https://github.com/cert-manager/cert-manager/blob/master/deploy/charts/cert-manager/values.yaml)

---

## 6. Contributing

This chart is maintained at [github.com/cert-manager/cert-manager](https://github.com/cert-manager/cert-manager/tree/master/deploy/charts/cert-manager).

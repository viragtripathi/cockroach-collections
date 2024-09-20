# CockroachDB with Istio on Kubernetes and Minikube: Step-by-Step Guide

This guide walks you through setting up a **CockroachDB** cluster with **Istio** service mesh on both **real Kubernetes platforms** and **Minikube** for demo purposes. It covers both **secure** and **non-secure** setups, allowing you to choose the appropriate setup based on your needs.

## Prerequisites

Ensure you have the following tools installed:

- [Minikube](https://minikube.sigs.k8s.io/docs/start/) (for local demos)
- [Colima (optional)](https://github.com/abiosoft/colima) if using Docker Daemon on macOS instead of Docker Desktop
- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Istioctl](https://istio.io/latest/docs/setup/getting-started/)
- [CockroachDB CLI](https://www.cockroachlabs.com/docs/stable/install-cockroachdb-mac.html) (optional)

---

## 1. Set Up Kubernetes Cluster

### For Real Kubernetes Platforms (GKE, EKS, AKS, etc.)

1. **Create a Kubernetes cluster** on your platform of choice (e.g., GKE, EKS, or AKS).
   - Follow your cloud provider's guide for creating a cluster:
      - [GKE](https://cloud.google.com/kubernetes-engine/docs/how-to/creating-a-zonal-cluster)
      - [EKS](https://docs.aws.amazon.com/eks/latest/userguide/create-cluster.html)
      - [AKS](https://docs.microsoft.com/en-us/azure/aks/kubernetes-walkthrough-portal)

2. **Configure `kubectl`** to connect to the cluster:
   ```bash
   kubectl config use-context <your-cluster-context>
   ```

### For Local Minikube (for Testing and Demos)

1. Start Minikube with the Docker driver and ensure Kubernetes is running:
   ```bash
   minikube start --driver=docker
   ```

2. Verify that Minikube is running:
   ```bash
   kubectl get nodes
   ```

### Optional: Start Colima with Kubernetes (macOS)
If using Colima to manage Docker, run:
```bash
colima start --with-kubernetes
```

---

## 2. Install Istio

### 1. Download and Install Istio
```bash
curl -L https://istio.io/downloadIstio | sh -
cd istio-<version>
export PATH=$PWD/bin:$PATH
```

### 2. Install Istio on the Cluster
For **demo** purposes, use the demo profile:
```bash
istioctl install --set profile=demo -y
```

For **real Kubernetes platforms**, you can use the `default` profile:
```bash
istioctl install --set profile=default -y
```

Verify that Istio is installed:
```bash
kubectl get pods -n istio-system
```

---

## 3. Deploy CockroachDB with Istio Integration

CockroachDB can be deployed in both **secure** and **non-secure** modes. Secure mode is recommended for production environments, while non-secure mode is typically used for local development and testing purposes.

### Option 1: Non-Secure CockroachDB Deployment (For Local Demo)

1. Use the **non-secure** manifest:
   ```bash
   curl -O https://raw.githubusercontent.com/cockroachdb/cockroach/master/cloud/kubernetes/cockroachdb-statefulset.yaml
   ```

2. **Modify the StatefulSet for Resource-Constrained Environments**:
   If you're running on Minikube or a low-resource machine, adjust the memory requests and API version:

   - **Change the `apiVersion`** from `v1beta1` to `v1` in the `PodDisruptionBudget` section:
     ```yaml
     apiVersion: policy/v1
     ```

   - **Reduce memory requests** from `8Gi` to `2Gi`:
     ```yaml
     requests:
       memory: "2Gi"
     limits:
       memory: "2Gi"
     ```

3. Apply the **non-secure** StatefulSet:
   ```bash
   kubectl apply -f cockroachdb-statefulset.yaml
   ```

4. Initialize the CockroachDB cluster using the `cluster-init.yaml` file:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/cockroachdb/cockroach/master/cloud/kubernetes/cluster-init.yaml
   ```

---

### Option 2: Secure CockroachDB Deployment (For Real Kubernetes Platforms)

1. Use the **secure** CockroachDB manifest:
   ```bash
   curl -O https://raw.githubusercontent.com/cockroachdb/cockroach/master/cloud/kubernetes/cockroachdb-statefulset-secure.yaml
   ```

2. Apply the **secure** StatefulSet:
   ```bash
   kubectl apply -f cockroachdb-statefulset-secure.yaml
   ```

3. **Initialize the CockroachDB cluster with certificates** by applying the `cluster-init-secure.yaml` file:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/cockroachdb/cockroach/master/cloud/kubernetes/cluster-init-secure.yaml
   ```

This will automatically generate and distribute certificates to the CockroachDB nodes for secure communication.

---

## 4. Disable Istio Sidecar Injection for CockroachDB

### Option 1: Disable Sidecar Injection for the Namespace

1. Disable sidecar injection for the entire namespace where CockroachDB is deployed (e.g., `default`):
   ```bash
   kubectl label namespace default istio-injection=disabled --overwrite
   ```

### Option 2: Disable Sidecar Injection for Specific Pods

Alternatively, you can disable the sidecar injection at the pod level by adding an annotation to the `StatefulSet`.

1. Modify the `cockroachdb-statefulset.yaml` or `cockroachdb-statefulset-secure.yaml` to include the following annotation under the `metadata` section for the `template`:

   ```yaml
   template:
     metadata:
       annotations:
         sidecar.istio.io/inject: "false"
   ```

2. Apply the changes:
   ```bash
   kubectl apply -f cockroachdb-statefulset.yaml  # Non-secure
   kubectl apply -f cockroachdb-statefulset-secure.yaml  # Secure
   ```

---

## 5. Configure Istio Ingress Gateway for CockroachDB

### 1. Create a Gateway and VirtualService for CockroachDB

To expose both TCP (for SQL) and HTTP (for the Admin UI), create a file named `cockroachdb-istio.yaml` with the following content:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: Gateway
metadata:
  name: cockroachdb-gateway
spec:
  selector:
    istio: ingressgateway
  servers:
  - port:
      number: 26257
      name: cockroachdb
      protocol: TCP
    hosts:
    - "*"
  - port:
      number: 80
      name: http
      protocol: HTTP
    hosts:
    - "*"
---
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: cockroachdb
spec:
  hosts:
  - "*"
  gateways:
  - cockroachdb-gateway
  tcp:
  - match:
    - port: 26257
    route:
    - destination:
        host: cockroachdb-public
        port:
          number: 26257
  http:
  - match:
    - port: 80
    route:
    - destination:
        host: cockroachdb-public
        port:
          number: 8080
```

Apply the configuration:
```bash
kubectl apply -f cockroachdb-istio.yaml
```

---

## 6. Access CockroachDB

### For Real Kubernetes Platforms

1. **Obtain External IP** for the Istio Ingress Gateway:
   ```bash
   kubectl get svc istio-ingressgateway -n istio-system
   ```

   Use the `EXTERNAL-IP` from the output to access the CockroachDB Admin UI:
   ```bash
   http://<EXTERNAL-IP>:80
   ```

2. **Connect to CockroachDB SQL**:
   ```bash
   psql -h <EXTERNAL-IP> -p 26257 -U root
   ```

### For Minikube

1. **Use Minikube Tunnel**:
   ```bash
   minikube tunnel
   ```

2. **Access CockroachDB Admin UI** via Minikube IP:
   ```bash
   http://<minikube-ip>:80
   ```

3. **Connect to CockroachDB SQL**:
   ```bash
   psql -h 127.0.0.1 -p 26257 -U root
   ```

---

## Troubleshooting

1. **Istio Sidecar Not Injected**: Ensure sidecar injection is either disabled for CockroachDB or configured correctly.
2. **Cannot Connect to SQL**: Check that port `26257` is correctly routed through Istio Ingress Gateway.
3. **404 NR (No Route)**: Ensure your `VirtualService` is routing HTTP traffic to CockroachDB Admin UI on port `8080`.

---

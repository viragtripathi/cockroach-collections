# CockroachDB with Istio on Kubernetes and Minikube: Step-by-Step Guide

<details><summary><b>What is Istio?</b></summary>

Istio is an open-source service mesh that provides a way to control how microservices communicate within a distributed system. It runs transparently in the background and handles traffic management, security, policy enforcement, and observability for services in Kubernetes clusters, like CockroachDB.

Istio adds a layer of functionality on top of Kubernetes that makes it easier to manage service-to-service communication in a secure, reliable, and observable way. This is especially important in modern microservice architectures, where many services need to communicate with each other across complex, distributed systems.
</details>

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

<details><summary>Installing Docker, Colima, and Minikube on macOS:</summary>

### Step 1: Install Homebrew (if not already installed)

If you haven’t installed Homebrew yet, you can install it by running:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### Step 2: Install Docker

Docker is required to run containers on your local machine.

Install Docker using Homebrew:

   ```bash
   brew install docker
   ```

### Step 3: Install Colima (Docker Alternative)

Colima is a lightweight alternative to Docker Desktop that allows you to run containers and even Kubernetes (similar to Docker Desktop).

1. Install Colima using Homebrew:

   ```bash
   brew install colima
   ```

2. Verify Colima is installed:

   ```bash
   colima --version
   ```

### Step 4: Install Minikube

Minikube allows you to run a local Kubernetes cluster, which is required to deploy CockroachDB and Istio.

1. Install Minikube using Homebrew:

   ```bash
   brew install minikube
   ```

2. Verify Minikube is installed:

   ```bash
   minikube version
   ```

## Starting Colima and Minikube on macOS

Once Docker, Colima, and Minikube are installed, follow these steps to start Colima and Minikube for running Kubernetes:

### Step 1: Start Colima

Start Colima with the desired CPU and memory resources and enable Kubernetes support. This will ensure Colima provides enough resources to run both CockroachDB and Istio.

1. Run the following command to start Colima with 8 CPUs, 20 GB of memory, and Kubernetes support:

   ```bash
   colima start --cpu 8 --memory 20 --with-kubernetes
   ```

   - `--cpu 8`: Allocates 8 CPU cores to Colima.
   - `--memory 20`: Allocates 20 GB of memory to Colima.
   - `--with-kubernetes`: Starts Kubernetes within Colima.

2. After Colima starts, verify that Kubernetes is running inside Colima:

   ```bash
   colima status
   ```

### Step 2: Start Minikube

Once Colima is up and running, start Minikube using Docker as the driver:

```bash
minikube start --driver=docker
```

- This starts Minikube with Docker as the backend, allowing you to run a local Kubernetes cluster.

Verify that Minikube is running by checking the status:

```bash
minikube status
```

</details>

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

     💡
     `apiVersion` change is only required if you run into `error: resource mapping not found for name: "cockroachdb-budget" namespace: "" from "https://raw.githubusercontent.com/cockroachdb/cockroach/master/cloud/kubernetes/cockroachdb-statefulset.yaml": no matches for kind "PodDisruptionBudget" in version "policy/v1beta1"
     ensure CRDs are installed first` Since Kubernetes 1.21, the `PodDisruptionBudget` API has moved to `policy/v1`, and the old v1beta1 version is no longer available.

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

### 2. Set Up cockroachdb-ui.yaml for the CockroachDB Admin UI
   The CockroachDB Admin UI needs its own routing via the Istio Gateway. Create a file named cockroachdb-ui.yaml:

```yaml
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
   name: cockroachdb-ui
spec:
   hosts:
      - "*"
   gateways:
      - cockroachdb-gateway
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
kubectl apply -f cockroachdb-ui.yaml
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

## Troubleshooting & Debugging

1. **Istio Sidecar Not Injected**: Ensure sidecar injection is either disabled for CockroachDB or configured correctly.
2. **Cannot Connect to SQL**: Check that port `26257` is correctly routed through Istio Ingress Gateway.
3. **404 NR (No Route)**: Ensure your `VirtualService` is routing HTTP traffic to CockroachDB Admin UI on port `8080`.
4. **Connect to the SQL shell of the CockroachDB node**:
   ```bash
   kubectl exec -it cockroachdb-0 -- ./cockroach sql --insecure
   ```
5. **Check Istio Logs for Errors**:
   ```bash
   kubectl logs -l app=istio-ingressgateway -n istio-system
   ```
6. **Test Connection Using Port Forwarding with Istio**:
   ```bash
   kubectl port-forward -n istio-system svc/istio-ingressgateway 8080:8080
   ```
7. **Double-Check the UI Service**:
   ```bash
   kubectl get svc cockroachdb-public
   ```
8. **Verify VirtualService Configuration**:
   ```bash
   kubectl get virtualservice cockroachdb-ui -o yaml
   ```
9. **Verify Gateway Configuration**:
   ```bash
   kubectl get gateway cockroachdb-gateway -o yaml
   ```
10. **Check If Routes Are Configured**:
   ```bash
   istioctl proxy-config routes <istio-ingressgateway-pod-name> -n istio-system
   ```
   To get the <istio-ingressgateway-pod-name>, you can list the pods in the istio-system namespace. The name of the istio-ingressgateway pod will be displayed in the output.

Run the following command to get the pod name:
   ```bash
   kubectl get pods -n istio-system
   ```
---

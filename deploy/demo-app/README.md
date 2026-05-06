# Demo App

Minimal Python HTTP service for AIOps experiment testing.

## Endpoints

```text
GET /          basic JSON response
GET /healthz   liveness check
GET /readyz    readiness check
GET /config    selected environment variables
GET /work?ms=100  CPU-bound work for the requested duration
```

## Build

```bash
docker build -t demo-app:dev deploy/demo-app
```

For k3d:

```bash
k3d image import demo-app:dev -c lab
```

## Install With Helm

```bash
helm upgrade --install demo-service deploy/demo-app/chart \
  -n demo --create-namespace \
  --set image.repository=demo-app \
  --set image.tag=dev \
  --set image.pullPolicy=IfNotPresent
```

## Test

```bash
kubectl port-forward -n demo svc/demo-service 8080:80
curl -sS localhost:8080/healthz
curl -sS 'localhost:8080/work?ms=500'
```

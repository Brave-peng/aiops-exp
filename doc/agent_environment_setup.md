# Agent 环境搭建手册

这份文档给后续 Agent 使用，用于在本地复现 AIOps benchmark 的 Kubernetes 实验环境。目标是跑通 `T1_cpu_saturation`：部署 `demo-service`，用 Chaos Mesh 注入 CPU 压力，再运行建议 Agent 和评估 Agent。

## 前置条件

- Linux 本机环境。
- Docker 可用。
- `kubectl` 可用。
- `uv` 可用。
- 可访问 DeepSeek API，并配置以下任一环境变量：

```bash
export DEEPSEEK_API_KEY=...
```

可选模型覆盖：

```bash
export AIOPS_DEEPSEEK_PROPOSER_MODEL=deepseek-v4-pro
export AIOPS_DEEPSEEK_JUDGE_MODEL=deepseek-v4-pro
```

## 启动 minikube

推荐使用 Docker driver、containerd runtime 和 bridge CNI。这里不配置镜像代理。

```bash
minikube start \
  --driver=docker \
  --container-runtime=containerd \
  --cni=bridge \
  --cpus=4 \
  --memory=6144
```

确认集群可用：

```bash
kubectl get nodes
kubectl get pods -A
```

## 安装 Chaos Mesh

添加官方 Helm 仓库：

```bash
helm repo add chaos-mesh https://charts.chaos-mesh.org
helm repo update
```

安装到 `chaos-mesh` namespace：

```bash
helm upgrade --install chaos-mesh chaos-mesh/chaos-mesh \
  -n chaos-mesh \
  --create-namespace \
  --set chaosDaemon.runtime=containerd \
  --set chaosDaemon.socketPath=/run/containerd/containerd.sock \
  --set controllerManager.replicaCount=1 \
  --set dashboard.create=false \
  --set dnsServer.create=false
```

确认 CRD 和 Pod：

```bash
kubectl get crd stresschaos.chaos-mesh.org
kubectl get pods -n chaos-mesh
```

期望至少看到：

- `chaos-controller-manager` 为 Running。
- `chaos-daemon` 为 Running。
- `stresschaos.chaos-mesh.org` CRD 存在。

## 准备 demo-app 镜像

`deploy/demo-app/k8s.yaml` 使用镜像 `demo-app:dev`，并设置 `imagePullPolicy: IfNotPresent`。因此镜像必须先加载到 minikube。

### 标准路径：Dockerfile 构建

如果 Docker Hub 可用，可以直接构建 Python 版 demo-app：

```bash
docker build -t demo-app:dev deploy/demo-app
minikube image load demo-app:dev
```

### 离线路径：静态 C 版 rootfs

如果 `python:3.12-alpine` 拉取失败，可以使用仓库里的静态 C 版实现，不依赖基础镜像：

```bash
gcc -O2 -static -o /tmp/demo-app-main deploy/demo-app/app/main.c -lm
mkdir -p /tmp/demo-app-rootfs
cp /tmp/demo-app-main /tmp/demo-app-rootfs/app
tar -C /tmp/demo-app-rootfs -cf /tmp/demo-app-rootfs.tar .
docker import \
  --change 'ENTRYPOINT ["/app"]' \
  --change 'EXPOSE 8080' \
  /tmp/demo-app-rootfs.tar \
  demo-app:dev
minikube image load demo-app:dev
```

确认镜像已加载：

```bash
minikube image ls | grep demo-app
```

## 运行 benchmark

默认人工模式：

```bash
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml
```

AI 建议 Agent + AI 评估 Agent：

```bash
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml --ai
```

成功时 CLI 摘要类似：

```text
通过 T1_cpu_saturation
运行目录：results/T1_cpu_saturation/<run_id>

环境：ready
故障：cpu_stress=active
观测：collected
建议：ready
评估：passed
清理：completed

报告：report.md
```

## 结果文件

每次运行写入：

```text
results/T1_cpu_saturation/<run_id>/
  report.md
  run.json
  observations.json
  scenario.yaml
  cleanup.json
```

优先阅读 `report.md`。需要排障时再看 `run.json` 和 `observations.json`。

## 清理检查

运行结束后确认没有残留：

```bash
kubectl get stresschaos -A
kubectl wait --for=delete namespace/aiops-t1 --timeout=120s
```

如果 namespace 仍处于 `Terminating`，等待删除完成后再开始下一次运行。

## 常见问题

### `kubectl top pod` 失败

现象：

```text
error: Metrics API not available
```

这不影响 Chaos Mesh 注入判定。当前 benchmark 通过 StressChaos status、conditions 和 containerRecords 判断故障是否真实注入。如果后续要评估 CPU 使用率曲线，需要安装 metrics-server 或接入 Prometheus。

### Chaos Mesh Pod 拉镜像超时

可以先在宿主机 Docker 拉取，再加载进 minikube：

```bash
docker pull ghcr.io/chaos-mesh/chaos-mesh:v2.8.2
docker pull ghcr.io/chaos-mesh/chaos-daemon:v2.8.2
minikube image load ghcr.io/chaos-mesh/chaos-mesh:v2.8.2
minikube image load ghcr.io/chaos-mesh/chaos-daemon:v2.8.2
kubectl rollout restart deployment/chaos-controller-manager -n chaos-mesh
kubectl delete pod -n chaos-mesh -l app.kubernetes.io/component=chaos-daemon
```

### `python:3.12-alpine` 拉取失败

使用上面的“离线路径：静态 C 版 rootfs”。它只要求本机有 `gcc`，不依赖 Docker Hub 基础镜像。

### 故障状态看起来矛盾

以 `report.md` 里的“判定依据”为准：

- `Chaos Mesh condition AllInjected=True` 表示 Chaos Mesh 明确确认注入。
- `containerRecords show injected_count > 0` 表示至少有容器记录显示曾注入。

原始 conditions 仍保留在报告里，供审计和排障使用。

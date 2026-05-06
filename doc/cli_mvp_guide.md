# Python CLI MVP 开发手册

这份文档只覆盖第一版 CLI 的设计和本地手动验证方式。目标是先跑通最小闭环，后面再逐步接入 Chaos Mesh、更多场景和评分细节。

## 1. 开发目标

MVP 先做一个 Python 命令行工具：

```bash
uv run aiops-bench load --scenario scenarios/T1_cpu_saturation.yaml
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml --agent http://localhost:8081
```

第一阶段先保证：

```text
读取 YAML -> 构造 Agent 输入 -> 调用 Agent -> 校验 action 白名单 -> 输出 result JSON
```

真实故障注入、真实 kubectl 动作和真实评估可以分阶段接入。

## 2. 建议目录

```text
aiops_bench/cli.py             # CLI 入口
aiops_bench/scenario.py        # YAML 加载和基础校验
aiops_bench/agent.py           # mock agent / HTTP Agent 调用
aiops_bench/actions.py         # action 白名单校验和 kubectl 命令渲染
scenarios/*.yaml               # 测试场景
results/                       # 输出结果
```

原则：先用 dict 保持 schema 灵活。等场景格式稳定后，再决定是否引入 dataclass、pydantic 或 Go 重写。

## 3. 开发顺序

### Step 1: `load`

只实现 YAML 解析。

验收：

```bash
uv run aiops-bench load --scenario scenarios/T1_cpu_saturation.yaml
```

能打印解析后的 JSON 即可。

### Step 2: fake `run`

先不碰真实故障注入。内置 mock agent 返回一个 `kubectl_scale` action，CLI 校验白名单并渲染 kubectl 命令。默认 dry-run，不执行。

验收：

```bash
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml
```

能输出 result JSON，里面包含 `actions` 和 `commands`。

### Step 3: 接 Agent Gateway

约定 Agent 暴露：

```text
POST /solve
```

返回：

```json
{
  "analysis": "reason",
  "actions": [
    {
      "type": "kubectl_scale",
      "params": {
        "namespace": "demo",
        "deployment": "demo-service",
        "replicas": 3
      }
    }
  ]
}
```

CLI 需要校验：

- action type 必须在 scenario 的 `allowed_actions` 里
- params 先只做基础字段校验，不做复杂 schema

### Step 4: 接真实 kubectl action

优先实现这三个：

```text
kubectl_scale
kubectl_set_resources
kubectl_set_env
```

执行命令建议通过固定模板生成，不允许 Agent 传任意 shell。

### Step 5: 接真实故障注入

先只支持 T1 的 CPU 场景。用 Chaos Mesh 的 `StressChaos` CRD 创建和删除故障。

验收标准：

- 创建 CRD 后目标 Pod CPU 明显升高
- 删除 CRD 后故障停止
- 无论 run 成功失败，最后都能清理 CRD

## 4. k3d Lab 手动流程

下面流程用于在你现有 k3d lab 里先手动验证完整思路。

### 4.1 确认集群

```bash
kubectl config current-context
kubectl get nodes
kubectl get pods -A
```

如果你有多个 context，先切到 lab：

```bash
kubectl config use-context k3d-<你的集群名>
```

### 4.2 安装或确认 Chaos Mesh

确认是否已经安装：

```bash
kubectl get ns chaos-mesh
kubectl get pods -n chaos-mesh
kubectl get crd | grep chaos-mesh
```

如果没装，先按 Chaos Mesh 官方 Helm 方式装到 lab。安装完至少要看到：

```text
chaos-controller-manager
chaos-daemon
```

### 4.3 部署一个 demo 服务

先建 namespace：

```bash
kubectl create ns demo
```

部署一个简单 HTTP 服务。后面项目里可以把它固化到 `deploy/k8s/demo-app.yaml`。

```bash
kubectl create deployment demo-service \
  -n demo \
  --image=nginx:1.27 \
  --replicas=1

kubectl expose deployment demo-service \
  -n demo \
  --port=80 \
  --target-port=80

kubectl get pod -n demo -l app=demo-service
kubectl get svc -n demo
```

验证服务：

```bash
kubectl run curl -n demo --rm -it --image=curlimages/curl -- \
  curl -sS http://demo-service.demo.svc.cluster.local/
```

### 4.4 手动注入 CPU 故障

先确认 Chaos Mesh CRD 名称：

```bash
kubectl api-resources | grep StressChaos
```

创建一个 `StressChaos`：

```yaml
apiVersion: chaos-mesh.org/v1alpha1
kind: StressChaos
metadata:
  name: demo-cpu-stress
  namespace: chaos-mesh
spec:
  mode: one
  selector:
    namespaces:
      - demo
    labelSelectors:
      app: demo-service
  stressors:
    cpu:
      workers: 2
      load: 100
  duration: 5m
```

保存成临时文件后执行：

```bash
kubectl apply -f stress.yaml
kubectl get stresschaos -n chaos-mesh
kubectl describe stresschaos demo-cpu-stress -n chaos-mesh
```

观察目标 Pod：

```bash
kubectl top pod -n demo
kubectl get pod -n demo -w
```

如果 `kubectl top` 不可用，说明 metrics-server 没装；这不影响先验证 CRD 创建和删除。

### 4.5 手动恢复

```bash
kubectl delete stresschaos demo-cpu-stress -n chaos-mesh
kubectl get stresschaos -n chaos-mesh
```

确认目标服务还活着：

```bash
kubectl get pod -n demo -l app=demo-service
kubectl run curl -n demo --rm -it --image=curlimages/curl -- \
  curl -sS http://demo-service.demo.svc.cluster.local/
```

### 4.6 手动模拟 Agent 动作

先模拟 T4，副本数为 0：

```bash
kubectl scale deployment/demo-service -n demo --replicas=0
kubectl get deploy demo-service -n demo
```

再模拟 Agent 修复动作：

```bash
kubectl scale deployment/demo-service -n demo --replicas=1
kubectl rollout status deployment/demo-service -n demo
```

这一步对应未来 CLI 的 `kubectl_scale` executor。

## 5. 当前建议

先做 `load` 和 fake `run`，不要一开始就接 Chaos Mesh client-go。等 CLI 主流程稳定后，再把手动验证过的 `kubectl apply/delete StressChaos` 改成代码实现。

# Python CLI MVP 开发手册

这份文档只覆盖第一版 CLI 的设计和本地手动验证方式。目标是先跑通最小闭环，后面再逐步接入 Chaos Mesh、更多场景和评分细节。

## 1. 开发目标

MVP 先做一个 Python 命令行工具：

```bash
uv run aiops-bench load --scenario scenarios/T1_cpu_saturation.yaml
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml --proposer mock --judge mock
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml --proposer deepseek --judge deepseek
```

第一阶段先保证：

```text
读取 YAML -> 创建测试环境 -> 注入故障 -> 采集现场快照 -> 调用 proposer -> 调用 judge -> 输出结果文件 -> cleanup
```

真实故障注入、真实 kubectl 动作和真实评估可以分阶段接入。

## 2. 建议目录

```text
aiops_bench/cli.py             # CLI 入口
aiops_bench/scenario.py        # YAML 加载和基础校验
aiops_bench/agents/            # manual/mock/deepseek proposer
aiops_bench/evaluators/        # manual/mock/deepseek judge
aiops_bench/observability.py   # 只读 kubectl 现场快照
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

T1 场景使用 `aiops-t1` namespace 和 `deploy/demo-app/k8s.yaml`。先构建镜像并导入 k3d：

```bash
docker build -t demo-app:dev deploy/demo-app
k3d image import demo-app:dev -c lab
```

手动部署和验证：

```bash
kubectl create ns aiops-t1
kubectl apply -n aiops-t1 -f deploy/demo-app/k8s.yaml
kubectl rollout status deployment/demo-service -n aiops-t1 --timeout=120s
kubectl get pod -n aiops-t1 -l app=demo-service
kubectl get svc -n aiops-t1
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
      - aiops-t1
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
kubectl top pod -n aiops-t1
kubectl get pod -n aiops-t1 -w
```

如果 `kubectl top` 不可用，说明 metrics-server 没装；这不影响先验证 CRD 创建和删除。

### 4.5 手动恢复

```bash
kubectl delete stresschaos demo-cpu-stress -n chaos-mesh
kubectl get stresschaos -n chaos-mesh
```

确认目标服务还活着：

```bash
kubectl get pod -n aiops-t1 -l app=demo-service
kubectl run curl -n aiops-t1 --rm -it --image=curlimages/curl -- \
  curl -sS http://demo-service.aiops-t1.svc.cluster.local/
```

### 4.6 手动模拟 Agent 动作

先模拟 T4，副本数为 0：

```bash
kubectl scale deployment/demo-service -n aiops-t1 --replicas=0
kubectl get deploy demo-service -n aiops-t1
```

再模拟 Agent 修复动作：

```bash
kubectl scale deployment/demo-service -n aiops-t1 --replicas=1
kubectl rollout status deployment/demo-service -n aiops-t1
```

这一步对应未来 CLI 的 `kubectl_scale` executor。

### 4.7 CLI 真实运行

确认镜像和 Chaos Mesh 准备好后，直接运行 T1：

```bash
uv run aiops-bench load --scenario scenarios/T1_cpu_saturation.yaml
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml --proposer mock --judge mock
```

运行结束后会写入 `results/T1_cpu_saturation/<run_id>/`，并清理 `StressChaos` 和 `aiops-t1` namespace。
如果故障没有真实生效，CLI 会把本次运行标记为 `invalid`，并跳过 proposer 和 judge。`StressChaos` 在 k3d-in-Docker 环境里可能遇到 cgroup 路径不匹配，例如 `cgroups: cgroup deleted`。

结果目录包含：

```text
scenario.yaml
agent_prompt.md
observations.json
observations.md
proposal.json
evaluation_prompt.md
evaluation.json
cleanup.json
run.json
```

## 5. 当前建议

当前 CLI 已经把手动验证过的 `kubectl apply/delete StressChaos` 接入 T1 场景，并支持 `manual`、`mock`、`deepseek` 三类 proposer/judge 组合。后续再扩展真实修复执行器和更多场景。

# aiops_bench K8s 实验运行器架构

`aiops_bench` 当前定位是一个场景驱动的 Kubernetes 实验生命周期运行器。它读取一份场景 YAML，准备隔离环境，注入故障，采集现场证据，让 proposer 生成诊断建议，让 judge 评估建议，保存结果，并清理实验资源。

## 主流程

```text
CLI
-> ScenarioContext
-> Environment setup
-> Fault injection
-> Observation collection
-> Proposer
-> Judge
-> Result writing
-> Cleanup
```

`runner.py` 只负责编排生命周期。具体能力由各层模块提供：

```text
aiops_bench/
  cli.py
  runner.py

  scenario/
    loader.py       # YAML 读取、项目根目录定位
    schema.py       # 场景 schema 校验、workload 归一

  environment/
    k8s.py          # namespace、kubectl apply、rollout、cleanup

  faults/
    base.py         # FaultInjector 协议
    manager.py      # 故障注册表和批量注入/清理
    chaos_mesh.py   # StressChaos / NetworkChaos / PodChaos
    kubernetes.py   # 通过 Kubernetes 原生命令注入应用态故障

  observability/
    base.py         # ObservationSource 协议
    manager.py      # 多源观测聚合
    kubernetes.py   # kubectl 只读现场快照和 evidence 归一
    render.py       # Markdown 观测渲染

  agents/
    manual.py
    deepseek.py

  evaluators/
    manual.py
    deepseek.py

  results/
    writer.py       # run.json/report.md/cleanup.json 输出

  llm/
    deepseek.py
```

## 场景契约

场景文件是运行器的唯一实验契约。`workload` 是必填字段，观测命令、报告和 prompt 都从它读取目标资源，不再在代码里硬编码 demo-service。

```yaml
id: T1_cpu_saturation
name: demo-service CPU 饱和

environment:
  type: k8s
  namespace: aiops-t1
  setup:
    - type: kubectl_apply
      path: deploy/demo-app/k8s.yaml
  readiness:
    - type: kubectl_rollout
      resource: deployment/demo-service
      namespace: aiops-t1
      timeout_seconds: 120
  cleanup:
    mode: delete_namespace

workload:
  namespace: aiops-t1
  kind: Deployment
  name: demo-service
  selector:
    app: demo-service
  containers:
    - demo-service

faults:
  - id: cpu_stress
    type: chaos_mesh.stress_cpu
    target:
      namespace: aiops-t1
      selector:
        app: demo-service
    spec:
      workers: 2
      load: 100
      duration: 5m

agent_task:
  instruction: |
    请诊断问题并给出修复建议，不要直接执行修复。

solution_contract:
  allowed_actions:
    - kubectl_scale
    - kubectl_set_resources
    - kubectl_restart

evaluation:
  type: deepseek
```

## 路径解析

`ScenarioContext` 负责定位项目根目录和解析场景中的相对路径。场景里的 `environment.setup[].path` 按项目根目录解析，因此 CLI 从仓库外运行时也不会依赖当前工作目录。

## 故障状态语义

故障注入器返回统一状态：

```text
active    有证据证明故障已生效
selected 目标已被 Chaos Mesh 选中，但未确认注入
created  故障资源存在，但未确认注入
failed   注入失败
unknown  无法读取或判断状态
```

runner 只把所有故障均为 `active` 的实验视为有效运行。只创建 Chaos Mesh CRD 但没有注入证据时，本次运行会标记为 `invalid`，并跳过 proposer/judge。

## 观测层

默认观测源是 Kubernetes：

```text
kubectl get deploy,po,svc -n <environment.namespace> -o wide
kubectl describe <workload.kind>/<workload.name> -n <workload.namespace>
kubectl logs -l <workload.selector> -n <workload.namespace> --all-containers=true --tail=100
kubectl top pod -n <workload.namespace>
kubectl get/describe <fault resource>
```

观测结果同时输出原始命令结果和标准化 evidence，供 proposer、judge 和报告复用。

## Proposer/Judge

当前支持：

- `manual`：生成提示词和 pending 结果，等待人工处理。
- `deepseek`：通过 OpenAI 兼容 Chat Completions 接口生成 JSON。

默认运行 `deepseek` proposer 和 `deepseek` judge；使用 `--manual` 时才切换到人工占位结果。proposer 只生成建议，不执行修复动作。judge 独立读取场景、现场证据和 proposer 输出进行评分。

## 结果文件

每次运行写入：

```text
results/<scenario_id>/<run_id>/
  scenario.yaml
  observations.json
  run.json
  report.md
  cleanup.json
```

`run.json` 是完整结构化结果，包含 summary、proposal、evaluation 和 prompts；`report.md` 是中文优先的人类可读报告。

# aiops_bench K8s 实验运行器架构草案

本文记录当前讨论后的方向：`aiops_bench` 先不做大而全的 AIOps 平台，而是先做一个面向 K8s 场景的自动化实验运行器。

它要解决的问题是：给定一份实验场景文件，程序自动搭环境、注入故障、生成 Agent 作答提示词、让 Agent 在提示词约束下自行查看现场并给出解决建议、保存结果，最后清理环境。

## 1. 一句话定位

`aiops_bench` 是一个 K8s 实验生命周期运行器。

一次实验的主流程：

```text
读取场景文件
-> 创建测试环境
-> 等待服务就绪
-> 注入故障
-> 生成 Agent 作答提示词
-> 获取 Agent 的解决建议
-> 评估结果，当前先人工或 mock
-> 清理测试环境
-> 保存本次实验结果
```

当前阶段做这些：

- 自动创建 K8s 测试环境。
- 通过 Chaos Mesh 注入故障。
- 生成 Agent 作答提示词，在提示词里说明它可以使用哪些只读命令。
- Agent 只给建议，不直接修改集群。
- 评估模块先占位，当前主要靠人工 review。
- 每次实验保存完整结果，方便之后回看和自动评分。

当前阶段先不做这些：

- 通用混沌工程平台。
- 通用 Agent 框架。
- 复杂权限系统。
- 自动执行 Agent 的修复动作。
- 题库难度分级、排行榜、训练路线。

## 2. 总体结构

```text
┌──────────────────────────────────────────────────────────────┐
│                         命令行入口                            │
│                                                              │
│  aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml  │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                         实验运行器                            │
│                                                              │
│  1. 读取场景文件                                              │
│  2. 创建测试环境                                              │
│  3. 等待服务就绪                                              │
│  4. 注入故障                                                  │
│  5. 生成 Agent 作答提示词                                     │
│  6. 获取 Agent 解决建议                                       │
│  7. 评估，当前先人工或 mock                                   │
│  8. 清理测试环境                                              │
│  9. 保存结果                                                  │
└──────────────┬───────────────┬───────────────┬───────────────┘
               │               │               │
               ▼               ▼               ▼
┌────────────────────┐ ┌────────────────────┐ ┌────────────────────┐
│ 场景文件处理        │ │ K8s 环境管理        │ │ 故障注入            │
│                    │ │                    │ │                    │
│ - 读取 YAML         │ │ - 创建 namespace    │ │ - 创建 Chaos Mesh   │
│ - 校验必要字段       │ │ - kubectl apply     │ │   故障资源          │
│ - 补默认值          │ │ - 等待 rollout      │ │ - 先支持 CPU 故障    │
│                    │ │ - 删除 namespace    │ │ - 后续支持网络故障   │
└────────────────────┘ └──────────┬─────────┘ └──────────┬─────────┘
                                  │                      │
                                  ▼                      ▼
                         ┌────────────────────────────────────────┐
                         │                K8s 集群                 │
                         │                                        │
                         │  ┌──────────────────────────────────┐  │
                         │  │ 本次实验的 namespace              │  │
                         │  │                                  │  │
                         │  │ - demo-service                   │  │
                         │  │ - Service                        │  │
                         │  │ - ConfigMap / 其他资源            │  │
                         │  └──────────────────────────────────┘  │
                         │                                        │
                         │  ┌──────────────────────────────────┐  │
                         │  │ chaos-mesh namespace              │  │
                         │  │                                  │  │
                         │  │ - chaos-controller-manager        │  │
                         │  │ - chaos-daemon                    │  │
                         │  │ - StressChaos / NetworkChaos      │  │
                         │  └──────────────────────────────────┘  │
                         └────────────────────────────────────────┘
```

Agent 和评估这边的流程：

```text
┌──────────────────────────────────────────────────────────────┐
│                         生成作答提示词                        │
│                                                              │
│  运行器不预先替 Agent 收集现场信息。                           │
│                                                              │
│  给 Agent 的提示词包含：                                      │
│                                                              │
│  - 场景描述                                                   │
│  - 环境信息                                                   │
│  - 已注入的故障摘要                                           │
│  - 可以使用哪些只读 kubectl 命令                              │
│  - 禁止执行哪些会修改集群的命令                               │
│  - 允许提出哪些修复建议类型                                   │
│  - 要求的输出格式                                             │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                         Agent 接入                            │
│                                                              │
│  第一阶段先简单：                                             │
│                                                              │
│  manual: 只生成 agent_prompt.md，人工贴给 Codex/Claude Code   │
│  mock:   返回固定建议                                         │
│  http:   后续再支持 POST /solve                               │
│  local:  后续再考虑自动拉起 codex / claude code                │
│                                                              │
│  关键约束：当前先靠提示词约束 Agent 只读查看、不要执行修复。    │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                         解决建议                              │
│                                                              │
│  Agent 输出建议，而不是直接执行：                              │
│                                                              │
│  {                                                           │
│    "diagnosis": "...",                                       │
│    "evidence": ["..."],                                      │
│    "proposed_actions": [                                     │
│      {                                                       │
│        "type": "kubectl_scale",                              │
│        "params": { ... },                                    │
│        "reason": "..."                                       │
│      }                                                       │
│    ]                                                         │
│  }                                                           │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                         评估模块                              │
│                                                              │
│  当前：                                                       │
│  - manual：人工 review                                       │
│  - mock：返回固定占位结果                                     │
│                                                              │
│  后续：                                                       │
│  - 单独起一个 judge agent                                    │
│  - 根据场景、Agent 过程记录、Agent 建议打分                   │
│  - 检查诊断是否正确、方案是否可行、操作是否安全                │
└─────────────────────────────┬────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│                         结果保存                              │
│                                                              │
│  results/T1_cpu_saturation/<run_id>/                          │
│                                                              │
│  - scenario.yaml                                              │
│  - agent_prompt.md                                            │
│  - proposal.json                                              │
│  - evaluation.json                                            │
│  - run.json                                                   │
└──────────────────────────────────────────────────────────────┘
```

## 3. 场景文件设计

场景文件是一份自动化实验说明书，不只是 Agent 输入。

建议的最小结构：

```yaml
id: T1_cpu_saturation
name: demo-service CPU 饱和
description: |
  demo-service 出现 CPU 压力，服务延迟升高。
  Agent 需要诊断问题，并给出安全的缓解建议。

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
    你可以使用只读 kubectl 命令查看现场，例如 get、describe、logs、top。
    禁止执行任何会修改集群状态的命令，例如 apply、delete、scale、patch、exec。
    请诊断问题并给出修复建议，不要直接执行修复。

solution_contract:
  allowed_actions:
    - kubectl_scale
    - kubectl_set_resources
    - kubectl_restart

evaluation:
  type: manual
```

字段名继续用英文，原因是 YAML 字段需要稳定、简短、方便程序读取。字段解释和文档尽量用中文。

## 4. 关键字段说明

### 4.1 environment

`environment` 描述如何自动搭建测试环境。

第一版只支持 K8s：

- `type: k8s`
- 每个场景使用一个 namespace 做隔离。
- `setup` 先只支持 `kubectl_apply`。
- `readiness` 先只支持 `kubectl_rollout`。
- `cleanup` 先只支持 `delete_namespace`。

后续再考虑：

- Helm。
- Kustomize。
- 多 namespace。
- 多个场景共享基础环境。

### 4.2 faults

`faults` 用数组，方便以后支持组合故障。

第一版可以先限制：

- 只支持 Chaos Mesh。
- 只实现 `chaos_mesh.stress_cpu`。
- 场景文件里是数组，但运行器可以先只允许一个故障。

后续故障类型可以扩展为：

```text
chaos_mesh.stress_cpu      CPU 压力
chaos_mesh.network_delay   网络延迟
chaos_mesh.pod_kill        Pod 异常退出
k8s.patch_resource         修改 K8s 资源
business.config_change     修改业务配置
workload.traffic           制造流量压力
```

业务故障先不放进第一版实现。等 K8s + Chaos Mesh 主流程跑稳后，再单独设计业务故障的执行和恢复方式。

### 4.3 agent_task

`agent_task` 描述给 Agent 的作答要求。

当前先不设计独立的权限系统，也不让运行器预先替 Agent 收集现场信息。第一版直接把可做和禁止做的事情写进提示词：

```yaml
agent_task:
  instruction: |
    你可以使用只读 kubectl 命令查看现场，例如 get、describe、logs、top。
    禁止执行任何会修改集群状态的命令，例如 apply、delete、scale、patch、exec。
    请诊断问题并给出修复建议，不要直接执行修复。
```

含义：

- Agent 可以自己查看现场。
- Agent 只能使用提示词允许的只读命令。
- 当前先靠提示词和人工监督约束 Agent 行为。
- Agent 只给解决建议。
- 运行器不自动执行 Agent 的修复动作。

后续可能扩展：

```text
propose    只给建议
execute    Agent 给动作，运行器校验后执行
diagnose   只做诊断，不要求修复建议
```

### 4.4 solution_contract

`solution_contract` 描述 Agent 的建议里允许出现哪些动作类型。

它不是权限系统，只是建议格式的约束。

第一版只做基础校验：

- 动作类型是否在 `allowed_actions` 里。
- 参数是否满足基础字段要求。

### 4.5 evaluation

当前评估先保留接口，不做复杂实现。

第一版：

```yaml
evaluation:
  type: manual
```

或：

```yaml
evaluation:
  type: mock
```

后续可以扩展成：

```yaml
evaluation:
  type: llm_judge
  rubric:
    - name: diagnosis_correctness
      weight: 0.4
    - name: remediation_feasibility
      weight: 0.4
    - name: safety
      weight: 0.2
```

评估模块后续单独拆出来，例如 `evaluator.py`。

### 4.6 level 字段

当前不保留 `level` 字段。

原因：

- MVP 不做题库分级。
- 不做排行榜或难度统计。
- 不做训练课程路径。

如果未来需要，可以放进 `metadata`：

```yaml
metadata:
  difficulty: easy
  tags:
    - k8s
    - cpu
    - mitigation
```

## 5. 建议代码模块

后续代码可以演进成：

```text
aiops_bench/
  cli.py                  # 命令行入口，只负责参数和输出
  runner.py               # 实验主流程
  scenario.py             # 场景文件加载、校验、默认值

  environment/
    __init__.py
    k8s.py                # K8s namespace、部署、就绪检查、清理

  faults/
    __init__.py
    chaos_mesh.py         # Chaos Mesh 故障注入和清理

  agents/
    __init__.py
    manual.py             # 生成 agent_prompt.md，人工贴给 Agent
    mock.py               # 返回固定建议，用于跑通流程

  evaluators/
    __init__.py
    manual.py             # 返回 pending，等待人工 review
    mock.py               # 返回固定评估结果，用于跑通流程

  results/
    __init__.py
    writer.py             # 实验结果目录、JSON/Markdown 输出
```

第一阶段真正需要实现：

```text
cli.py
runner.py
scenario.py
environment/k8s.py
faults/chaos_mesh.py
agents/manual.py
agents/mock.py
evaluators/manual.py
evaluators/mock.py
results/writer.py
```

暂时不需要：

```text
actions.py
observations.py
permissions.py
executor.py
reporter.py
orchestrator.py
```

暂缓：

```text
真实执行 Agent 的修复动作
HTTP Agent
自动拉起本地 Codex / Claude Code
复杂权限系统
复杂评分
```

## 6. 运行器主流程

`runner.py` 里的主流程建议保持直观：

```text
run_scenario(path, agent_mode):
  读取场景文件
  创建本次实验结果目录

  try:
    创建 K8s 测试环境
    等待服务就绪

    注入故障
    生成 Agent 作答提示词
    获取 Agent 解决建议

    执行评估
    保存结果
    返回本次运行摘要
  finally:
    清理故障
    清理测试环境
```

注意点：

- 清理必须放在 `finally`。
- 故障清理和 namespace 清理要尽量幂等。
- 如果故障注入失败，也要尽量清理已创建的环境。
- Agent 不直接拿 kubeconfig。

## 7. 当前决策

目前倾向采用：

- 环境由程序自动构造。
- 当前只考虑 K8s 环境。
- 故障先基于 Chaos Mesh。
- `faults` 用数组，结构上支持组合故障，第一版实现可以只支持一个。
- Agent 第一阶段通过提示词说明只读权限和禁止操作，由 Agent 自己查看现场。
- Agent 输出解决建议，不直接执行。
- 评估先 manual/mock，后续单独拆模块。
- 删除 `level`，未来需要时放进 `metadata`。
- `target` 不作为顶层字段，只作为 `faults[].target` 这类局部字段。
- 主流程模块命名为 `runner.py`。
- `environment` 和 `faults` 从第一版开始使用目录拆分。
- 第一阶段不保留 `actions.py`，因为当前不执行 Agent 的修复动作，也不单独做动作模块。

## 8. 待讨论问题

- 实验 namespace 是固定写在场景里，还是每次运行自动追加 run id？
- `setup.path` 只允许单个 YAML 文件，还是也允许目录？
- Chaos Mesh 默认要求预安装，还是运行器负责检测并提示？
- manual 模式是只生成 `agent_prompt.md`，还是也支持读取人工填写的 `solution.json`？
- evaluator 的输入是否固定为：场景文件 + Agent 过程记录 + Agent 建议？

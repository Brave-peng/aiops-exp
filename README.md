# aiops-exp

一个轻量级的 AIOps 实验运行器。

第一版基于 Python 实现，当前约定：

- 使用 Typer 编写命令行。
- 使用 uv 管理依赖和运行命令。

## 快速开始

安装依赖：

```bash
uv sync
```

检查场景文件：

```bash
uv run aiops-bench load --scenario scenarios/T1_cpu_saturation.yaml
```

运行场景。默认使用 `manual` proposer 和场景里声明的 judge，执行环境准备和故障注入，并生成中文 `report.md`：

```bash
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml
```

T1 场景会真实操作当前 `kubectl` context：

- 创建 `aiops-t1` namespace。
- 应用 `deploy/demo-app/k8s.yaml`。
- 等待 `deployment/demo-service` rollout ready。
- 创建 Chaos Mesh `StressChaos` CPU 故障。
- 结束时删除故障和 `aiops-t1` namespace。

运行前需要先准备本地 lab：

```bash
docker build -t demo-app:dev deploy/demo-app
k3d image import demo-app:dev -c lab
kubectl get crd stresschaos.chaos-mesh.org
```

给后续 Agent 复现实验环境的完整步骤见 [Agent 环境搭建手册](doc/agent_environment_setup.md)。

使用 DeepSeek 生成修复建议并评分：

```bash
uv run aiops-bench run \
  --scenario scenarios/T1_cpu_saturation.yaml \
  --ai
```

DeepSeek 使用 OpenAI 兼容接口：

```text
base_url: https://api.deepseek.com
model: deepseek-v4-pro
api key env: DEEPSEEK_API_KEY
```

`--ai` 会顺序运行两个独立 AI Agent：

- 建议 Agent：读取场景和 Kubernetes 现场观测，输出诊断与修复建议。
- 评估 Agent：独立读取场景、现场观测和建议 Agent 输出，按动作约束评分。

可以通过环境变量分别覆盖模型：

```bash
export AIOPS_DEEPSEEK_PROPOSER_MODEL=deepseek-v4-pro
export AIOPS_DEEPSEEK_JUDGE_MODEL=deepseek-v4-pro
```

也可以拆开组合，例如人工生成建议、DeepSeek 评分：

```bash
uv run aiops-bench run \
  --scenario scenarios/T1_cpu_saturation.yaml \
  --proposer manual \
  --judge deepseek
```

指定结果输出目录：

```bash
uv run aiops-bench run \
  --scenario scenarios/T1_cpu_saturation.yaml \
  --results-root results
```

运行后会生成类似下面的结果文件：

```text
results/T1_cpu_saturation/<run_id>/
  scenario.yaml
  observations.json
  report.md
  run.json
  cleanup.json
```

其中 `report.md` 是中文优先的人类可读报告；`run.json` 是完整结构化结果，包含 proposer 建议、judge 评估和提示词；`observations.json` 保留原始 kubectl 输出，便于排障。

如果 `StressChaos` CRD 创建成功但 Chaos Mesh 没有真实注入到目标容器，run 会被标记为 `invalid`，并跳过 proposer/judge。当前本地 k3d-in-Docker 环境可能因为 cgroup 路径不匹配导致 `cgroups: cgroup deleted`，这种情况属于实验环境无效，不应计入 AI 评分。

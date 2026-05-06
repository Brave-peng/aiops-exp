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

运行场景。默认使用 `manual` 模式，只生成 `agent_prompt.md`，方便人工贴给 Codex 或 Claude Code：

```bash
uv run aiops-bench run --scenario scenarios/T1_cpu_saturation.yaml
```

使用内置模拟智能体运行场景：

```bash
uv run aiops-bench run \
  --scenario scenarios/T1_cpu_saturation.yaml \
  --agent mock
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
  agent_prompt.md
  proposal.json
  evaluation.json
  cleanup.json
  run.json
```

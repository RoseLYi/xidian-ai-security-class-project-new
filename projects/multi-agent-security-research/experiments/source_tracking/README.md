# 项目 04：三角色来源追踪实验

学号 / 姓名：26241215025 / 董俊逸。课程主体为 `project-04-Intelligence Gathering`。

本实验读取公开研究资料，依次调用阅读、分析、核验三个角色，比较开启与关闭来源约束时的输出。三个角色使用同一模型、独立请求；程序记录消息父节点和来源编号。原项目的批量摘要接口另接入同一来源校验模块，网页可查看原文引用和校验状态。

已完成的真实运行、负结果和局限见 [REPORT.md](REPORT.md)。这是自建的课程原型，未复现 AgentDojo、CaMeL、Colosseum 或目录内其他论文的实验。

## 环境准备

在课程仓库根目录执行，命令均适用于 PowerShell：

```powershell
cd "projects/project-04-Intelligence Gathering"
uv sync --frozen --python 3.11
uv run configure_api.py
cd "../multi-agent-security-research"
```

使用项目 04 的 `.env` 中 `AI_API_KEY`、`AI_BASE_URL`、`AI_MODEL`。实验也支持终端中的 `OPENAI_API_KEY` 与配套的 `OPENAI_BASE_URL` 作为备用配置；不会把密钥写入结果。`--model` 必须显式指定为当前服务可用的模型。本次使用 `deepseek-flash`；其他服务的可用模型应自行核实。

## 采集可复查的公开材料

```powershell
uv run --frozen --project "../project-04-Intelligence Gathering" python -m experiments.source_tracking.evaluate collect --count 22 --output experiments/source_tracking/local-runs/corpus
```

来源是原多智能体资料库固定提交的 `papers/catalog.json`；程序校验 Git blob 哈希。保存查询主题、固定版本、选择顺序、采集时间和内容 SHA-256。材料是整理过的公开元数据与中文研究说明，不是论文全文。若 GitHub 匿名请求限流，可在终端配置自己的 `GITHUB_TOKEN` 后重试；令牌仅用于这个固定 GitHub API 请求。

## 先试运行，再做正式比较

```powershell
uv run --frozen --project "../project-04-Intelligence Gathering" python -m experiments.source_tracking.evaluate run --corpus experiments/source_tracking/local-runs/corpus/corpus.jsonl --output experiments/source_tracking/local-runs/smoke --model deepseek-flash --cases 2 --repeats 1 --max-calls 24 --concurrency 2

uv run --frozen --project "../project-04-Intelligence Gathering" python -m experiments.source_tracking.evaluate run --corpus experiments/source_tracking/local-runs/corpus/corpus.jsonl --output experiments/source_tracking/local-runs/evaluation --model deepseek-flash --offset 2 --cases 20 --repeats 3 --max-calls 720 --concurrency 4
```

P01–P02 仅用于试运行；正式比较使用 P03–P22，每个条件 60 次。四个条件是正常/含注入资料分别配对关闭/开启校验。每个完整运行最多三次调用，每次输出最多 650 token；不自动重试。`--max-calls` 是请求次数上限，不是货币费用上限。正式运行前核对服务价格和账户预算。

已有输出目录不会被覆盖。中断后可在完全相同的正式命令末尾加 `--resume`，从已保存的完整运行记录恢复；更换配置时使用新目录。异常退出时已发送但未记录的请求无法从结果还原，累计账单以模型服务记录为准。

## 运行项目 04 的完整资料流程

```powershell
uv run --frozen --project "../project-04-Intelligence Gathering" python -m experiments.source_tracking.demo --corpus experiments/source_tracking/local-runs/corpus/corpus.jsonl --output experiments/source_tracking/local-runs/demo-summary.json
```

此命令在项目 04 的 `data/github/jsonl/` 写入本演示的 22 条记录、一个重复记录与一个空对象；调用实际清洗、筛选、模型批量摘录、SQLite 和知识库归档流程。演示的知识库限于项目 04 自身的 `knowledge/academic` 和 `knowledge/social`，不写入外部个人知识库。同名输入若与演示内容不同会拒绝覆盖。

随后运行：

```powershell
cd "../project-04-Intelligence Gathering"
uv run start.py
```

在网页“内容分析”中选择演示文件与分析主题，查看“分批 AI 总结 → 查看原文与来源”；“采集结果”可预览 JSONL，“知识库”可查看实际归档。服务默认地址为 `http://127.0.0.1:8080`。

## 回归检查

在项目 04 目录执行：

```powershell
uv run --frozen python -m pytest tests/test_source_grounding.py tests/test_api_limits.py tests/test_store_factory.py -q
cd webui
npm ci
npm run build
```

## 文件及证据边界

- `agents.py`：有界三角色协作、固定来源与调用记录。
- `collect.py`：固定版本公开材料采集和完整性检查。
- `evaluate.py`：配对实验、判据、错误分列及汇总。
- `demo.py`：实际课程管线的完整演示。
- `results_summary.json`、`demo_summary.json`、`collection_manifest.json`：可公开核对的汇总。
- `local-runs/`：原始采集、模型输出和运行记录，仅保留本地，已忽略。

“来源匹配”表示结论逐字对应某条输入资料，并不证明资料真实。未开启校验的输出是实验对照，不能作为核验后的研究结论使用。正常内容被拒绝、模型错误和攻击成功分别报告，不将任何一项改写成防御成功。

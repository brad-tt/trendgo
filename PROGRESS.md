# TrendGo Progress

更新时间：2026-05-16

## 当前阶段

当前处在 Agent 原生解析重构后的稳定期。

已经确定的新产品主线：

- Agent / Skill 负责自然语言理解和字段整理。
- 后端负责结构化校验、计算、自动建工作台和持久化。
- 前端继续作为工作台、展示和纠错入口。
- SQLite 是交易数据真相来源，Markdown 是归档和兼容副本。

## 已完成

- 新增结构化写入接口：`POST /api/agent/commit`。
- 新增能力探测接口：`GET /api/agent/contract`。
- CLI `scripts/openclaw_client.py` 支持 `--intent` 和 `--payload-json`。
- 默认后端端口改为 `8526`，避开旧项目端口。
- Skill 源文件和本机安装 Skill 都已切到当前仓库路径和结构化提交。
- 开仓、纪律事件、复盘可在目标工作台不存在时自动创建。
- 平仓在只有一笔未平仓交易时可自动选择，多笔时要求补 `tradeId`。
- 后端和前端盈亏公式统一为 `(exitPrice - entryPrice) * positionSize`。
- Rule event commit 已修复为真实持久化并读回校验。
- 文档已清理：删除历史 bug 台账和一次性测试准备文档，保留当前权威说明。

## 最近验证

已通过的核心回归：

```bash
cd app
python3 scripts/replay_agent_commit_sandbox.py
python3 scripts/replay_agent_open_write_sandbox.py
python3 scripts/replay_agent_close_write_sandbox.py
python3 scripts/replay_agent_rule_event_write_sandbox.py
python3 scripts/replay_agent_review_write_sandbox.py
python3 -m py_compile api_server.py local_web.py db_init.py database/dal.py core/*.py scripts/*.py
```

前端构建已通过：

```bash
cd app/frontend
npm run build
```

## 当前风险

- Legacy natural-language intake 仍存在，容易让后续开发误以为后端 NLP 是主路径。
- 前端 Agent 面板还需要继续收敛成“字段确认 + 写入结果”面板。
- 测试脚本和真实数据之间仍要保持清晰边界，避免污染真实交易日。
- 规则和知识资料很多，当前只应通过索引稳定引用，不应一次性产品化。

## 推荐下一步

1. 把前端 Agent 面板改成结构化确认面板，突出意图、字段、缺失项和写入状态。
2. 给真实写入和沙盒回归加更明显的数据保护提示。
3. 继续保留 legacy intake，但在 UI 和 Skill 层默认只走 `/api/agent/commit`。

## 暂缓

- 新增长期画像表。
- 新增能力评分系统。
- 删除前端表单。
- 自动改写规则或知识库。
- 把研究材料全量搬到前端。

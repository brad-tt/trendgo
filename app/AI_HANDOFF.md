# AI Handoff

最后更新：2026-05-16

## 当前结论

TrendGo 已经完成 Agent 原生解析方向的重构。新主路径不是让后端解析自然语言，而是：

```text
Agent / Skill 解析自然语言
  -> 结构化 fields
  -> scripts/openclaw_client.py --intent ... --payload-json ...
  -> POST /api/agent/commit
  -> 后端校验、计算、写入、返回 committed 状态
```

判断是否完成记录只看 `committed=true` 或 CLI 的 `已写入: 是`。

## 当前页面结构

一级页面仍是 6 个：

1. `盘前准备`
2. `参考信息`
3. `盘中执行`
4. `盘后复盘`
5. `归档闭环`
6. `历史复查`

核心路由见 `frontend/src/App.tsx`。

## 当前端口

- 当前后端默认：`127.0.0.1:8526`
- 旧 `local_web.py`：`127.0.0.1:8522`
- Vite 前端代理默认：`http://127.0.0.1:8526`

如需换端口：

```bash
TOPTRADER_PORT=8527 python3 -m uvicorn api_server:app --host 127.0.0.1 --port 8527
VITE_API_PROXY_TARGET=http://127.0.0.1:8527 npm run dev
```

## Agent 主接口

当前主接口：

- `GET /api/agent/contract`
- `POST /api/agent/commit`

`/api/agent/contract` 用来确认当前运行中的服务是否支持结构化 commit。CLI 会优先检查它，避免误打到旧服务。

`/api/agent/commit` 支持四种 intent：

- `open_trade`
- `close_trade`
- `rule_event`
- `review`

后端在这个接口里不调用自然语言解析器，只处理结构化字段。

## Legacy 接口

以下接口仍保留兼容，但不是新 Skill 主路径：

- `/api/agent/intake/*`
- `/api/agent/workflow/intake`
- `/api/agent/session`

如果继续维护这些接口，不要让它们重新成为产品主流程。它们的价值是兼容旧脚本、做安全 fallback 和回归观察。

## 写入规则

- 开仓、纪律事件、复盘：目标日期工作台不存在时自动创建。
- 平仓：不自动创建空工作台；只有一笔未平仓交易时可以自动选择，多笔时必须返回缺 `tradeId`。
- 不传日期时：
  - 开仓默认今天。
  - 平仓默认当前市场最近有未平仓交易的工作台。
  - 复盘和纪律事件默认当前市场最近工作台。
- 盈亏计算统一为 `(exitPrice - entryPrice) * positionSize`。

## 关键文件

- `api_server.py`：FastAPI 路由和 Agent commit API。
- `local_web.py`：旧逻辑、记录文件读写和 PnL 计算。
- `database/dal.py`：SQLite 访问层。
- `core/agent_policy.py`：规则和知识提示逻辑。
- `scripts/openclaw_client.py`：Skill 调用的 CLI。
- `scripts/replay_agent_commit_sandbox.py`：结构化 Agent commit 端到端回归。
- `frontend/src/components/review/tradeForm.ts`：前端盈亏预览公式。

## 前端状态

页面仍保留表单入口，用于纠错和补录。Agent 入口还不应该替代所有前端录入 UI。

最近需要注意的前端结构：

- `frontend/src/views/PremarketView.tsx`
- `frontend/src/views/WorkbenchView.tsx`
- `frontend/src/views/CloseoutView.tsx`
- `frontend/src/components/review/ValidationPanel.tsx`
- `frontend/src/components/Drawer.tsx`

`盘前准备` 已经是紧凑入口 + 抽屉式填写，不要无确认地回到大表单平铺。

## 必跑校验

改 Agent commit、写入、计算或 CLI 后：

```bash
python3 -m py_compile api_server.py local_web.py db_init.py database/dal.py core/*.py scripts/*.py
python3 scripts/replay_agent_commit_sandbox.py
python3 scripts/replay_agent_open_write_sandbox.py
python3 scripts/replay_agent_close_write_sandbox.py
python3 scripts/replay_agent_rule_event_write_sandbox.py
python3 scripts/replay_agent_review_write_sandbox.py
```

改规则索引或知识路由后：

```bash
python3 scripts/validate_agent_indexes.py
```

改前端后：

```bash
cd frontend
npm run build
```

## 当前不要做

- 不要新增另一个 NLP 服务。
- 不要让后端重新承担自然语言猜字段职责。
- 不要删除前端表单入口。
- 不要让 Agent 自动修改规则原文或知识路由。
- 不要把历史 bug 文档当作当前设计约束。

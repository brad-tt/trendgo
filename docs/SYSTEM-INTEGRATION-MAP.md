# TrendGo 系统整合地图

## 定位

本文件描述当前 TrendGo 的系统边界。它是产品结构参考，不是接口契约；接口和运行命令以根目录 `README.md` 和 `app/README.md` 为准。

当前系统由三块组成：

| 模块 | 当前职责 |
|---|---|
| `app/` | 主产品容器：FastAPI、SQLite、React、Agent CLI、回归脚本 |
| `trading-system/` | 交易规则和执行纪律来源 |
| `toptrader-research/` | 训练剧本、能力包、知识路由来源 |

## 当前唯一写入主线

```text
用户自然语言
  -> Agent / Skill 解析字段
  -> POST /api/agent/commit
  -> SQLite: app/database/toptrader.db
  -> Markdown 记录归档
  -> 前端展示、复盘和纠错
```

旧的自然语言 intake 接口保留兼容，但不再是主线。

## 数据流

```text
Agent 结构化提交 / 前端表单
        |
        v
FastAPI 后端校验和写入
        |
        v
SQLite 主数据源
        |
        v
前端页面 / 历史复查 / 复盘展示
```

SQLite 是唯一交易数据真相来源。Markdown 记录文件是归档和兼容副本。

## 规则流

```text
trading-system 原始规则文档
        |
        v
trading-system/00-index/rules-catalog-v1.md
        |
        v
Agent 规则提示 / 前端只读展示 / 复盘引用
```

规则原文仍以 `trading-system` 为准，索引负责稳定编号和触发口径。

## 知识路由流

```text
toptrader-research 剧本与能力包
        |
        v
toptrader-research/00-index/knowledge-router-v1.md
        |
        v
Agent 按情境推送一个最相关动作
```

知识库不平铺到前端。Agent 每次只推送当下最相关的一小段。

## 当前落地文件

- 顶层愿景：`docs/TopTrader-顶层设计-v1.md`（历史文件名）
- 规则索引：`trading-system/00-index/rules-catalog-v1.md`
- 知识路由：`toptrader-research/00-index/knowledge-router-v1.md`
- Skill 使用说明：`TOPTRADER_SKILL_USAGE.md`
- 应用开发说明：`app/README.md`
- 当前边界：`BOUNDARIES.md`
- 当前进度：`PROGRESS.md`

## 禁止事项

- 不再新增平行交易记录系统。
- 不让前端、Markdown 和 SQLite 同时竞争真相来源。
- 不让后端重新承担自然语言猜字段职责。
- 不让 Agent 自动修改已确认规则。
- 不一次性删除前端表单入口。

## 成功标准

- 用户可以用自然语言完成记录。
- Agent 知道缺什么，并且不会编造关键交易事实。
- 后端返回明确的写入状态。
- 前端能展示和纠错。
- 规则和知识引用能追溯到来源文件。

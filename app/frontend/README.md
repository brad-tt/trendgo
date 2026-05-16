# TrendGo Frontend

## 角色

这是 TrendGo 当前在用的生产前端。

- React SPA
- 由 FastAPI 提供静态文件与 API
- 以交易工作流而不是系统结构来组织页面

## 技术栈

- React
- TypeScript
- Vite
- Tailwind CSS
- React Router

## 当前一级页面

- `盘前准备`
- `参考信息`
- `盘中执行`
- `盘后复盘`
- `归档闭环`
- `历史复查`

## 当前前端实现重点

### 盘前准备

- `盘前决策面板` 负责展示关键盘前信息
- `盘前作战台` 负责输入
- 作战台已改成：
  - 3 个步骤入口
  - 抽屉式填写
  - 不再在页面中间平铺大段表单

### 参考信息

- 展示恒指参考
- 展示观察标的
- 预留资讯接入位置

### 归档闭环

- `ValidationPanel` 里才是 `盘前完成 / 盘中记录完成 / 盘后复盘完成` 的真实修改入口
- `盘前准备` 页里的 `流程状态` 是只读映射，不可点击

## 本地开发

安装依赖：

```bash
cd frontend
npm install
```

开发模式：

```bash
cd frontend
npm run dev
```

默认代理：

`http://127.0.0.1:8526`

如果后端端口不是 `8526`：

```bash
VITE_API_PROXY_TARGET=http://127.0.0.1:8527 npm run dev
```

## 构建

```bash
cd frontend
npm run build
```

产物输出到：

`frontend/dist`

## 校验

```bash
cd frontend && npm run lint
cd frontend && npm run build
```

## 当前注意事项

- 默认建议把新版跑在 `127.0.0.1:8526`，端口冲突时同步调整后端端口和 `VITE_API_PROXY_TARGET`
- 旧 `local_web.py` 页面固定跑在 `127.0.0.1:8522`
- 如果出现“前端提交新字段但后端报 extra inputs”这类问题，优先怀疑后端进程没重启
- `WorkbenchView` 是最近改动最密集的区域，后续再改盘前页时要先读清当前抽屉交互

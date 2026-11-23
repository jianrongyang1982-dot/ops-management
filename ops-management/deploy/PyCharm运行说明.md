# PyCharm 运行说明

## 一、打开项目

PyCharm → `File` → `Open` → 选择 `D:\WestlakeGroup\code\BlackFortune\ops-management`（项目根目录）

## 二、配置 Python 解释器

`File` → `Settings` → `Project: ops-management` → `Python Interpreter`
→ 齿轮 → `Add Interpreter` → `Add Local Interpreter`
→ `Existing environment` → 解释器路径选：
```
D:\WestlakeGroup\code\BlackFortune\ops-management\backend\.venv\Scripts\python.exe
```
（已创建好，且继承了全部依赖）

## 三、运行后端

右上角运行配置下拉框，选择 **「启动后端服务」** → 点绿色三角 ▶

看到输出 `Uvicorn running on http://127.0.0.1:8001` 即成功。

浏览器访问：`http://127.0.0.1:8001/`
登录：`yjr` / `123`

> 该配置已设好工作目录（`backend`）和脚本（`server.py`），并开启了 reload（改代码自动重启）。

## 四、前端（两种方式二选一）

**方式 A：直接用后端托管的前端（推荐，最简单）**
不需要单独跑前端。后端 `static/` 里已有构建好的页面，访问 8001 端口即可。
适合：只改后端、或只看效果。

**方式 B：前端热更新（改 Vue 代码时用）**
运行配置选 **「启动前端(热更新)」** → ▶
访问 `http://localhost:5173`（已配置代理，API 自动转发到 8001）
改 `.vue` 文件浏览器会自动刷新。

> 注意：前端改动后如需正式发布，需在 `frontend/` 目录执行 `npm run build`，
> 再把 `frontend/dist/` 内容复制到 `backend/static/`。

## 五、常见问题

- **启动报「找不到 .env / 数据库连不上」**：确认运行配置的工作目录是 `backend`（已配好）。
- **端口冲突**：后端用 8001（已避开本机 C-Lodop 打印服务占用的 8000）。若 8001 也被占用，改 `server.py` 里的 `port=8001`，同时改 `vite.config.js` 里的代理目标。
- **PyCharm 看不到运行配置**：`File` → `Settings` → `Advanced Settings` 确认没有禁用；
  或右键 `backend/server.py` → `Run 'server'`，效果一样。

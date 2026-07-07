# 晨报球搭子

给睡过比赛的中国泛球迷，用 3 分钟讲好昨晚发生了什么。

「晨报球搭子」是一个面向 2026 美加墨世界杯的移动优先 H5 应用。它把凌晨结束的比赛整理成中文叙事卡片、关键事件、技术统计和 AI 追问，让用户早上打开手机就能快速补完昨晚的比赛。

线上访问：

- 首页：http://182.92.114.199
- 冠军预测：http://182.92.114.199/predictions
- 健康检查：http://182.92.114.199/health

## 核心功能

- 今日/昨晚比赛列表：按中国用户的阅读习惯展示已结束比赛、比分和一句话钩子。
- 单场比赛战报：提供关键事件、技术统计、球员表现和 5-8 张叙事卡片。
- 三种叙事风格：支持 `formal` 正经复盘、`funny` 段子手、`tactical` 战术党。
- AI 追问：围绕单场比赛进行 SSE 流式问答，并提供普通 JSON 回退接口。
- 历史比赛：支持继续浏览更早的完赛内容。
- 冠军预测：基于球队能力指标和蒙特卡洛模拟输出 2026 世界杯夺冠概率。
- H5 部署：FastAPI 可同源托管前端 SPA，适合微信、公众号菜单、二维码和移动浏览器访问。

## 技术架构

```text
React + TypeScript + Vite + Tailwind CSS
        |
        | HTTP / SSE
        v
FastAPI + SQLAlchemy + SQLite
        |
        +-- API-Football v3：比赛、事件、技术统计同步
        +-- OpenAI-compatible API：战报生成与比赛追问
        +-- 本地快照/缓存：冠军预测与低成本演示数据
```

主要技术栈：

- 前端：React 19、TypeScript、Vite、Tailwind CSS、Zustand、Recharts、Axios、React Router。
- 后端：FastAPI、Uvicorn、SQLAlchemy、Pydantic Settings、HTTPX。
- 数据：默认 SQLite，后续可迁移到 PostgreSQL；预测和临时数据保存在 `backend/data`。
- AI：OpenAI 兼容接口，支持通过 `OPENAI_BASE_URL` 接入不同模型服务。
- 部署：支持 Docker 单服务部署，也支持主机模式用 systemd 直接运行 FastAPI。

## 项目结构

```text
.
├── backend/
│   ├── app/
│   │   ├── api/              # matches、chat、predictions API
│   │   ├── core/             # 配置与数据库初始化
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   └── services/         # 数据同步、预测、叙事、聊天服务
│   ├── data/                 # SQLite 数据库、预测快照与缓存
│   ├── scripts/              # 数据同步、知识库构建、叙事生成脚本
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/              # 前端 API client 与类型定义
│   │   ├── components/       # 比赛卡片、叙事卡片、聊天面板等
│   │   ├── pages/            # 首页、比赛详情、预测、历史页
│   │   └── store/            # Zustand 状态管理
│   └── package.json
├── deploy/                   # Docker 启动脚本
├── Dockerfile
├── render.yaml               # Render Blueprint
├── DEPLOY_H5.md              # H5 部署指南
└── 部署步骤.md                # 当前服务器部署记录
```

## 本地开发

### 1. 后端

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

创建 `backend/.env`：

```bash
DATABASE_URL=sqlite:///./data/worldcup.db
OPENAI_API_KEY=your_openai_or_compatible_key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
CHAT_MODEL=
API_FOOTBALL_KEY=your_api_football_key
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
APP_TIMEZONE=Asia/Shanghai
SYNC_YESTERDAY_ON_STARTUP=true
SYNC_TODAY_ON_STARTUP=true
SYNC_STARTUP_WITH_DETAILS=false
PREDICTION_SYNC_ON_STARTUP=true
PREDICTION_SYNC_BLOCK_STARTUP=false
CORS_ORIGINS=http://localhost:8000,http://localhost:5173
```

启动后端：

```bash
cd backend
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/predictions/champion
```

### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

开发环境默认前端地址：

```text
http://localhost:5173
```

如需连接非同源后端，可设置：

```bash
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1 npm run dev
```

## 构建与运行

### 前端生产构建

```bash
cd frontend
npm run build
```

构建产物会生成到 `frontend/dist`。当该目录存在时，FastAPI 会自动托管前端静态资源，并把非 API 路由回退到 `index.html`。

### 单服务运行

```bash
cd backend
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

访问：

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/health
http://127.0.0.1:8000/api/v1/matches
http://127.0.0.1:8000/api/v1/predictions/champion
```

### Docker

```bash
docker build -t worldcup-app .
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=sqlite:///./data/worldcup.db \
  -e CORS_ORIGINS=http://localhost:8000 \
  -e API_FOOTBALL_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  worldcup-app
```

## API 概览

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 根路径健康检查 |
| `GET` | `/api/v1/health` | API 健康检查 |
| `GET` | `/api/v1/matches` | 获取某天比赛列表，支持 `date`、`include_unfinished` |
| `GET` | `/api/v1/matches/history` | 获取历史完赛列表 |
| `GET` | `/api/v1/matches/{match_id}` | 获取单场比赛详情 |
| `GET` | `/api/v1/matches/{match_id}/narrative` | 获取叙事卡片，支持 `style=formal/funny/tactical` |
| `POST` | `/api/v1/matches/{match_id}/chat` | SSE 流式比赛追问 |
| `POST` | `/api/v1/matches/{match_id}/chat/plain` | 普通 JSON 比赛追问 |
| `GET` | `/api/v1/predictions/champion` | 获取冠军预测，支持 `iterations`、`seed` |

FastAPI 自动文档在后端启动后可访问：

```text
http://127.0.0.1:8000/docs
```

## 部署

推荐生产形态是单服务部署：先执行前端构建，再由 FastAPI 同源托管前端 SPA 和 `/api/v1` 接口。

当前线上服务采用主机模式部署：

- 代码目录：`/srv/worldcup-app`
- 持久化数据目录：`/srv/world-cup-app-data`
- 服务管理：`systemd` 服务 `worldcup-app`
- 监听地址：`0.0.0.0:80`

常用运维命令：

```bash
systemctl status worldcup-app
journalctl -u worldcup-app -f
systemctl restart worldcup-app
```

更新线上代码：

```bash
cd /srv/worldcup-app
git pull
systemctl restart worldcup-app
```

更完整的 Docker、Render 和 H5 部署说明见 `DEPLOY_H5.md`。

## 数据与环境说明

- 默认数据库为 `backend/data/worldcup.db`，由后端启动时自动初始化。
- `backend/data/prediction_snapshot.json` 和 `backend/data/champion_prediction_cache.json` 用于冠军预测快照和缓存。
- 启动时可通过 `SYNC_YESTERDAY_ON_STARTUP`、`SYNC_TODAY_ON_STARTUP`、`SYNC_STARTUP_WITH_DETAILS` 控制比赛数据同步。
- 外部 API 短暂失败时，比赛列表会优先返回本地已有数据，避免页面完全不可用。
- 若没有配置 `OPENAI_API_KEY`，依赖 LLM 的战报生成和追问能力会受限。
- 若没有配置 `API_FOOTBALL_KEY`，实时比赛同步会受限，但本地快照和已有数据库内容仍可用于演示部分页面。

## 验证

常用检查命令：

```bash
cd frontend && npm run lint && npm run build
cd backend && PYTHONPATH=. .venv/bin/python scripts/test_data_pipeline.py
curl http://127.0.0.1:8000/health
```

仓库中还保留了 `qa-report/`，用于记录移动端、桌面端、页面跳转、聊天和预测页的历史 QA 截图与报告。

# H5 部署指南

本文档记录「晨报球搭子」先以 H5 网站上线，并支持微信、公众号打开与分享的部署步骤。

## 部署目标

推荐生产形态是「单服务部署」：先构建前端静态文件，再由 FastAPI 同时托管前端 SPA 与 `/api/v1` 接口。这样前后端同源，`VITE_API_BASE_URL` 可以使用默认 `/api/v1`，CORS 配置也更简单。

```text
微信聊天 / 朋友圈 / 公众号菜单 / 二维码
        ↓
H5 前端：https://yourdomain.com
        ↓
同源 API：https://yourdomain.com/api/v1
        ↓
临时 SQLite / 镜像内置预测快照 / AI 服务
```

## 生产环境变量

单服务部署时前端无需额外变量，默认请求同源 `/api/v1`。

如果前后端拆成两个域名，再在构建前端时设置：

```bash
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1
```

后端：

```bash
DATABASE_URL=sqlite:///./data/worldcup.db
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
CHAT_MODEL=
API_FOOTBALL_KEY=your_key
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io
APP_TIMEZONE=Asia/Shanghai
SYNC_YESTERDAY_ON_STARTUP=true
SYNC_STARTUP_WITH_DETAILS=true
PREDICTION_SYNC_ON_STARTUP=true
PREDICTION_SYNC_BLOCK_STARTUP=false
PREDICTION_SYNC_MAX_AGE_HOURS=24
PREDICTION_SYNC_DAILY_ENABLED=false
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

## 推荐：Docker 单服务部署

项目根目录已提供：

```text
Dockerfile
.dockerignore
deploy/docker-entrypoint.sh
render.yaml
```

构建镜像：

```bash
docker build -t worldcup-app .
```

本地生产模式验证：

```bash
docker run --rm -p 8000:8000 \
  -e DATABASE_URL=sqlite:///./data/worldcup.db \
  -e CORS_ORIGINS=http://localhost:8000 \
  -e API_FOOTBALL_KEY=your_key \
  -e OPENAI_API_KEY=your_key \
  worldcup-app
```

访问：

```text
http://localhost:8000/
http://localhost:8000/health
http://localhost:8000/api/v1/predictions/champion
```

容器启动时会执行 `deploy/docker-entrypoint.sh`：

1. 确保 `/app/backend/data` 存在。
2. 如果数据目录为空，将镜像内置的 `prediction_snapshot.json`、`champion_prediction_cache.json` 复制为种子数据。
3. 通过 `uvicorn` 启动 FastAPI，并使用云平台注入的 `PORT`。

### 无持久化数据盘方案

Render 免费/无信用卡场景可以不购买持久化数据盘。当前 `render.yaml` 默认采用无盘部署，运行数据写入容器内的 `/app/backend/data` 临时目录。

| 数据 | 无盘表现 |
|------|----------|
| `prediction_snapshot.json` | 镜像内置，容器启动可直接使用 |
| `champion_prediction_cache.json` | 镜像内置，缺失时也可重新计算 |
| `worldcup.db` | 容器启动时由 `init_db()` 创建空库 |
| 昨日比赛 | 启动时通过 API-Football 重新同步 |
| AI 战报/聊天上下文 | 只保存在当前容器生命周期内，重启后丢失 |

无盘方案的适用范围：

- 低成本验证产品和 H5 页面。
- 冠军预测页优先可用。
- 首页/昨日回顾依赖 `API_FOOTBALL_KEY` 启动同步。

无盘方案的限制：

- Render 重启、重新部署、休眠恢复后，SQLite 内写入的比赛明细和战报会重置。
- 如果 API-Football 当次同步失败，首页可能短时没有最新比赛。
- 不适合作为长期生产数据存储。

后续如果需要稳定保存比赛库、战报和聊天记录，再开启 Render Disk 或切换 PostgreSQL。

## Render 部署

仓库根目录的 `render.yaml` 是 Render Blueprint 配置。使用方式：

1. 将代码推送到 GitHub/GitLab。
2. 在 Render 选择 `New` → `Blueprint`。
3. 选择本仓库，Render 会读取 `render.yaml` 创建 Docker Web Service。
4. 在 Render 环境变量中填入：
   - `API_FOOTBALL_KEY`
   - `OPENAI_API_KEY`
   - `OPENAI_BASE_URL`
   - `LLM_MODEL`
   - `CHAT_MODEL`
   - `CORS_ORIGINS`
5. 绑定自定义域名后，把 `CORS_ORIGINS` 改为正式域名，例如：

```text
https://yourdomain.com,https://www.yourdomain.com
```

`render.yaml` 已配置：

| 配置 | 说明 |
|------|------|
| `env: docker` | 使用项目根目录 `Dockerfile` 构建 |
| `plan: free` | 使用免费实例，避免信用卡/付费实例要求 |
| `healthCheckPath: /health` | Render 健康检查 |
| 无 `disk` 配置 | 不购买持久化数据盘，适配无信用卡/免费验证场景 |
| `SYNC_STARTUP_WITH_DETAILS=true` | 启动同步昨日比赛详情 |

如果后续要启用持久化数据盘，可在 `render.yaml` 的服务下恢复：

```yaml
disk:
  name: worldcup-data
  mountPath: /app/backend/data
  sizeGB: 1
```

## 备选：传统前后端分离部署

### 前端构建

```bash
cd frontend
npm install
VITE_API_BASE_URL=https://api.yourdomain.com/api/v1 npm run build
```

构建产物在 `frontend/dist`。

### 后端启动

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

生产环境建议用 `systemd` 托管后端进程。

### Nginx 示例

前端站点：

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com www.yourdomain.com;

    root /srv/worldcup/frontend/dist;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

后端 API：

```nginx
server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 健康检查

上线后检查：

```text
https://yourdomain.com/health
https://yourdomain.com/api/v1/health
https://yourdomain.com/api/v1/predictions/champion
https://yourdomain.com/predictions
```

## 微信分享

当前 H5 已在 `frontend/index.html` 配置基础分享信息：

- 页面标题
- 描述
- `og:title`
- `og:description`
- `og:image`
- `theme-color`

分享封面位于：

```text
frontend/public/share-cover.svg
```

后续如果要在微信内自定义「分享给朋友」和「分享到朋友圈」内容，需要接入微信 JS-SDK：

1. 公众号后台配置 JS 接口安全域名。
2. 后端提供签名接口，生成 `nonceStr`、`timestamp`、`signature`。
3. 前端调用 `wx.config`。
4. 前端调用 `wx.updateAppMessageShareData` 和 `wx.updateTimelineShareData`。

## 预测接口缓存

`GET /api/v1/predictions/champion` 默认请求 `10000` 次模拟，并优先读取：

```text
backend/data/champion_prediction_cache.json
```

如果缓存不存在，或早于 `prediction_snapshot.json`，后端会自动重新计算并写入缓存。

带非默认参数时仍会实时计算：

```text
/api/v1/predictions/champion?iterations=3000&seed=2026
```

## 微信内容合规

预测页已加入免责声明：

```text
预测结果基于公开数据、球队评分与蒙特卡洛模拟，仅用于赛事分析与娱乐参考，不构成投注、竞猜或任何收益承诺。
```

运营文案避免使用：

```text
稳赚
必中
下注建议
预测神器
内部消息
```

## 上线前检查清单

| 检查项 | 要求 |
|--------|------|
| 前端域名 | HTTPS 可访问 |
| API 域名 | HTTPS 可访问 |
| CORS | 只允许正式前端域名 |
| 预测页 | 手机宽度无横向溢出 |
| 聊天 | SSE 失败时可回退普通 JSON 接口 |
| 分享卡片 | 标题、描述、封面已配置 |
| 健康检查 | `/health` 返回 `status=ok` |
| 免责声明 | 预测页可见 |

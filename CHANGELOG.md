# 晨报球搭子 — 变更日志

> 本文档记录项目历次迭代的改动，用于留痕和未来代码构建参考。

---

## v1.3 — 首页卡片精简（2026-05-27）

### 改动摘要

去掉首页比赛卡片底部的「正经复盘」「段子手」「战术党」风格标签提示，压缩卡片间距和内部留白，让一屏能展示更多比赛。

### 修改文件

| 文件 | 改动 |
|------|------|
| `frontend/src/components/MatchCard.tsx` | 删除 `STYLE_LABELS` 常量和底部风格标签 JSX 区块 |
| `frontend/src/index.css` | 删除 `.match-card-styles`、`.style-badge` 相关 CSS；压缩卡片内边距（18→12px）、轮次标签下边距（10→6px）、国旗尺寸（28→24px）、比分类号（26→22px）、钩子区域间距、卡片间距（12→8px）|

### 关键技术决策

风格标签在详情页的风格切换器中已经存在，首页重复展示造成视觉噪音，去掉后卡片更聚焦于核心信息（对阵、比分、钩子）。

---

## v1.2 — 中文本地化 + 聊天再加速（2026-05-27）

### 改动摘要

1. **中文本地化**：球队名、球场名、城市名、赛事轮次全部显示中文
2. **聊天速度再提升**：首字响应从 8-14s 降到 0.4-0.5s（~20 倍），全响应 2-3s
3. **通用追问提示**：将 "梅西表现怎么样？" 改为 "本场最佳球员是谁？"（适用于所有比赛）

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/i18n.py` | **新建**。球队/球场/城市/轮次/状态的中英文映射，提供 `get_team_cn()`、`get_stadium_cn()`、`get_city_cn()`、`get_round_cn()`、`get_status_cn()` 工具函数 |
| `backend/app/api/matches.py` | 所有返回字段通过 i18n 函数转为中文名（`home_team`、`away_team`、`stadium`、`round`、`status`、`team` 等）|
| `backend/app/core/config.py` | 新增 `chat_model: str` 配置字段，为空时回退到 `llm_model` |
| `backend/.env` | 新增 `CHAT_MODEL=qwen-turbo-latest`，聊天用快速模型，叙事用质量模型 |
| `backend/app/services/chat_engine.py` | **重写**。① 持久 OpenAI 客户端；② `@lru_cache` 缓存 context；③ 轻量上下文（仅比分+进球时间线+TOP3球员+3张叙事卡片，~392 token vs 原 2171）；④ 过滤点球大战事件（`minute < 120` 且 `detail != "Missed Penalty"`）；⑤ `max_tokens=100`、`temperature=0.5`；⑥ 历史消息裁剪到 6 条 |
| `backend/app/services/chat_prompt.py` | 精简 System Prompt 到 ~80 字符，去掉重复 context 注入 |
| `frontend/src/components/MatchCard.tsx` | FLAGS 映射 key 从英文改为中文（与后端返回一致）|
| `frontend/src/pages/NarrativePage.tsx` | 适配中文队名显示 |
| `frontend/src/components/ChatPanel.tsx` | 追问提示改为 "本场最佳球员是谁？" |

### 关键技术决策

**聊天模型分离**：叙事生成需要高质量（`qwen3.6-flash-2026-04-16`），聊天追问需要低延迟（`qwen-turbo-latest`，首 token 0.4s）。通过 `chat_model` 配置字段分离，互不影响。

**轻量上下文策略**：

| 项目 | 优化前 | 优化后 |
|------|--------|--------|
| 上下文 token | ~2171 | ~392 |
| 包含内容 | 全部事件+全部统计+全部球员+全部叙事 | 进球时间线+TOP3球员+3张funny卡片 |
| 点球大战 | 混入进球列表 | `minute < 120` 过滤 |

---

## v1.1 — 三项优化：叙事补充 / SSE 流式聊天 / UI 重写（2026-05-27）

### 改动摘要

1. **补充 5 场比赛叙事**：数据库原有 6 场比赛仅 1 场有叙事数据，批量生成后共 108 张叙事卡片（6场 × 3风格 × 6卡片）
2. **聊天 SSE 流式响应**：从同步等待改为 Server-Sent Events 逐 token 推送，用户感知延迟大幅降低
3. **前端 UI 重写**：参照 `finalized.html` 设计风格，全面改为绿茵场+暖色卡片+金色点缀主题

### 修改文件

#### 后端

| 文件 | 改动 |
|------|------|
| `backend/scripts/generate_all_narratives.py` | **新建**。一次性脚本，查询无叙事的比赛并调用 `generate_all_styles()` 批量生成 |
| `backend/app/api/chat.py` | 从同步 `chat()` 改为 `StreamingResponse` + `chat_stream()`，设置 SSE 响应头（`text/event-stream`、`X-Accel-Buffering: no`）|
| `backend/app/services/chat_engine.py` | 新增 `chat_stream()` 函数，使用 `stream=True` 逐 chunk yield SSE 格式数据 |

#### 前端

| 文件 | 改动 |
|------|------|
| `frontend/src/index.css` | **完全重写**。深绿渐变背景 + 草坪纹理 + 浮动星星动画；CSS 变量体系（--green-deep, --gold, --coral 等）；卡片、英雄区、风格切换器、叙事文章、聊天面板、底部导航全套样式 |
| `frontend/src/pages/HomePage.tsx` | **重写**。AppHeader + 比赛列表 + BottomNav 三段式布局 |
| `frontend/src/pages/NarrativePage.tsx` | **重写**。返回按钮 → 毛玻璃比分英雄区 → 三色风格切换器 → 叙事文章卡片 → 聊天面板 → 底部导航 |
| `frontend/src/components/MatchCard.tsx` | **重写**。round 标签 + 国旗/队名/比分布局 + hook + style badges |
| `frontend/src/components/StyleSwitch.tsx` | **重写**。三色渐变激活态（formal 蓝 / funny 橙 / tactical 紫）|
| `frontend/src/components/NarrativeCardView.tsx` | **重写**。article-section 排版：section-badge（按 card_type 着色）+ section-heading + section-body + 分隔线 |
| `frontend/src/components/ChatPanel.tsx` | **重写**。SSE 流式显示 + typing 动画 + 建议问题按钮 |
| `frontend/src/api/client.ts` | 新增 `chatWithAIStream()` 函数，使用 `fetch` + `ReadableStream` 解析 SSE 数据流 |

### 关键技术决策

**SSE vs WebSocket**：选择 SSE 因为只需要服务端→客户端单向推送，实现更简单，不需要额外的连接管理。FastAPI 的 `StreamingResponse` 天然支持。

**前端 SSE 解析**：没有使用 EventSource API（只支持 GET），而是用 `fetch` + `ReadableStream` 手动解析，因为聊天请求是 POST。

**UI 配色方案**：

| 用途 | 颜色 |
|------|------|
| 深绿背景 | `#0d2818` → `#1a4d2e` → `#2d6a3f` |
| 金色点缀 | `#d4a843` / `#f0d68a` |
| 珊瑚红强调 | `#ff6b6b` / `#ff8e7a` |
| 卡片背景 | `rgba(255,255,255,0.92)` |
| 正经复盘 | 蓝色渐变 `#1a56db` → `#2563eb` |
| 段子手 | 橙色渐变 `#e67e22` → `#f39c12` |
| 战术党 | 紫色渐变 `#6b21a8` → `#7c3aed` |

---

## v1.0 — 基础修复：SPA 路由 + 查询性能（2026-05-27）

### 改动摘要

1. **修复前端详情页 404**：React Router 客户端路由在直接访问 `/match/:id` 时返回 404，需要后端 SPA 回退
2. **修复比赛列表查询超时**：`joinedload` 导致 4 表联合查询产生笛卡尔积，单次查询耗时 99 秒

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/main.py` | 新增前端静态文件服务：① `/assets` 挂载 `StaticFiles`；② `/{path:path}` catch-all 路由返回 `index.html`，让 React Router 接管客户端路由 |
| `backend/app/api/matches.py` | 所有 `joinedload` 替换为 `selectinload`，避免多表联合查询的笛卡尔积问题 |

### 关键技术决策

**StaticFiles(html=True) vs catch-all 路由**：`StaticFiles(html=True)` 只对目录路径生效（如 `/`），对 `/match/abc` 这种非目录路径不生效。最终方案是分开处理：`/assets` 用 `StaticFiles`，其他路径用 `@app.get("/{path:path}")` catch-all 返回 `index.html`。

**selectinload vs joinedload**：

| 方式 | 查询耗时 | 原因 |
|------|---------|------|
| joinedload（4表）| ~99s | 笛卡尔积：events × stats × performances × narratives |
| selectinload（4表）| ~0.05s | 每条关联单独 SELECT，用 IN 子句批量加载 |

---

## 项目结构（当前状态）

```
世界杯应用/
├── MVP技术方案与开发计划.md
├── CHANGELOG.md                        ← 本文档
├── backend/
│   ├── .env                            # 环境变量（API keys, DB, 模型配置）
│   ├── app/
│   │   ├── main.py                     # FastAPI 应用入口 + SPA 路由
│   │   ├── i18n.py                     # 中英文映射（球队/球场/城市/轮次）
│   │   ├── api/
│   │   │   ├── matches.py              # 比赛/叙事 API（selectinload + 中文名）
│   │   │   └── chat.py                 # 追问对话 API（SSE 流式）
│   │   ├── core/
│   │   │   ├── config.py               # 配置（含 chat_model 分离）
│   │   │   └── database.py             # SQLAlchemy 数据库连接
│   │   ├── models/
│   │   │   └── match.py                # 数据模型（Match, Event, Stat 等）
│   │   └── services/
│   │       ├── chat_engine.py           # 聊天引擎（轻量上下文 + lru_cache + 流式）
│   │       ├── chat_prompt.py           # 聊天 prompt 模板
│   │       ├── narrative_engine.py      # 叙事生成引擎
│   │       ├── rag_context.py           # RAG 上下文检索
│   │       ├── hooks.py                 # 一句话钩子生成
│   │       ├── football_api.py          # API-Football 数据拉取
│   │       ├── data_ingestion.py        # 数据入库流水线
│   │       ├── preprocessor.py          # 数据预处理
│   │       ├── prompts.py               # 叙事 prompt 模板
│   │       └── quality_check.py         # 叙事质量检查
│   └── scripts/
│       ├── generate_all_narratives.py   # 批量叙事生成脚本
│       ├── build_knowledge_base.py      # ChromaDB 知识库构建
│       ├── test_data_pipeline.py        # 数据流水线测试
│       └── test_narrative.py            # 叙事引擎测试
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   │   └── client.ts               # API 客户端 + SSE 流式解析
│   │   ├── components/
│   │   │   ├── MatchCard.tsx            # 比赛卡片（精简版，无风格标签）
│   │   │   ├── StyleSwitch.tsx          # 三色风格切换器
│   │   │   ├── NarrativeCardView.tsx    # 叙事文章展示
│   │   │   └── ChatPanel.tsx            # 追问对话面板（SSE 流式）
│   │   ├── pages/
│   │   │   ├── HomePage.tsx             # 首页（比赛列表）
│   │   │   └── NarrativePage.tsx        # 详情页（叙事+聊天）
│   │   ├── store/
│   │   │   └── useAppStore.ts           # Zustand 状态管理
│   │   ├── index.css                    # 全局样式（绿茵场主题）
│   │   ├── App.tsx                      # 路由配置
│   │   └── main.tsx                     # 应用入口
│   └── dist/                            # 构建产物（由 FastAPI 提供服务）
└── data/
    └── worldcup.db                      # SQLite 数据库
```

---

## 环境配置参考

```bash
# backend/.env
API_FOOTBALL_KEY=<api-football-key>
API_FOOTBALL_BASE_URL=https://v3.football.api-sports.io

OPENAI_API_KEY=<dashscope-key>
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen3.6-flash-2026-04-16        # 叙事生成（质量优先）
CHAT_MODEL=qwen-turbo-latest               # 追问聊天（速度优先）

DATABASE_URL=sqlite:///./data/worldcup.db
CHROMA_PERSIST_DIR=./data/chromadb
```

---

## 性能指标汇总

| 指标 | v1.0 前 | v1.2 后 | 提升 |
|------|---------|---------|------|
| 比赛列表查询 | ~99s | ~0.05s | 1980x |
| 聊天首字延迟 | 8-14s | 0.4-0.5s | ~20x |
| 聊天完整响应 | 8-14s | 2-3s | ~5x |
| 上下文 token | ~2171 | ~392 | -82% |
| 叙事覆盖率 | 1/6 场 | 6/6 场 | 100% |

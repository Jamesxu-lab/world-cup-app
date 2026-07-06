# 晨报球搭子 — 变更日志

> 本文档记录项目历次迭代的改动，用于留痕和未来代码构建参考。

---

## 2026-07-06 追加更新：Render 无持久化数据盘部署

### 改动摘要

为无信用卡/不购买 Render Disk 的场景，将 Render Blueprint 调整为无持久化数据盘部署。应用仍使用 Docker 单服务运行，预测快照和冠军预测缓存随镜像内置，SQLite 数据库在容器临时目录中启动创建。

### 用户可见影响

| 场景 | 影响 |
|------|------|
| 冠军预测页 | 可继续使用镜像内置 `prediction_snapshot.json` 和缓存 |
| 首页昨日比赛 | 依赖启动时 API-Football 同步；容器重启后会重新同步 |
| 赛后详情战报 | 容器生命周期内可用；重启后未持久化的战报会丢失并重新生成/同步 |
| 运营成本 | 不需要 Render 付费持久化数据盘 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `render.yaml` | 移除 `disk` 配置，改为无盘 Web Service |
| `DEPLOY_H5.md` | 增加无持久化数据盘方案、限制和后续恢复 Disk 的配置片段 |

### 风险与后续

无盘方案适合产品验证，不适合长期保存比赛明细、AI 战报或聊天记录。正式运营建议后续切换到 Render Disk 或 PostgreSQL。

## 2026-07-06 追加更新：生产部署配置与单服务上线准备

### 改动摘要

补齐项目上线所需的容器化部署配置，采用「前端构建 + FastAPI 托管静态文件与 API」的单服务形态。该方案适合 Render、Docker 主机或其他支持容器的云平台，能避免前后端分离时的跨域与多服务运维复杂度。

### 修改文件

| 文件 | 改动 |
|------|------|
| `Dockerfile` | 新增多阶段构建：Node 构建 `frontend/dist`，Python 运行 FastAPI 并托管前端静态文件 |
| `.dockerignore` | 排除本地虚拟环境、node_modules、临时报告和敏感 `.env` 文件 |
| `deploy/docker-entrypoint.sh` | 容器启动时初始化 `/app/backend/data`，缺失时复制镜像内置种子数据，再启动 Uvicorn |
| `render.yaml` | 新增 Render Blueprint：Docker Web Service、健康检查、持久化数据盘和生产环境变量占位 |
| `DEPLOY_H5.md` | 更新为推荐 Docker 单服务部署，补充 Render 部署步骤、生产环境变量和上线检查 |

### 验证结果

| 检查项 | 结果 |
|--------|------|
| `npm run build` | 通过，前端产物可被后端静态托管 |
| 部署配置检查 | 已确认本机暂无 `vercel/netlify/fly/railway/render/docker` CLI，真实云端发布需接入目标平台账号或服务器 |

### 剩余上线条件

| 条件 | 说明 |
|------|------|
| 代码托管 | 需要推送到 GitHub/GitLab 或上传到服务器 |
| 云平台/服务器 | 需要 Render、Docker 主机或其他容器平台访问权限 |
| 生产密钥 | 需要配置 `API_FOOTBALL_KEY`、`OPENAI_API_KEY`、`OPENAI_BASE_URL`、模型名等 |
| 正式域名 | 绑定域名后需更新 `CORS_ORIGINS` |

## v1.4 — 冠军预测模型与实时数据快照（2026-06-18）

### 改动摘要

新增 2026 世界杯冠军预测模块，从「静态种子数据」升级为「联网同步快照 + 球队综合评分 + 真实小组赛模拟 + 淘汰赛蒙特卡洛模拟」。

当前模型版本为 `lightweight-v3-squad-form-availability`，预测页地址为 `/predictions`，后端接口为 `GET /api/v1/predictions/champion`。

### 2026-06-25 追加更新：H5 访问、战报数据修复与昨日回顾

#### 改动摘要

完成 H5 访问/分享基础能力、首页战报数据口径修复、昨日比赛自动补同步，以及前端 lint 清零。首页现在默认只展示当天已完赛比赛；如果昨天有已完赛比赛，会在「今日战报」下方显示「昨日回顾」。后端启动时会自动拉取昨天世界杯场次，降低本地数据库漏更新导致页面空栏目的风险。

#### 用户可见变化

| 场景 | 变化 |
|------|------|
| 首页今日战报 | 不再混入 2026 全年比赛、未开赛比赛或进行中脏数据；默认只显示当天已完赛场次 |
| 首页昨日回顾 | 昨天有已完赛比赛时自动出现「昨日回顾」栏目，复用比赛卡片进入详情 |
| 比分准确性 | 回补 2026-06-18 的旧脏数据，修正乌兹别克斯坦 1-3 哥伦比亚等终场比分 |
| H5 访问分享 | 前端支持生产 API 地址配置、分享元信息和分享封面，便于通过微信/公众号打开 |
| 详情页体验 | 修复底部导航入口；叙事加载状态改为按比赛/风格归属，切换风格时不会被旧请求回写 |

#### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/api/matches.py` | `/api/v1/matches` 默认按当天日期过滤，并只返回 `FT/AET/PEN` 已完赛比赛；新增 `include_unfinished` 参数用于调试或扩展场景 |
| `backend/app/services/startup_match_sync.py` | 新增启动同步服务：按 `Asia/Shanghai` 计算昨天，调用 API-Football 拉取世界杯场次并 upsert 到本地库 |
| `backend/app/core/config.py` | 新增 `APP_TIMEZONE`、`SYNC_YESTERDAY_ON_STARTUP`、`SYNC_STARTUP_WITH_DETAILS` 配置 |
| `backend/.env.example` | 补充启动同步配置示例 |
| `backend/app/main.py` | FastAPI 启动时初始化数据库后执行昨日比赛同步；同时增强静态资源挂载防护 |
| `backend/app/i18n.py` | 补充韩国别名、库拉索、科特迪瓦、海地、苏格兰等队名映射 |
| `backend/data/worldcup.db` | 已回补 2026-06-18 终场比分，并实际同步 2026-06-24 的 5 场比赛 |
| `frontend/src/pages/HomePage.tsx` | 首页拆分「今日战报」与「昨日回顾」，昨日有比赛时自动展示第二栏目 |
| `frontend/src/pages/NarrativePage.tsx` | 修复 `react-hooks/set-state-in-effect`：用比赛/风格 key 归属请求结果，并派生 loading 状态 |
| `frontend/src/components/MatchCard.tsx` | 继续使用语义化 `Link` 卡片，并补充南非、库拉索、科特迪瓦、海地、苏格兰等旗帜 |
| `frontend/src/api/client.ts` | 支持生产 `VITE_API_BASE_URL`，保留冠军预测和聊天接口类型 |
| `frontend/index.html`、`frontend/public/share-cover.svg` | 补充 H5 分享标题、描述、封面和主题色 |
| `frontend/src/App.tsx`、`frontend/src/pages/ProfilePage.tsx`、`frontend/src/pages/NotFoundPage.tsx` | 补齐「我的」页面和 404 页面，避免底部导航/未知路由断路 |
| `DEPLOY_H5.md` | 新增 H5 部署规划与检查清单 |

#### 数据修复记录

| 日期 | 修复/同步结果 |
|------|---------------|
| 2026-06-18 | 回补加拿大 6-0 卡塔尔、瑞士 4-1 波黑、捷克 1-1 南非、乌兹别克斯坦 1-3 哥伦比亚 |
| 2026-06-24 | 启动同步同款逻辑实际拉取并入库 5 场：苏格兰 0-3 巴西、摩洛哥 4-2 海地、波黑 3-1 卡塔尔、瑞士 2-1 加拿大、哥伦比亚 1-0 刚果（金） |
| 2026-06-25 | 默认 `/api/v1/matches` 只返回当天 2 场已完赛：捷克 0-3 墨西哥、南非 1-0 韩国 |

#### 验证结果

| 检查项 | 结果 |
|--------|------|
| `GET /api/v1/matches` | 通过；默认返回 `date=2026-06-25`、`include_unfinished=false`、共 2 场已完赛 |
| `GET /api/v1/matches?date=2026-06-24` | 通过；返回 5 场昨日已完赛比赛，队名已中文化 |
| `GET /api/v1/matches?date=2026-06-25&include_unfinished=true` | 通过；可返回当天已完赛 + 未开始比赛，用于调试 |
| `sync_worldcup_matches_for_date(2026-06-24)` | 通过；实际访问 API-Football 并写入 5 场 |
| `python -m compileall backend/app backend/scripts` | 通过 |
| `npm run build` | 通过 |
| `npm run lint` | 通过；已修复 `frontend/src/pages/NarrativePage.tsx:24` 的 hooks 规则问题 |

#### 新增待解决问题

| 问题 | 当前状态 | 下一步建议 |
|------|----------|------------|
| 启动同步只补昨天 | 当前只解决「昨天漏同步」这一条产品路径 | 增加最近 2-3 天补偿同步，避免 API 临时失败后留下空窗 |
| API-Football 免费计划窗口 | 免费计划不能回刷部分历史日期，旧比赛仍可能需要快照或手工回补 | 建立 `prediction_snapshot.json` 到比赛库的自动 reconciliation 脚本 |
| 首页日期来源 | 前端用浏览器日期计算昨日，后端默认用服务端日期 | 长期应统一暴露 `/matches/daily-summary`，由后端返回今日/昨日分组和数据时间 |

### 2026-06-23 追加更新：10000 次模拟与法国队热门对比

#### 改动摘要

将冠军预测的默认蒙特卡洛模拟次数从 `6000` 提升到 `10000`，并基于当前快照重新跑出 Top 10 冠军概率。随后对法国队与阿根廷、西班牙、英格兰、德国、巴西等争冠热门做了单项因子拆解，用于解释法国队当前评分位置。

#### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/services/prediction_model.py` | `build_prediction()` 默认模拟次数调整为 `10000` |
| `backend/app/api/predictions.py` | `/api/v1/predictions/champion` 的 `iterations` 默认查询参数调整为 `10000` |
| `frontend/src/api/client.ts` | `fetchChampionPrediction()` 默认请求模拟次数调整为 `10000` |

#### 10000 次模拟结果

当前快照时间为 `2026-06-23T08:29:08.900958+00:00`，随机种子为 `2026`。

| 排名 | 球队 | 冠军概率 | 进决赛 | 进四强 | 进八强 | 综合分 |
|------|------|----------|--------|--------|--------|--------|
| 1 | 阿根廷 | 38.71% | 53.32% | 72.38% | 89.53% | 92.52 |
| 2 | 法国 | 18.42% | 32.44% | 56.93% | 80.58% | 87.50 |
| 3 | 西班牙 | 17.96% | 32.93% | 52.22% | 79.96% | 87.88 |
| 4 | 英格兰 | 12.43% | 28.43% | 51.08% | 75.23% | 84.35 |
| 5 | 德国 | 4.39% | 15.77% | 36.88% | 73.53% | 77.43 |
| 6 | 哥伦比亚 | 2.50% | 9.67% | 25.55% | 53.76% | 77.23 |
| 7 | 巴西 | 1.60% | 6.18% | 17.37% | 44.76% | 75.36 |
| 8 | 荷兰 | 1.49% | 6.22% | 18.76% | 46.36% | 75.37 |
| 9 | 墨西哥 | 0.67% | 3.77% | 15.38% | 46.68% | 70.64 |
| 10 | 日本 | 0.67% | 3.10% | 11.53% | 32.19% | 71.28 |

#### 法国队评分拆解

| 因素 | 法国分数 | 权重 | 加权贡献 |
|------|----------|------|----------|
| Elo 实力 | 88.0 | 35% | 30.80 |
| 阵容质量 | 93 | 20% | 18.60 |
| 近期状态 | 80 | 20% | 16.00 |
| 大赛经验 | 92 | 10% | 9.20 |
| 防守能力 | 88 | 10% | 8.80 |
| 教练稳定性 | 82 | 5% | 4.10 |
| 伤病可用性 | 100 | 额外调整 | 0.00 |
| **综合分** |  |  | **87.50** |

#### 主要结论

| 对比 | 模型解释 |
|------|----------|
| 法国 vs 阿根廷 | 法国在防守和近期状态上不弱，但阿根廷 Elo、阵容质量和大赛经验更高；Elo 权重为 35%，导致阿根廷基础盘明显领先 |
| 法国 vs 西班牙 | 西班牙靠 Elo 和阵容质量领先，法国靠近期状态和大赛经验追回差距；两队综合分非常接近 |
| 法国 vs 英格兰 | 英格兰近期状态略好，但法国在 Elo、大赛经验、防守和教练稳定性上更均衡，因此冠军概率明显高于英格兰 |
| 法国潜力 | 当前模型认可法国是第二热门，但可能低估其淘汰赛中的阵容深度、冲击力、比赛管理和替补厚度 |

#### 验证结果

| 检查项 | 结果 |
|--------|------|
| `build_prediction(iterations=10000, seed=2026)` | 通过；返回 `iterations=10000` 和 Top 10 概率 |
| `GET /api/v1/predictions/champion` | 通过；默认返回 `iterations=10000` |
| `npm run build` | 通过 |

#### 新增模型待解决问题

| 问题 | 当前状态 | 下一步建议 |
|------|----------|------------|
| 法国队淘汰赛优势 | 当前仍以线性综合分为主，没有单独建模淘汰赛经验、阵容深度和比赛管理能力 | 增加 `knockout_resilience_score`、`squad_depth_score`、`transition_attack_score` 等因子 |
| 热门队路径优势 | 当前冠军概率不仅受综合分影响，也受简化 bracket 路径影响 | 接入 2026 官方 32 强落位规则，区分实力优势和赛程路径优势 |
| Elo 权重偏强 | Elo 对阿根廷、西班牙等队的基础盘影响较大，可能压制近期状态和阵容深度判断 | 用历史世界杯回测校准 Elo、近期状态、大赛经验的权重 |

### 修改文件

| 文件 | 改动 |
|------|------|
| `backend/app/services/prediction_model.py` | 新增冠军预测核心模型：球队综合评分、单场胜率、真实小组赛处理、32 强/淘汰赛模拟、冠军概率统计；优先读取 `prediction_snapshot.json`，缺失时回退内置种子数据 |
| `backend/app/api/predictions.py` | 新增预测 API：`/api/v1/predictions/champion?iterations=10000&seed=2026` |
| `backend/app/main.py` | 注册 `predictions_router` |
| `backend/scripts/sync_prediction_data.py` | 新增联网同步脚本，抓取 Elo、FIFA 排名页元数据、真实分组、小组赛赛程/比分、最终名单，并生成本地快照 |
| `backend/data/prediction_snapshot.json` | 新增预测输入快照：48 队、12 个真实小组、72 条小组赛 fixture/score、48 份最终名单 |
| `frontend/src/api/client.ts` | 新增冠军预测 API 类型与 `fetchChampionPrediction()` |
| `frontend/src/pages/PredictionPage.tsx` | 新增冠军预测页：Top 10 概率、晋级路径、模型因子展示、数据说明 |
| `frontend/src/App.tsx` | 新增 `/predictions` 路由 |
| `frontend/src/pages/HomePage.tsx` | 底部导航增加「预测」入口 |
| `frontend/src/index.css` | 新增预测页样式：概率条、模型因子条、晋级路径网格、Top 榜单 |

### 当前数据源

| 数据 | 来源 | 当前状态 |
|------|------|----------|
| 实时 Elo | `https://www.eloratings.net/World.tsv` | 已接入 |
| FIFA 排名页元数据 | `https://inside.fifa.com/fifa-world-ranking/men` | 已接入；完整积分表 API 暂未稳定解析 |
| 真实分组 | Wikipedia 2026 World Cup group pages | 已接入，并有当前分组兜底表 |
| 小组赛赛程/比分 | Wikipedia 2026 World Cup group pages | 已接入；已赛比分直接计入积分，未赛比赛由模型模拟 |
| 最终名单 | Wikipedia 2026 World Cup squads | 已接入，当前解析到 48 队最终名单 |
| 伤病/停赛 | 可选 `--injuries path/to/file.json` | 已预留接口，尚未接入稳定自动源 |

### 当前模型计算逻辑

综合实力评分：

```text
TeamScore =
  0.35 * EloScore
+ 0.20 * SquadScore
+ 0.20 * RecentFormScore
+ 0.10 * TournamentExperienceScore
+ 0.10 * DefenseScore
+ 0.05 * CoachStabilityScore
```

模拟流程：

1. 读取 `prediction_snapshot.json` 中的 48 队、真实小组、赛程和名单。
2. 将原始 Elo 映射为 0-100 的 `EloScore`。
3. 综合阵容、近期状态、大赛经验、防守、教练稳定性生成 `TeamScore`。
4. 小组赛中已有真实比分的比赛直接计入积分/净胜球/进球；未赛比赛按模型概率模拟。
5. 每组前 2 名 + 8 个成绩最好的小组第三进入 32 强。
6. 淘汰赛按单场胜率函数模拟，重复 `iterations` 次。
7. 统计各队进入 32 强、16 强、8 强、4 强、决赛、夺冠的概率。

### 验证结果

| 检查项 | 结果 |
|--------|------|
| `backend/scripts/sync_prediction_data.py` | 通过；生成 48 队、72 条 fixture、48 份最终名单 |
| `python -m compileall backend/app backend/scripts/sync_prediction_data.py` | 通过 |
| `GET /api/v1/predictions/champion?iterations=1000` | 通过；返回 `lightweight-v3-squad-form-availability` |
| `npm run build` | 通过 |
| `npm run lint` | 当时未通过；卡在既有 `frontend/src/pages/NarrativePage.tsx:24` 的 `react-hooks/set-state-in-effect` 规则，已在 2026-06-25 追加更新中修复 |

### 模型待解决问题

| 问题 | 当前状态 | 下一步建议 |
|------|----------|------------|
| FIFA 完整积分 | 官方页面可解析元数据，但稳定完整积分表 API 暂未找到 | 继续定位 FIFA 前端动态接口；若不可用，考虑接入可信第三方镜像或手动快照 |
| 阵容质量 | 当前主要使用内置评分 + 名单人数/不可用人数修正，尚未真正球员级建模 | 接入球员身价、俱乐部等级、近季出场时间、国家队首发概率 |
| 近期状态 | 当前仍偏静态，没有完整使用近 10-20 场赛果 | 接入近期比赛结果、对手 Elo、净胜球、进失球、Elo 变化 |
| 防守稳定性 | 当前仍是内置/派生评分 | 接入场均失球、零封率、被射门、xGA 等指标 |
| 伤病/停赛 | 只预留了 `--injuries` JSON 输入 | 寻找稳定伤病数据源，或建立人工维护的伤停快照 |
| 淘汰赛 bracket | 当前 32 强配对仍是简化模型，不是完整 FIFA 官方路径 | 接入 2026 官方 32 强对阵映射和第三名落位规则 |
| 概率校准 | 尚未用历史世界杯回测校准权重 | 用 2014/2018/2022 世界杯回测 Brier Score、Log Loss、Top-K 命中率 |
| 主场/旅途/气候 | 暂未显式建模 | 对加拿大/美国/墨西哥主办优势、旅行距离、气候适应增加修正项 |
| 小样本爆冷 | 当前 sigmoid 单场模型较简单 | 引入 draw/加时/点球分层模型，增强淘汰赛不确定性表达 |

### 关键技术决策

**快照优先而非请求时联网**：预测接口读取本地 `prediction_snapshot.json`，避免每次打开页面都依赖外网，保证页面响应稳定。数据更新由 `sync_prediction_data.py` 显式触发。

**真实结果优先**：如果小组赛已有比分，模型不再重新模拟该场，而是直接计入真实积分；只有未赛比赛才按概率模拟。

**模型保持轻量可解释**：当前仍采用可解释加权评分 + Monte Carlo，而不是直接上复杂黑盒模型，方便后续逐项替换特征和回测权重。

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

# Myna 生产环境架构文档

> **最后更新**: 2026-08-03
> **维护者**: 请在每次变更后更新此文档
> **用途**: 任何人修改代码前必须先阅读本文档，避免误改错误的代码副本

---

## 一、容器物理拓扑

```
容器名:       myna-app
镜像:         myna:recovered-20260730-home-files-v2
启动时间:     2026-08-01 17:52 UTC
进程:         python3 main.py (PID=1)
工作目录:     /app/backend
Python:       3.11
```

### 挂载关系（docker inspect myna-app）

| 容器路径 | 宿主机路径 | 类型 | 用途 |
|---|---|---|---|
| `/app/data` | ivy-myna_app_data (Volume) | 持久化 | 数据库、上传、workspace |
| `/app/db` | ivy-myna_app_db (Volume) | 持久化 | 备用数据库目录(当前未使用) |
| `/root/.hermes/profiles` | ivy-myna_hermes_profiles (Volume) | 持久化 | Hermes Agent 配置文件 |
| `/app/docker-compose.yml` | /data/myna/docker-compose.yml | 只读绑定 | Compose 配置 |

---

## 二、运行时后端代码（这才是真正运行的代码）

### 入口文件: `/app/backend/main.py`

### 导入关系树

```
main.py (PID=1, cwd=/app/backend)
├── from db import get_database
│   └── 实际文件: /app/backend/db.py (1765行)
│       包含: create_room, delete_room, delete_agent, get_model_config 等
│
├── from routes.admin import router
│   └── 实际文件: /app/backend/routes/admin.py (1966行)
│       包含: 所有 /admin/* 路由
│       import: ai_engine (下一级)
│
├── from routes.auth import router
│   └── 实际文件: /app/backend/routes/auth.py
│
├── from routes.upload import router
│   └── 实际文件: /app/backend/routes/upload.py
│
├── from routes.gateway import router
│   └── 实际文件: /app/backend/routes/gateway.py
│
├── from routes.system_agent import router
│   └── 实际文件: /app/backend/routes/system_agent.py
│
├── import ai_engine (由 routes/admin.py 间接引入)
│   └── 实际文件: /app/backend/ai_engine.py (2240行)
│       ⚠️ 注意: 此文件与 Git 仓库中的 /app/backend/Myna/backend/ai_engine.py
│       版本不同 (后者 2727行)，运行中的版本是精简版
│
├── from workflow_engine import WorkflowRunner
│   └── 实际文件: /app/backend/workflow_engine.py
│
├── from credentials import CredentialStore
│   └── 实际文件: /app/backend/credentials.py
│
├── from system_agent import SystemAgent
│   └── 实际文件: /app/backend/system_agent.py
│
└── from backend.paths import APP_ROOT, DB_ROOT
    └── 实际文件: /app/backend/backend/paths.py
        APP_ROOT = /app
        DB_ROOT  = /app/data
```

### 静态文件服务

```python
# main.py 中的挂载
frontend_dist = APP_ROOT / "src" / "web" / "public"
# 即: /app/src/web/public

app.mount("/", StaticFiles(directory=frontend_dist, html=True))
```

**结论**: 浏览器访问的所有静态资源都来自 `/app/src/web/public/`

---

## 三、Git 仓库（源码管理，但不直接运行）

```
路径:  /app/backend/Myna/
最近:  d372b91 feat: show model info in message metadata (#11)
分支:  master (推断)
```

### Git 仓库中的代码 vs 运行中的代码

| 文件 | Git 仓库 | 运行中 | 是否相同 |
|---|---|---|---|
| routes/admin.py | 1966行 | 1966行 | ✓ |
| db.py | 1757行 | 1765行 | ≈ 相近 |
| ai_engine.py | 2727行 | 2240行 | ✗ 差异大 |
| 前端源码 | /app/backend/Myna/frontend/src/ | (构建发布到 /app/src/web/public/) | - |

⚠️ **重要**: 修改后端代码时，必须同时更新:
1. `/app/backend/xxx.py` (运行代码)
2. `/app/backend/Myna/backend/xxx.py` (Git 仓库)
两个位置都要改，否则下次从 Git 构建镜像时会丢失修改。

---

## 四、前端链路

### 源码

```
构建源:     /app/backend/Myna/frontend/src/
工具:       vite v8.0.14
命令:       cd /app/backend/Myna/frontend && npm run build
产物:       /app/backend/Myna/src/web/public/
```

### 部署

```bash
# 当前部署流程
cd /app/backend/Myna/frontend && npm run build
cp -r /app/backend/Myna/src/web/public/. /app/src/web/public/
```

### 关键问题

```
构建产物目录:  /app/backend/Myna/src/web/public/ (7个js)
服务读取目录:  /app/src/web/public/ (77个js — 历史残留未清理)
```

**建议**: 每次构建后先清理旧资源再复制:
```bash
rm -rf /app/src/web/public/assets /app/src/web/public/index.html
cp -r /app/backend/Myna/src/web/public/. /app/src/web/public/
```

### 当前上线资源

```
index.html 指向: /assets/index-BuRn4hwB.js
CSS: /assets/index-ByO7Uz5d.css
构建时间: 2026-08-03 08:32 UTC
```

### 额外前端副本

```
/app/frontend/src/  与 /app/backend/Myna/frontend/src/ 当前文件大小一致
但前者少一个 vue 文件
```

**⚠️ 本地 Windows 工作区**:
```
D:\myna\frontend\src\  与生产源码差异显著，不要再直接覆盖生产
```

---

## 五、数据库

### 生产数据库（唯一）

```
路径:     /app/data/db/myna.sqlite
进程打开: /proc/1/fd/11,12,13,18 → 该文件
统计:     42 房间, 2773 消息, 112 智能体, 25 模型配置, 20 张表
```

### 重要配置

```
默认统筹智能体: 64efada1-5a31-4ce5-8f09-e1ab10b8fdc6 (马哥)
当前默认模型:   qweapi.com - claude-fable-5 (base_url: https://qweapi.com/v1)
表结构:         见 db.py create 方法
```

### 其他数据库（不运行，不能配置）

```
/app/db/myna.sqlite            — 16 房间, 10 智能体
/app/backend/data/db/myna.sqlite — 1 房间, 6 智能体
/app/backend/db/myna.sqlite    — 空
/app/backend/Myna/data/db/myna.sqlite — 1 房间
```

---

## 六、核心功能调用链

### 首页发送消息

```
用户点击绿色箭头
  ↓
AssistantHome.vue → send()
  ↓ 检查输入内容非空
  ↓ submitPrompt(value)
  ↓ emit('start-chat', { prompt, mode, temperature })
  ↓
App.vue → startAssistantChat(options)
  ↓
  ↓ ① POST /admin/collaboration/planning-room
  ↓    后端: /app/backend/routes/admin.py
  ↓    DB: create_room, add_member
  ↓
  ↓ ② POST /admin/rooms/{id}/send
  ↓    后端: /app/backend/routes/admin.py → ai_engine.process_message
  ↓    DB: create_message, process_message 异步
  ↓
  ↓ ③ loadConversations({ force: true })
  ↓    GET /admin/rooms, GET /admin/dms
  ↓
  ↓ ④ page.value = 'chats', openChat(room, 'group')
  ↓    URL → #chat/{roomId}
  ↓
ChatView.vue 挂载
  ↓ GET /admin/rooms/{id}/messages?limit=30
  ↓ GET /admin/rooms/{id}/threads  ← 后台拉取（前端未显示thread）
  ↓ 渲染前端消息
```

### 消息列表

```
ChatList.vue (onMounted)
  ↓ loadConversations() → GET /admin/rooms + GET /admin/dms
  ↓ visibleConversations = rooms + dms 合并排序
  ↓ 点击列表项 → emit('open-chat') → App.vue openChat()
```

### 聊天页发送

```
ChatView.vue → send()
  ↓ POST /admin/rooms/{id}/send
  ↓ ai_engine.process_message 异步处理
```

### 批量删除

```
ChatList.vue → confirmBatchDelete()
  ↓ POST /admin/conversations/batch-delete
  ↓ items: [{ id, type }, ...]
  ↓ 后端: /app/backend/routes/admin.py (行683)
```

---

## 七、API 差异清单（前端调用 vs 后端路由）

| 前端调用 | 后端路由 | 状态 |
|---|---|---|
| POST /admin/conversations/batch-delete | ✓ 已补 | 容器重建会丢失 |
| GET /admin/pinned-conversations | ✗ 不存在 | 返回 404 |
| GET /admin/token-usage/by-room | ✗ 不存在 | 返回 404 |

---

## 八、变更操作规范

### 修改后端代码

```bash
# 1. 修改运行代码
vi /app/backend/routes/admin.py    # 或其他文件

# 2. 同步到 Git 仓库
cp /app/backend/routes/admin.py /app/backend/Myna/backend/routes/admin.py

# 3. 如果修改涉及路由注册，重启容器
docker restart myna-app

# 4. 验证
curl http://127.0.0.1:3455/health
curl http://127.0.0.1:3455/admin/新路由   # 测试新路由
```

### 修改前端代码

```bash
# 1. 修改构建源
vi /app/backend/Myna/frontend/src/components/xxx.vue

# 2. 构建
cd /app/backend/Myna/frontend && npm run build

# 3. 清理旧资源并部署（关键！不能跳过清理）
rm -rf /app/src/web/public/assets /app/src/web/public/index.html
cp -r /app/backend/Myna/src/web/public/. /app/src/web/public/

# 4. 同步前端副本
cp /app/backend/Myna/frontend/src/components/xxx.vue /app/frontend/src/components/xxx.vue

# 5. 验证
curl http://127.0.0.1:3455/ | head -12   # 检查新 js hash
```

### 数据库变更

```bash
# 只操作生产库
DB=/app/data/db/myna.sqlite
sqlite3 $DB "SELECT ..."

# 绝对不要操作以下数据库:
# /app/db/myna.sqlite
# /app/backend/data/db/myna.sqlite
# /app/backend/db/myna.sqlite
# /app/backend/Myna/data/db/myna.sqlite
```

### 禁止操作

```
❌ docker cp 单个文件进运行容器然后不记录
❌ 从本地 Windows D:\myna 直接覆盖生产文件
❌ 同时改 /app/frontend/ 和 /app/backend/Myna/frontend/ 但只构建一个
❌ 改数据库但不知道是哪个数据库
❌ 改路由不重启容器
❌ 改前端不清除历史产物 (/app/src/web/public 残留)
❌ 发布前端大改不做 HTML 验证 (curl 看新的 js hash)
```

---

## 九、已知问题

1. **MYNA_ENCRYPTION_KEY 未设置**: 凭据加密在容器重建后会丢失
2. **/app/src/web/public 历史产物堆积**: 77个js可能被浏览器惰性加载
3. **批量删除路由是热补**: 容器重建后需重新确认
4. **ai_engine.py 运行版与Git版不同**: 可能需要回溯差异
5. **两个前端源码目录**: 应当只保留一个
6. **本地工作区和生产源码不同步**: 本地文件不能再用
7. **478 ← reserved line count mark (display artifact)**

---

## 十、联系人

```
更新此文档: 每次架构/部署变更后必须更新
文档位置:   /app/backend/Myna/ARCHITECTURE.md
```

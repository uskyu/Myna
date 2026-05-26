# hermes-hub

多智能体协作平台 — 类 Telegram Bot API 风格的 Gateway，让多个 AI Agent 在"群聊"中协作。

## 特性

- **Telegram 风格 Bot API** — Agent 用一个 API Key 接入，`/sendMessage`、`/getUpdates` 即可通信
- **房间系统** — 创建房间，拉入多个 Agent，它们互相 @、自动协作
- **Markdown 支持** — 消息支持完整 Markdown 渲染
- **Docker 一键部署** — `docker-compose up` 即可运行
- **Agent 容器管理** — 通过 Web UI 一键创建/停止 Agent 容器

## 快速开始（本地开发）

```bash
# 安装依赖
npm install

# 启动服务
npm start

# 开发模式（自动重启）
npm run dev
```

服务启动后：
- Web UI: http://localhost:3000
- Gateway API: http://localhost:3000/bot{API_KEY}/

## Gateway API

模仿 Telegram Bot API 风格：

```
POST /bot{api_key}/sendMessage
  body: { room_id, text, parse_mode: "markdown" }

POST /bot{api_key}/getUpdates
  body: { offset, limit }

POST /bot{api_key}/sendMessage
  body: { room_id, text, reply_to_message_id, mentions: ["agent_name"] }
```

## 环境变量

```env
PORT=3000              # 服务端口
SECRET_KEY=xxx         # Admin 认证密钥
DATA_DIR=./db          # SQLite 数据目录
```

## Docker 部署

```bash
docker-compose up -d
```

## 架构

```
┌─────────────────────────────────────────┐
│              hermes-hub                  │
├─────────────┬───────────┬───────────────┤
│  Gateway    │ Orchestr. │ Agent Manager │
│  (Bot API)  │ (Rooms)   │ (Docker)      │
├─────────────┴───────────┴───────────────┤
│           SQLite + WebSocket            │
└─────────────────────────────────────────┘
```

## License

MIT

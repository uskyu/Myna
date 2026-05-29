# [开源] Myna — 多智能体协作平台，对话即协作，自主进化，完全自定义 API

## 项目地址

GitHub: https://github.com/uskyu/myna

## 这是什么

一个轻量的多智能体协作平台，部署在自己服务器上，多个 AI Agent 在群聊里通过 @提及 自动接力完成任务。

比如我日常用法：跟「程序开发」说一句需求，它写完代码自动 @程序测试员 去测，测试员发现 bug 再 @回开发修，全程不用我管。

## 跟 Dify / Coze / CrewAI 有什么区别

| | Myna | Dify | Coze | CrewAI |
|---|---|---|---|---|
| 协作方式 | 对话 @提及接力 | 拖拽流程图 | 拖拽流程图 | 写代码定义 |
| 自主学习 | ✅ 自动提取技能 | ❌ | ❌ | 部分 |
| 自定义 API | ✅ 任意 OpenAI 格式 | ✅ | ⚠️ 绑字节模型 | ✅ |
| 部署复杂度 | 1 条命令 | Redis+PG+微服务 | 云端不可自托管 | 纯代码无 UI |
| Web UI | ✅ 开箱即用 | ✅ | ✅ | ❌ |

**核心差异：不需要画流程图，不需要写代码编排，对话里 @ 就行。**

## 主要特性

- 🔗 **链式协作** — Agent 之间 @提及自动触发，无限接力
- 🧠 **自主进化** — 多步操作后自动提取技能，越用越聪明
- 🌐 **完全自定义 API** — 兼容任意 OpenAI 格式接口，自由选模型
- 🛠 **完整工具链** — 终端、文件读写、HTTP 请求、代码搜索
- ✅ **审批机制** — auto / confirm / manual 三档，不是黑盒
- 📡 **实时流式输出** — WebSocket 推送，工具调用过程全程可见
- 🐳 **一键部署** — `docker compose up -d`，SQLite 零配置

## 实际效果

### 链式协作：开发 → 测试 → 修复

【配图1：chain-workflow.jpg — 开发→测试→修复的协作流程截图】

### 链式对话触发

【配图2：chain-chat.jpg — 对话界面中 Agent 之间 @提及接力的示意图】

### 自主进化：自动提取技能

【配图3：self-improve.jpg — Agent 自动提取技能的界面截图】

## 快速开始

```bash
git clone https://github.com/uskyu/myna.git
cd myna
docker compose up -d
```

打开 `http://你的IP:3456`，默认密码 `admin`，进去改。

## 技术栈

- 后端：Python 3.11 + FastAPI + Hermes Agent 引擎
- 前端：Vue 3 + Vite
- 数据库：SQLite（默认）/ MySQL（可选）
- 部署：Docker Compose 单容器

## 适合谁

- 想让多个 AI Agent 协作干活，但不想画流程图
- 想用自己的 API Key / 自建模型，不想被平台绑定
- 想要 Agent 能记住经验、越用越好用
- 想要一个轻量的自托管方案，不想搞一堆中间件

---

第一次做这类项目，还有很多不完善的地方，欢迎大佬们指点。有问题直接开 issue 或者在下面回复，功能建议也欢迎提，一起完善。

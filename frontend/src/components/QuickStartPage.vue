<template>
  <div class="page active quickstart-page">
    <div class="header"><h1>快速开始</h1></div>
    <main class="quickstart-workspace">
      <section class="quickstart-hero">
        <p class="eyebrow">Quick Start</p>
        <h2>样例模板 / 快速建队</h2>
        <p>选择一个模板，系统会自动创建或复用智能体，创建群聊并加入成员，完成后直接打开样例群聊。</p>
      </section>

      <section class="template-grid" aria-label="样例模板">
        <article v-for="tpl in teamTemplates" :key="tpl.id" class="template-card">
          <div class="template-card-head">
            <div>
              <h3>{{ tpl.name }}</h3>
              <p>{{ tpl.description }}</p>
            </div>
            <span class="member-count">{{ tpl.members.length }} 人</span>
          </div>
          <div class="role-list">
            <span v-for="member in tpl.members" :key="member.name" class="role-chip">{{ member.name }}</span>
          </div>
          <div v-if="templateResult[tpl.id]" class="template-status success">
            已创建「{{ templateResult[tpl.id].roomName }}」，{{ templateResult[tpl.id].memberCount }} 名成员已加入。
          </div>
          <div v-if="templateErrors[tpl.id]" class="template-status error">{{ templateErrors[tpl.id] }}</div>
          <button
            type="button"
            class="primary-action"
            :disabled="creatingTemplate === tpl.id"
            @click="createTemplateTeam(tpl)"
          >
            {{ creatingTemplate === tpl.id ? '正在创建...' : '一键创建并打开' }}
          </button>
        </article>
      </section>
    </main>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { api, loadAgents, loadConversations, store } from '../store.js'

const emit = defineEmits(['open-room'])

const creatingTemplate = ref('')
const templateErrors = reactive({})
const templateResult = reactive({})

const teamTemplates = [
  {
    id: 'product-launch',
    name: '产品落地小队',
    description: '适合把一个想法拆成需求、实现方案和验收清单。',
    roomDescription: '样例团队：围绕产品需求、程序实现和测试验收协作。',
    members: [
      { name: '产品经理', description: '负责澄清目标、拆解需求、定义验收标准，并推动团队形成可落地方案。' },
      { name: '程序开发', description: '负责把需求转成可执行技术方案，以最小可行改动完成实现并说明取舍。' },
      { name: '测试员', description: '负责测试用例、边界条件、回归验证和发布风险检查。' },
    ],
  },
  {
    id: 'content-creation',
    name: '内容创作小队',
    description: '适合从选题、文案到视觉表达完整产出内容。',
    roomDescription: '样例团队：围绕内容策划、文案编辑和视觉表达协作。',
    members: [
      { name: '选题策划', description: '负责定位受众、筛选选题角度、规划内容结构和传播目标。' },
      { name: '内容编辑', description: '负责资料整理、撰写润色、统一语气，并把想法整理成可发布文本。' },
      { name: '视觉设计师', description: '负责画面风格、版式建议、封面方向和视觉素材提示词。' },
    ],
  },
  {
    id: 'code-fix',
    name: '代码修复小队',
    description: '适合定位问题、实施修复并完成回归验证。',
    roomDescription: '样例团队：围绕问题定位、代码修复和回归测试协作。',
    members: [
      { name: '问题定位', description: '负责复现问题、缩小范围、分析日志和提出根因假设。' },
      { name: '程序开发', description: '负责以最小改动实现修复，并说明关键取舍。' },
      { name: '测试员', description: '负责设计验证步骤、覆盖关键路径并整理验收结果。' },
    ],
  },
]

function setTemplateError(id, message) {
  templateErrors[id] = message
  delete templateResult[id]
}

function clearTemplateState(id) {
  templateErrors[id] = ''
  delete templateResult[id]
}

async function createTemplateTeam(template) {
  if (creatingTemplate.value) return
  creatingTemplate.value = template.id
  clearTemplateState(template.id)
  try {
    const agentData = await api('GET', '/admin/agents')
    if (agentData.ok === false) throw new Error(agentData.error || '读取智能体失败')
    const existingAgents = agentData.result || []
    const createdOrReused = []

    for (const member of template.members) {
      let agent = existingAgents.find(a => a.name === member.name && a.id !== 'system' && a.id !== 'user')
      if (!agent) {
        const created = await api('POST', '/admin/agents', { name: member.name, description: member.description })
        if (created.ok === false || !created.result) throw new Error(created.error || `创建智能体「${member.name}」失败`)
        agent = created.result
        existingAgents.push(agent)
      }
      createdOrReused.push(agent)
    }

    const now = new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    const roomName = `样例：${template.name} ${now}`
    const roomData = await api('POST', '/admin/rooms', { name: roomName, description: template.roomDescription })
    if (roomData.ok === false || !roomData.result) throw new Error(roomData.error || '创建群聊失败')
    const room = roomData.result

    for (const agent of createdOrReused) {
      const memberData = await api('POST', `/admin/rooms/${room.id}/members`, { agent_id: agent.id })
      if (memberData.ok === false) throw new Error(memberData.error || `加入成员「${agent.name}」失败`)
    }

    await Promise.all([loadAgents(), loadConversations()])
    const openedRoom = store.rooms.find(r => r.id === room.id) || { ...room, members: createdOrReused }
    templateResult[template.id] = { roomName, memberCount: createdOrReused.length }
    emit('open-room', openedRoom)
  } catch (e) {
    setTemplateError(template.id, e.message || '创建失败，请稍后重试')
  } finally {
    creatingTemplate.value = ''
  }
}
</script>

<style scoped>
.quickstart-page {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.quickstart-workspace {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px;
}

.quickstart-hero,
.template-card {
  border: 1px solid rgba(45, 106, 79, 0.16);
  background: var(--surface, #fff);
  box-shadow: var(--shadow-sm);
}

.quickstart-hero {
  border-radius: 24px;
  padding: clamp(22px, 4vw, 40px);
  margin-bottom: 18px;
  background: linear-gradient(135deg, #faf9f7 0%, rgba(45, 106, 79, 0.08) 100%);
}

[data-theme="dark"] .quickstart-hero,
[data-theme="dark"] .template-card {
  background: var(--surface);
  border-color: var(--border);
}

.eyebrow {
  margin: 0 0 8px;
  color: #d97706;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.quickstart-hero h2 {
  margin: 0;
  color: var(--text);
  font-size: clamp(28px, 4vw, 44px);
  letter-spacing: -0.05em;
}

.quickstart-hero p:not(.eyebrow) {
  max-width: 760px;
  margin: 12px 0 0;
  color: var(--text-dim);
  font-size: 15px;
  line-height: 1.7;
}

.template-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 16px;
}

.template-card {
  display: flex;
  flex-direction: column;
  gap: 16px;
  border-radius: 20px;
  padding: 18px;
  background: #faf9f7;
}

.template-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.template-card h3 {
  margin: 0;
  color: var(--text);
  font-size: 17px;
}

.template-card p {
  margin: 7px 0 0;
  color: var(--text-dim);
  font-size: 13px;
  line-height: 1.6;
}

.member-count {
  flex-shrink: 0;
  border-radius: 999px;
  background: rgba(217, 119, 6, 0.12);
  color: #d97706;
  font-size: 12px;
  font-weight: 800;
  padding: 6px 10px;
}

.role-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.role-chip {
  border: 1px solid rgba(45, 106, 79, 0.18);
  border-radius: 999px;
  color: #2d6a4f;
  background: rgba(45, 106, 79, 0.07);
  font-size: 12px;
  font-weight: 700;
  padding: 6px 9px;
}

.primary-action {
  border: none;
  border-radius: 13px;
  background: #2d6a4f;
  color: white;
  font-weight: 800;
  padding: 11px 16px;
  cursor: pointer;
}

.primary-action:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.template-status {
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.45;
}

.template-status.success {
  color: #2d6a4f;
}

.template-status.error {
  color: #e53e3e;
}

@media (min-width: 768px) {
  .quickstart-workspace {
    padding: 20px 24px 24px;
  }
}
</style>

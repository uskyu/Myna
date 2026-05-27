<template>
  <div class="agent-detail active">
    <div class="chat-header">
      <button class="back-btn" @click="$emit('close')" aria-label="返回">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <span class="title">{{ form.name || agent.name }}</span>
      <button class="back-btn" style="margin-left:auto" @click="startDM" title="发消息">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      </button>
    </div>
    <div class="agent-detail-content">
      <!-- Header card -->
      <div class="profile-head">
        <div class="avatar-large" :style="{ background: getAgentColor(idx) }">
          <span v-html="getAgentIcon(idx)"></span>
        </div>
        <div class="head-meta">
          <input class="head-name-input" v-model="form.name" @blur="saveField('name')" placeholder="智能体名称">
          <div class="status-row">
            <button type="button" class="toggle small" :class="{ on: form.status === 'online' }" @click="toggleStatus" aria-label="状态切换"></button>
            <span class="status-text">{{ form.status === 'online' ? '在线' : '离线' }}</span>
            <span v-if="saving" class="saving-tag">保存中...</span>
            <span v-else-if="lastSavedTag" class="saved-tag">{{ lastSavedTag }}</span>
          </div>
        </div>
      </div>

      <!-- Description / system prompt -->
      <div class="field-block">
        <label>描述 / 系统提示词</label>
        <textarea
          v-model="form.description"
          @blur="saveField('description')"
          placeholder="定义智能体的角色和行为..."
          rows="4"
        ></textarea>
      </div>

      <!-- Model picker -->
      <div class="field-block">
        <div class="field-head">
          <label>关联模型</label>
          <button class="link-btn" @click="showModels = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            管理供应商
          </button>
        </div>
        <select v-model="form.model_config_id" @change="saveField('model_config_id')" class="model-select">
          <option value="">使用默认配置</option>
          <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }} — {{ m.model }}</option>
        </select>
        <div v-if="selectedModel" class="model-preview">
          <span class="model-preview-tag">{{ selectedModel.model }}</span>
          <span v-if="selectedModel.max_tokens" class="model-preview-meta">{{ formatCtx(selectedModel.max_tokens) }} ctx</span>
          <span class="model-preview-base">{{ selectedModel.base_url }}</span>
        </div>
      </div>

      <!-- Sections -->
      <div class="profile-section">
        <h4>🛠 技能</h4>
        <div class="hint">暂无技能</div>
      </div>
      <div class="profile-section">
        <h4>📚 知识库</h4>
        <div class="hint">暂无知识库文件</div>
      </div>
      <div class="profile-section">
        <h4>⚙️ 工具</h4>
        <div class="profile-list-item">run_command — 执行系统命令</div>
        <div class="profile-list-item">read_file — 读取文件内容</div>
      </div>

      <div style="margin-top:32px;padding-top:16px;border-top:1px solid var(--border)">
        <button class="btn btn-danger" @click="$emit('delete', agent.id)" style="width:100%">删除智能体</button>
      </div>
    </div>

    <ModelsModal v-if="showModels" @close="onModelsClose" @changed="loadModels" />
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { api, getAgentColor, getAgentIcon, store, loadConversations } from '../store.js'
import ModelsModal from './ModelsModal.vue'

const props = defineProps({ agent: Object })
const emit = defineEmits(['close', 'delete'])

const models = ref([])
const showModels = ref(false)
const saving = ref(false)
const lastSavedTag = ref('')

const form = reactive({
  name: props.agent.name,
  description: props.agent.description || '',
  model_config_id: props.agent.model_config_id || '',
  status: props.agent.status || 'online',
})

const idx = computed(() => store.agents.findIndex(a => a.id === props.agent.id))

const selectedModel = computed(() => models.value.find(m => m.id === form.model_config_id))

function formatCtx(n) {
  if (!n) return ''
  if (n >= 1000000) return (n / 1000000).toFixed(1).replace(/\.0$/, '') + 'M'
  if (n >= 1000) return (n / 1000).toFixed(0) + 'k'
  return String(n)
}

async function persist() {
  saving.value = true
  lastSavedTag.value = ''
  try {
    await api('PUT', `/admin/agents/${props.agent.id}`, {
      name: form.name,
      description: form.description,
      model_config_id: form.model_config_id || null,
      status: form.status,
    })
    Object.assign(props.agent, {
      name: form.name,
      description: form.description,
      model_config_id: form.model_config_id || null,
      status: form.status,
    })
    // refresh agents store entry
    const idxStore = store.agents.findIndex(a => a.id === props.agent.id)
    if (idxStore >= 0) Object.assign(store.agents[idxStore], props.agent)
    lastSavedTag.value = '已保存'
    setTimeout(() => { lastSavedTag.value = '' }, 1600)
  } catch(e) {
    lastSavedTag.value = '保存失败'
  } finally {
    saving.value = false
  }
}

let saveTimer = null
function debouncedPersist() {
  if (saveTimer) clearTimeout(saveTimer)
  saveTimer = setTimeout(persist, 250)
}

async function saveField(field) {
  // Normalize empties
  if (field === 'name' && !form.name.trim()) {
    form.name = props.agent.name
    return
  }
  debouncedPersist()
}

async function toggleStatus() {
  form.status = form.status === 'online' ? 'offline' : 'online'
  debouncedPersist()
}

async function startDM() {
  const data = await api('POST', `/admin/dm/${props.agent.id}`)
  if (data.ok) {
    await loadConversations()
    // Close detail and let parent route to chat — simple fallback
    emit('close')
    // The store/App should pick up the new dm room. Trigger reload as fallback if needed
    window.dispatchEvent(new CustomEvent('open-dm', { detail: { agentId: props.agent.id, roomId: data.result?.room_id } }))
  }
}

async function loadModels() {
  const data = await api('GET', '/admin/models')
  models.value = data.result || []
}

function onModelsClose() {
  showModels.value = false
  loadModels()
}

onMounted(loadModels)
</script>

<style scoped>
.profile-head {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 18px 4px 22px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 18px;
}
.head-meta { flex: 1; min-width: 0; }
.head-name-input {
  width: 100%;
  font-size: 22px;
  font-weight: 700;
  letter-spacing: -0.01em;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text);
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  margin: 0 0 6px -8px;
  transition: all 0.15s ease;
}
.head-name-input:hover { border-color: var(--border); background: var(--surface2); }
.head-name-input:focus { outline: none; border-color: var(--accent); background: var(--surface); }

.status-row { display: flex; align-items: center; gap: 8px; padding-left: 0; }
.status-text { font-size: 13px; color: var(--text-dim); }
.saving-tag, .saved-tag {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--accent-soft);
  color: var(--accent);
  font-weight: 600;
  margin-left: 6px;
}
.saving-tag { color: var(--text-dim); background: var(--surface2); }

.toggle.small { width: 36px; height: 20px; }

.field-block { margin-bottom: 18px; }
.field-block label {
  display: block;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-dim);
  font-weight: 700;
  margin-bottom: 8px;
}
.field-head {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 8px;
}
.field-head label { margin: 0; }
.link-btn {
  background: transparent;
  border: 1px solid var(--border);
  color: var(--text-2);
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  display: inline-flex; align-items: center; gap: 5px;
  text-transform: none; letter-spacing: 0;
  transition: all 0.15s ease;
}
.link-btn:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-soft); }

.field-block textarea {
  width: 100%;
  min-height: 96px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
  resize: vertical;
  line-height: 1.55;
}
.field-block textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--shadow-glow);
}

.model-select {
  width: 100%;
  padding: 11px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  background: var(--surface);
  color: var(--text);
}
.model-select:focus { outline: none; border-color: var(--accent); box-shadow: var(--shadow-glow); }

.model-preview {
  margin-top: 8px;
  padding: 10px 12px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 12px;
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
}
.model-preview-tag {
  font-family: var(--font-mono);
  color: var(--accent);
  font-weight: 600;
}
.model-preview-meta {
  font-family: var(--font-mono);
  background: var(--surface);
  border: 1px solid var(--border);
  padding: 1px 8px;
  border-radius: 999px;
  color: var(--text-dim);
}
.model-preview-base {
  font-family: var(--font-mono);
  color: var(--text-dim);
  margin-left: auto;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}
</style>

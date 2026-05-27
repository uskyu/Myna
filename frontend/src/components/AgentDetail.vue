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

      <!-- Skills section -->
      <div class="profile-section">
        <div class="section-head">
          <h4>🛠 技能</h4>
          <button class="link-btn" @click="showAddSkill = true">+ 添加</button>
        </div>
        <div v-if="skills.length === 0" class="hint">暂无技能，点击添加</div>
        <div v-else class="skills-list">
          <div v-for="skill in skills" :key="skill.id" class="skill-item">
            <div class="skill-info">
              <span class="skill-name">{{ skill.name }}</span>
              <span class="skill-desc">{{ skill.description || '无描述' }}</span>
            </div>
            <div class="skill-actions">
              <button class="skill-action-btn" @click="editSkill(skill)" title="编辑">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
              </button>
              <button class="skill-action-btn" @click="downloadSkill(skill)" title="下载">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
              </button>
              <button class="skill-action-btn danger" @click="removeSkill(skill)" title="删除">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
              </button>
            </div>
          </div>
        </div>
        <div class="skill-upload-row">
          <button class="link-btn" @click="triggerUpload">📁 上传技能文件</button>
          <input ref="skillFileInput" type="file" accept=".md,.txt,.json,.yaml,.yml" style="display:none" @change="onSkillFileUpload" />
        </div>
      </div>

      <!-- Knowledge base -->
      <div class="profile-section">
        <h4>📚 知识库</h4>
        <div class="hint">暂无知识库文件</div>
      </div>

      <!-- Tools -->
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

    <!-- Add/Edit Skill Modal -->
    <Teleport to="body">
      <div v-if="showAddSkill || editingSkill" class="skill-modal-overlay" @click.self="closeSkillModal">
        <div class="skill-modal">
          <div class="skill-modal-header">
            <h4>{{ editingSkill ? '编辑技能' : '添加技能' }}</h4>
            <button class="wf-close" @click="closeSkillModal">×</button>
          </div>
          <div class="skill-modal-body">
            <div class="wf-field">
              <label>名称</label>
              <input v-model="skillForm.name" placeholder="例如：数据分析" />
            </div>
            <div class="wf-field">
              <label>描述</label>
              <input v-model="skillForm.description" placeholder="这个技能做什么？" />
            </div>
            <div class="wf-field">
              <label>内容</label>
              <textarea v-model="skillForm.content" placeholder="技能指令内容..." rows="10" class="skill-content-textarea"></textarea>
            </div>
          </div>
          <div class="skill-modal-footer">
            <button class="btn-cancel" @click="closeSkillModal">取消</button>
            <button class="btn-save" :disabled="!skillForm.name.trim()" @click="saveSkill">保存</button>
          </div>
        </div>
      </div>
    </Teleport>
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

// Skills state
const skills = ref([])
const showAddSkill = ref(false)
const editingSkill = ref(null)
const skillForm = reactive({ name: '', description: '', content: '' })
const skillFileInput = ref(null)

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
    emit('close')
    window.dispatchEvent(new CustomEvent('open-dm', { detail: { agentId: props.agent.id, roomId: data.result?.room_id } }))
  }
}

// === Skills ===
async function loadSkills() {
  const data = await api('GET', `/admin/agents/${props.agent.id}/skills`)
  skills.value = data.result || []
}

function editSkill(skill) {
  editingSkill.value = skill
  skillForm.name = skill.name
  skillForm.description = skill.description || ''
  skillForm.content = skill.content || ''
}

function closeSkillModal() {
  showAddSkill.value = false
  editingSkill.value = null
  skillForm.name = ''
  skillForm.description = ''
  skillForm.content = ''
}

async function saveSkill() {
  if (!skillForm.name.trim()) return
  if (editingSkill.value) {
    await api('PUT', `/admin/skills/${editingSkill.value.id}`, {
      name: skillForm.name.trim(),
      description: skillForm.description.trim(),
      content: skillForm.content,
    })
  } else {
    await api('POST', `/admin/agents/${props.agent.id}/skills`, {
      name: skillForm.name.trim(),
      description: skillForm.description.trim(),
      content: skillForm.content,
    })
  }
  closeSkillModal()
  loadSkills()
}

async function removeSkill(skill) {
  if (!confirm(`确定删除技能「${skill.name}」？`)) return
  await api('DELETE', `/admin/skills/${skill.id}`)
  loadSkills()
}

function downloadSkill(skill) {
  const blob = new Blob([skill.content || ''], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${skill.name}.md`
  a.click()
  URL.revokeObjectURL(url)
}

function triggerUpload() {
  skillFileInput.value?.click()
}

async function onSkillFileUpload(e) {
  const file = e.target.files[0]
  if (!file) return
  const text = await file.text()
  const name = file.name.replace(/\.(md|txt|json|yaml|yml)$/, '')
  await api('POST', `/admin/agents/${props.agent.id}/skills`, {
    name,
    description: `从文件 ${file.name} 导入`,
    content: text,
    file_type: file.name.split('.').pop() || 'text',
  })
  loadSkills()
  e.target.value = ''
}

async function loadModels() {
  const data = await api('GET', '/admin/models')
  models.value = data.result || []
}

function onModelsClose() {
  showModels.value = false
  loadModels()
}

onMounted(() => {
  loadModels()
  loadSkills()
})
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

/* Section head with action */
.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.section-head h4 { margin: 0; }

/* Skills list */
.skills-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
}
.skill-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  transition: border-color 0.15s ease;
}
.skill-item:hover { border-color: var(--accent); }
.skill-info { flex: 1; min-width: 0; }
.skill-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
  display: block;
}
.skill-desc {
  font-size: 11px;
  color: var(--text-dim);
  display: block;
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.skill-actions {
  display: flex;
  gap: 4px;
  flex-shrink: 0;
  margin-left: 8px;
}
.skill-action-btn {
  width: 28px; height: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface2);
  color: var(--text-dim);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s ease;
}
.skill-action-btn:hover { border-color: var(--accent); color: var(--accent); }
.skill-action-btn.danger:hover { border-color: var(--danger); color: var(--danger); }

.skill-upload-row {
  margin-top: 8px;
}

/* Skill modal */
.skill-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 20px;
}
.skill-modal {
  background: var(--bg);
  border-radius: var(--radius-lg, 16px);
  width: 100%;
  max-width: 560px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg, 0 20px 60px rgba(0,0,0,0.3));
}
.skill-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
}
.skill-modal-header h4 { margin: 0; font-size: 15px; font-weight: 700; }
.skill-modal-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}
.skill-modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid var(--border);
}
.skill-content-textarea {
  width: 100%;
  min-height: 200px;
  padding: 12px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  background: var(--surface);
  color: var(--text);
  resize: vertical;
  line-height: 1.5;
}
.skill-content-textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--shadow-glow);
}

.wf-field { margin-bottom: 14px; }
.wf-field label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-dim);
  margin-bottom: 6px;
}
.wf-field input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
}
.wf-field input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--shadow-glow);
}
.wf-close {
  background: none; border: none; font-size: 22px; color: var(--text-dim); cursor: pointer;
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
}
.wf-close:hover { background: var(--surface2); color: var(--text); }
.btn-cancel {
  padding: 8px 18px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text-2);
  font-size: 14px;
  cursor: pointer;
}
.btn-cancel:hover { background: var(--surface2); }
.btn-save {
  padding: 8px 18px;
  border: none;
  border-radius: var(--radius);
  background: var(--accent);
  color: white;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.15s ease;
}
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-save:not(:disabled):hover { opacity: 0.9; }
</style>

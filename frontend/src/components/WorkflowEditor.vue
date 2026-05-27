<template>
  <div class="wf-overlay" @click.self="$emit('close')">
    <div class="wf-modal">
      <div class="wf-header">
        <h3>{{ isEditing ? '编辑工作流' : '创建工作流' }}</h3>
        <button class="wf-close" @click="$emit('close')">×</button>
      </div>

      <div class="wf-body">
        <div class="wf-field">
          <label>名称</label>
          <input v-model="form.name" placeholder="例如：每周复盘" />
        </div>

        <div class="wf-field">
          <label>描述</label>
          <textarea v-model="form.description" placeholder="这个工作流做什么？" rows="2"></textarea>
        </div>

        <div class="wf-field">
          <label>触发方式</label>
          <select v-model="form.trigger_type">
            <option value="manual">手动触发</option>
            <option value="schedule">定时触发</option>
          </select>
        </div>

        <!-- Schedule config -->
        <div v-if="form.trigger_type === 'schedule'" class="wf-field">
          <label>定时配置</label>
          <div class="schedule-config">
            <select v-model="scheduleType" class="schedule-select">
              <option value="minutes">每N分钟</option>
              <option value="interval">每N小时</option>
              <option value="daily">每天</option>
              <option value="weekly">每周</option>
              <option value="cron">Cron 表达式</option>
            </select>

            <div v-if="scheduleType === 'minutes'" class="schedule-row">
              <span>每</span>
              <input type="number" v-model.number="scheduleMinutes" min="1" max="59" class="schedule-num" />
              <span>分钟执行一次</span>
            </div>

            <div v-if="scheduleType === 'interval'" class="schedule-row">
              <span>每</span>
              <input type="number" v-model.number="scheduleInterval" min="1" max="24" class="schedule-num" />
              <span>小时执行一次</span>
            </div>

            <div v-if="scheduleType === 'daily'" class="schedule-row">
              <span>每天</span>
              <input type="time" v-model="scheduleDailyTime" class="schedule-time" />
              <span>执行</span>
            </div>

            <div v-if="scheduleType === 'weekly'" class="schedule-row">
              <span>每周</span>
              <select v-model.number="scheduleWeeklyDay" class="schedule-day">
                <option :value="0">周日</option>
                <option :value="1">周一</option>
                <option :value="2">周二</option>
                <option :value="3">周三</option>
                <option :value="4">周四</option>
                <option :value="5">周五</option>
                <option :value="6">周六</option>
              </select>
              <input type="time" v-model="scheduleWeeklyTime" class="schedule-time" />
              <span>执行</span>
            </div>

            <div v-if="scheduleType === 'cron'" class="schedule-row">
              <input type="text" v-model="scheduleCron" placeholder="*/30 * * * *" class="schedule-cron" />
            </div>
            <div v-if="scheduleType === 'cron'" class="schedule-hint">
              格式: 分 时 日 月 周 (例: <code>0 9 * * 1-5</code> = 工作日9点)
            </div>
          </div>
        </div>

        <div class="wf-field">
          <label>步骤</label>
          <div class="wf-steps">
            <div v-for="(step, idx) in form.steps" :key="idx" class="wf-step">
              <div class="step-num">{{ idx + 1 }}</div>
              <div class="step-body">
                <select v-model="step.agent_id" class="step-agent">
                  <option value="">选择智能体</option>
                  <option v-for="a in availableAgents" :key="a.id" :value="a.id">{{ a.name }} {{ a.status === 'online' ? '🟢' : '🔴' }}</option>
                </select>
                <div class="step-prompt-wrap">
                  <textarea v-model="step.prompt" placeholder="指令内容..." rows="2" class="step-prompt"></textarea>
                  <div class="step-prompt-actions">
                    <button class="prompt-action-btn" @click="openExpandEditor(idx)" title="展开编辑">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
                    </button>
                    <button class="prompt-action-btn var-btn" @click="toggleVarMenu(idx)" title="插入变量">
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><text x="4" y="18" font-size="16" font-family="serif" font-style="italic" fill="currentColor" stroke="none">ƒx</text></svg>
                    </button>
                  </div>
                  <!-- Variable dropdown -->
                  <div v-if="varMenuIdx === idx" class="var-dropdown">
                    <div class="var-dropdown-header">插入变量</div>
                    <div v-if="idx === 0" class="var-dropdown-empty">第一步无可用变量</div>
                    <template v-else>
                      <div v-for="(prevStep, pi) in form.steps.slice(0, idx)" :key="pi"
                           class="var-dropdown-item"
                           @click="insertVar(idx, pi)">
                        <span class="var-tag" v-text="varLabel(pi)"></span>
                        <span class="var-desc">步骤{{ pi+1 }} {{ getAgentName(prevStep.agent_id) }} 的回复</span>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
              <button class="step-remove" @click="removeStep(idx)" title="删除步骤">×</button>
            </div>
          </div>
          <button class="btn-add-step" @click="addStep">+ 添加步骤</button>
        </div>
      </div>

      <div class="wf-footer">
        <button class="btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn-save" :disabled="!canSave" @click="save">保存</button>
      </div>
    </div>
  </div>

  <!-- Expand editor modal -->
  <Teleport to="body">
    <div v-if="expandIdx !== null" class="expand-overlay" @click.self="closeExpandEditor">
      <div class="expand-modal">
        <div class="expand-header">
          <h4>步骤 {{ expandIdx + 1 }} — 指令编辑</h4>
          <div class="expand-header-actions">
            <button class="prompt-action-btn var-btn" @click="toggleExpandVarMenu" title="插入变量">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><text x="4" y="18" font-size="16" font-family="serif" font-style="italic" fill="currentColor" stroke="none">ƒx</text></svg>
            </button>
            <button class="expand-close" @click="closeExpandEditor">×</button>
          </div>
          <!-- Variable dropdown in expand mode -->
          <div v-if="showExpandVarMenu" class="var-dropdown expand-var-dropdown">
            <div class="var-dropdown-header">插入变量</div>
            <div v-if="expandIdx === 0" class="var-dropdown-empty">第一步无可用变量</div>
            <template v-else>
              <div v-for="(prevStep, pi) in form.steps.slice(0, expandIdx)" :key="pi"
                   class="var-dropdown-item"
                   @click="insertVarExpand(pi)">
                <span class="var-tag" v-text="varLabel(pi)"></span>
                <span class="var-desc">步骤{{ pi+1 }} {{ getAgentName(prevStep.agent_id) }} 的回复</span>
              </div>
            </template>
          </div>
        </div>
        <textarea
          ref="expandTextarea"
          v-model="form.steps[expandIdx].prompt"
          class="expand-textarea"
          placeholder="在此编辑详细指令内容..."
        ></textarea>
        <div class="expand-footer">
          <span class="expand-hint">支持 &#123;&#123;stepN.reply&#125;&#125; 引用上一步结果</span>
          <button class="btn-save" @click="closeExpandEditor">完成</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
<script setup>
import { ref, reactive, computed, onMounted, watch, nextTick } from 'vue'
import { api, store } from '../store.js'

const props = defineProps({ room: Object, workflow: Object })
const emit = defineEmits(['close', 'saved'])

const isEditing = computed(() => !!props.workflow)
const agents = computed(() => store.agents.filter(a => a.id !== 'user' && a.id !== 'system'))
const roomMembers = ref([])

// Available agents: prefer room members if room is provided, else all agents
const availableAgents = computed(() => {
  if (roomMembers.value.length > 0) {
    return roomMembers.value
  }
  return agents.value
})

const form = reactive({
  name: '',
  description: '',
  trigger_type: 'manual',
  steps: [{ agent_id: '', prompt: '', wait_for_reply: true }]
})

// Schedule config state
const scheduleType = ref('minutes')
const scheduleMinutes = ref(5)
const scheduleInterval = ref(4)
const scheduleDailyTime = ref('09:00')
const scheduleWeeklyDay = ref(1)
const scheduleWeeklyTime = ref('09:00')
const scheduleCron = ref('')

// Expand editor state
const expandIdx = ref(null)
const expandTextarea = ref(null)
const showExpandVarMenu = ref(false)

// Variable menu state
const varMenuIdx = ref(null)

function getAgentName(agentId) {
  const a = availableAgents.value.find(x => x.id === agentId) || agents.value.find(x => x.id === agentId)
  return a ? a.name : '未选择'
}

function varLabel(pi) {
  return `{{step${pi + 1}.reply}}`
}

function openExpandEditor(idx) {
  expandIdx.value = idx
  showExpandVarMenu.value = false
  nextTick(() => {
    if (expandTextarea.value) expandTextarea.value.focus()
  })
}

function closeExpandEditor() {
  expandIdx.value = null
  showExpandVarMenu.value = false
}

function toggleVarMenu(idx) {
  varMenuIdx.value = varMenuIdx.value === idx ? null : idx
}

function toggleExpandVarMenu() {
  showExpandVarMenu.value = !showExpandVarMenu.value
}

function insertVar(stepIdx, prevIdx) {
  const varStr = `{{step${prevIdx + 1}.reply}}`
  form.steps[stepIdx].prompt += varStr
  varMenuIdx.value = null
}

function insertVarExpand(prevIdx) {
  const varStr = `{{step${prevIdx + 1}.reply}}`
  if (expandIdx.value !== null) {
    form.steps[expandIdx.value].prompt += varStr
  }
  showExpandVarMenu.value = false
}

// Close var menu on outside click
function onBodyClick(e) {
  if (!e.target.closest('.var-dropdown') && !e.target.closest('.var-btn')) {
    varMenuIdx.value = null
    showExpandVarMenu.value = false
  }
}
onMounted(() => document.addEventListener('click', onBodyClick))

// Pre-fill form when editing
onMounted(async () => {
  // Load room members if room is provided
  if (props.room?.id) {
    try {
      const data = await api('GET', `/admin/rooms/${props.room.id}/members`)
      if (Array.isArray(data)) {
        roomMembers.value = data.filter(m => m.id !== 'user' && m.id !== 'system')
      }
    } catch {}
  }

  if (props.workflow) {
    form.name = props.workflow.name || ''
    form.description = props.workflow.description || ''
    form.trigger_type = props.workflow.trigger_type || 'manual'
    try {
      const steps = typeof props.workflow.steps_json === 'string'
        ? JSON.parse(props.workflow.steps_json)
        : props.workflow.steps_json
      if (Array.isArray(steps) && steps.length > 0) {
        form.steps = steps.map(s => ({ ...s }))
      }
    } catch {}
    // Parse trigger_config
    if (form.trigger_type === 'schedule') {
      try {
        const config = typeof props.workflow.trigger_config === 'string'
          ? JSON.parse(props.workflow.trigger_config || '{}')
          : (props.workflow.trigger_config || {})
        if (config.cron) {
          scheduleType.value = 'cron'
          scheduleCron.value = config.cron
        } else if (config.interval_minutes) {
          scheduleType.value = 'minutes'
          scheduleMinutes.value = config.interval_minutes
        } else if (config.interval_hours) {
          scheduleType.value = 'interval'
          scheduleInterval.value = config.interval_hours
        } else if (config.daily_time) {
          scheduleType.value = 'daily'
          scheduleDailyTime.value = config.daily_time
        } else if (config.weekly_day !== undefined) {
          scheduleType.value = 'weekly'
          scheduleWeeklyDay.value = config.weekly_day
          scheduleWeeklyTime.value = config.weekly_time || '09:00'
        }
      } catch {}
    }
  }
})

const canSave = computed(() => {
  return form.name.trim() && form.steps.length > 0 && form.steps.every(s => s.agent_id && s.prompt.trim())
})

function addStep() {
  form.steps.push({ agent_id: '', prompt: '', wait_for_reply: true })
}

function removeStep(idx) {
  if (form.steps.length <= 1) return
  form.steps.splice(idx, 1)
}

function buildTriggerConfig() {
  if (form.trigger_type !== 'schedule') return '{}'
  if (scheduleType.value === 'minutes') {
    return JSON.stringify({ interval_minutes: scheduleMinutes.value })
  } else if (scheduleType.value === 'cron') {
    return JSON.stringify({ cron: scheduleCron.value.trim() })
  } else if (scheduleType.value === 'interval') {
    return JSON.stringify({ interval_hours: scheduleInterval.value })
  } else if (scheduleType.value === 'daily') {
    return JSON.stringify({ daily_time: scheduleDailyTime.value })
  } else if (scheduleType.value === 'weekly') {
    return JSON.stringify({ weekly_day: scheduleWeeklyDay.value, weekly_time: scheduleWeeklyTime.value })
  }
  return '{}'
}

async function save() {
  if (!canSave.value) return
  const payload = {
    name: form.name.trim(),
    description: form.description.trim(),
    steps_json: form.steps,
    trigger_type: form.trigger_type,
    trigger_config: buildTriggerConfig()
  }

  let data
  if (isEditing.value) {
    data = await api('PUT', `/admin/workflows/${props.workflow.id}`, payload)
  } else {
    data = await api('POST', `/admin/rooms/${props.room.id}/workflows`, payload)
  }
  if (data.ok || data.ok === undefined) {
    emit('saved')
  }
}
</script>
<style scoped>
.wf-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
}
.wf-modal {
  background: var(--bg);
  border-radius: var(--radius-lg, 16px);
  width: 100%;
  max-width: 580px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg, 0 20px 60px rgba(0,0,0,0.3));
}
.wf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.wf-header h3 { margin: 0; font-size: 16px; font-weight: 700; }
.wf-close {
  background: none; border: none; font-size: 22px; color: var(--text-dim); cursor: pointer;
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
}
.wf-close:hover { background: var(--surface2); color: var(--text); }

.wf-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.wf-field { margin-bottom: 18px; }
.wf-field label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-dim);
  margin-bottom: 6px;
}
.wf-field input,
.wf-field textarea,
.wf-field select {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
}
.wf-field input:focus,
.wf-field textarea:focus,
.wf-field select:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: var(--shadow-glow);
}

/* Schedule config */
.schedule-config {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}
.schedule-select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface2);
  color: var(--text);
}
.schedule-select:focus { outline: none; border-color: var(--accent); }
.schedule-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-2);
}
.schedule-num {
  width: 60px;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface2);
  color: var(--text);
  text-align: center;
}
.schedule-num:focus { outline: none; border-color: var(--accent); }
.schedule-time {
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface2);
  color: var(--text);
}
.schedule-time:focus { outline: none; border-color: var(--accent); }
.schedule-day {
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface2);
  color: var(--text);
}
.schedule-day:focus { outline: none; border-color: var(--accent); }
.schedule-cron {
  flex: 1;
  padding: 6px 10px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  background: var(--surface2);
  color: var(--text);
}
.schedule-cron:focus { outline: none; border-color: var(--accent); }
.schedule-hint {
  font-size: 11px;
  color: var(--text-dim);
  line-height: 1.4;
}
.schedule-hint code {
  background: var(--surface2);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 11px;
}

.wf-steps {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 10px;
}
.wf-step {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
}
.step-num {
  width: 24px; height: 24px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent);
  font-size: 12px;
  font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
  margin-top: 4px;
}
.step-body { flex: 1; display: flex; flex-direction: column; gap: 8px; }
.step-agent {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  background: var(--surface2);
  color: var(--text);
}

/* Prompt wrap with action buttons */
.step-prompt-wrap {
  position: relative;
}
.step-prompt {
  width: 100%;
  padding: 8px 12px;
  padding-right: 64px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
  background: var(--surface2);
  color: var(--text);
  resize: vertical;
  min-height: 48px;
}
.step-agent:focus, .step-prompt:focus { outline: none; border-color: var(--accent); }

.step-prompt-actions {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 4px;
}
.prompt-action-btn {
  width: 26px; height: 26px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text-dim);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s ease;
}
.prompt-action-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-soft);
}

/* Variable dropdown */
.var-dropdown {
  position: absolute;
  top: 100%;
  right: 0;
  margin-top: 4px;
  min-width: 240px;
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow-lg, 0 8px 24px rgba(0,0,0,0.15));
  z-index: 1100;
  overflow: hidden;
}
.var-dropdown-header {
  padding: 8px 12px;
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--text-dim);
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.var-dropdown-empty {
  padding: 12px;
  font-size: 12px;
  color: var(--text-dim);
  text-align: center;
}
.var-dropdown-item {
  padding: 10px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: background 0.1s ease;
}
.var-dropdown-item:hover {
  background: var(--accent-soft);
}
.var-tag {
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  background: var(--surface2);
  border: 1px solid var(--border);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--accent);
  font-weight: 600;
  white-space: nowrap;
}
.var-desc {
  font-size: 12px;
  color: var(--text-2);
}

.step-remove {
  background: none; border: none; color: var(--text-dim); font-size: 18px; cursor: pointer;
  width: 24px; height: 24px; display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm); flex-shrink: 0;
}
.step-remove:hover { background: var(--danger-soft); color: var(--danger); }

.btn-add-step {
  width: 100%;
  padding: 8px;
  border: 1px dashed var(--border);
  border-radius: var(--radius);
  background: transparent;
  color: var(--text-dim);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s ease;
}
.btn-add-step:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-soft); }

.wf-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}
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

/* Expand editor modal */
.expand-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 24px;
}
.expand-modal {
  background: var(--bg);
  border-radius: var(--radius-lg, 16px);
  width: 100%;
  max-width: 720px;
  height: 70vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg, 0 20px 60px rgba(0,0,0,0.3));
}
.expand-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border);
  position: relative;
}
.expand-header h4 { margin: 0; font-size: 15px; font-weight: 700; }
.expand-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}
.expand-close {
  background: none; border: none; font-size: 22px; color: var(--text-dim); cursor: pointer;
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  border-radius: var(--radius-sm);
}
.expand-close:hover { background: var(--surface2); color: var(--text); }
.expand-textarea {
  flex: 1;
  width: 100%;
  padding: 16px 20px;
  border: none;
  font-size: 14px;
  font-family: inherit;
  background: var(--surface);
  color: var(--text);
  resize: none;
  line-height: 1.6;
}
.expand-textarea:focus { outline: none; }
.expand-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
}
.expand-hint {
  font-size: 12px;
  color: var(--text-dim);
  font-family: 'SF Mono', 'Fira Code', monospace;
}
.expand-var-dropdown {
  position: absolute;
  top: 100%;
  right: 50px;
}
</style>

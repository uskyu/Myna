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
              <option value="interval">每N小时</option>
              <option value="daily">每天</option>
              <option value="weekly">每周</option>
              <option value="cron">Cron 表达式</option>
            </select>

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
                  <option v-for="a in agents" :key="a.id" :value="a.id">{{ a.name }}</option>
                </select>
                <textarea v-model="step.prompt" placeholder="指令内容..." rows="2" class="step-prompt"></textarea>
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
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { api, store } from '../store.js'

const props = defineProps({ room: Object, workflow: Object })
const emit = defineEmits(['close', 'saved'])

const isEditing = computed(() => !!props.workflow)
const agents = computed(() => store.agents.filter(a => a.id !== 'user' && a.id !== 'system'))

const form = reactive({
  name: '',
  description: '',
  trigger_type: 'manual',
  steps: [{ agent_id: '', prompt: '', wait_for_reply: true }]
})

// Schedule config state
const scheduleType = ref('interval')
const scheduleInterval = ref(4)
const scheduleDailyTime = ref('09:00')
const scheduleWeeklyDay = ref(1)
const scheduleWeeklyTime = ref('09:00')
const scheduleCron = ref('')

// Pre-fill form when editing
onMounted(() => {
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
  if (scheduleType.value === 'cron') {
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
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}
.wf-modal {
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 520px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.3);
}
.wf-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
}
.wf-header h3 { margin: 0; font-size: 16px; font-weight: 700; color: var(--text); }
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
.wf-field {
  margin-bottom: 16px;
}
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
.step-prompt {
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px;
  font-family: inherit;
  background: var(--surface2);
  color: var(--text);
  resize: vertical;
}
.step-agent:focus, .step-prompt:focus { outline: none; border-color: var(--accent); }
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
</style>

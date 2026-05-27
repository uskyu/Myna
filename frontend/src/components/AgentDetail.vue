<template>
  <div class="agent-detail active">
    <div class="chat-header">
      <button class="back-btn" @click="$emit('close')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <span class="title">{{ agent.name }}</span>
      <button class="back-btn" style="margin-left:auto" @click="editing = !editing">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
      </button>
    </div>
    <div class="agent-detail-content">
      <div style="text-align:center;margin-bottom:20px">
        <div class="avatar-large" :style="{ background: getAgentColor(idx) }">
          <span v-html="getAgentIcon(idx)"></span>
        </div>
        <div style="font-size:20px;font-weight:600;margin-top:8px">{{ agent.name }}</div>
        <div style="font-size:14px;color:var(--text-dim);margin-top:4px">{{ agent.description || '通用智能体' }}</div>
        <div style="font-size:13px;margin-top:8px;display:flex;align-items:center;justify-content:center;gap:6px">
          <span class="dot" :class="agent.status === 'online' ? 'online' : 'offline'" style="width:8px;height:8px;border-radius:50%;display:inline-block"></span>
          {{ agent.status === 'online' ? '在线' : '离线' }}
        </div>
      </div>

      <div v-if="editing">
        <div class="field">
          <label>名称</label>
          <input v-model="form.name" type="text">
        </div>
        <div class="field">
          <label>描述 / 系统提示词</label>
          <textarea v-model="form.description" placeholder="定义智能体的角色和行为..."></textarea>
        </div>
        <div class="field">
          <label>关联模型</label>
          <select v-model="form.model_config_id" style="width:100%;padding:12px 14px;border:1px solid var(--border);border-radius:10px;font-size:15px;background:var(--surface);color:var(--text)">
            <option value="">使用默认配置</option>
            <option v-for="m in models" :key="m.id" :value="m.id">{{ m.name }} ({{ m.model }})</option>
          </select>
        </div>
        <div class="field">
          <label>状态</label>
          <div style="display:flex;align-items:center;gap:12px">
            <div class="toggle" :class="{ on: form.status === 'online' }" @click="form.status = form.status === 'online' ? 'offline' : 'online'"></div>
            <span>{{ form.status === 'online' ? '在线' : '离线' }}</span>
          </div>
        </div>
        <button class="btn btn-primary" @click="save" style="width:100%;margin-top:8px">保存修改</button>
      </div>

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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api, getAgentColor, getAgentIcon, store } from '../store.js'

const props = defineProps({ agent: Object })
const emit = defineEmits(['close', 'delete'])

const editing = ref(false)
const models = ref([])
const form = reactive({
  name: props.agent.name,
  description: props.agent.description || '',
  model_config_id: props.agent.model_config_id || '',
  status: props.agent.status || 'online',
})

const idx = store.agents.findIndex(a => a.id === props.agent.id)

async function save() {
  await api('PUT', `/admin/agents/${props.agent.id}`, form)
  editing.value = false
  // Update local
  Object.assign(props.agent, form)
}

onMounted(async () => {
  const data = await api('GET', '/admin/models')
  models.value = data.result || []
})
</script>

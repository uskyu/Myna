<template>
  <div class="page active">
    <div class="header">
      <h1>智能体</h1>
      <div class="actions">
        <button @click="$emit('create-agent')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
      </div>
    </div>
    <div class="search-bar">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="text" v-model="filter" placeholder="搜索智能体...">
    </div>
    <div class="agent-grid list-view">
      <div v-for="a in filtered" :key="a.id" class="agent-card" :class="{ 'system-agent': a.id === '__system__', selected: a.id === selectedId }" @click="$emit('open-detail', a)">
        <div class="avatar-wrap">
          <div class="agent-avatar" :style="{ background: getAgentColor(agentIndex(a.id)) }">
            <span v-html="getAgentIcon(agentIndex(a.id))"></span>
          </div>
          <span class="status-dot" :class="a.status === 'online' ? 'online' : 'offline'"></span>
        </div>
        <div class="info-block">
          <div class="agent-name">
            {{ a.name }}
            <span v-if="a.id === '__system__'" class="sys-badge">系统</span>
          </div>
          <div class="agent-desc">{{ a.description || '通用智能体' }}</div>
        </div>
        <button class="btn-dm" @click.stop="startDM(a.id)" title="发消息">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        </button>
      </div>
    </div>
    <div v-if="!filtered.length" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>
      <p>{{ filter ? '没有匹配的智能体' : '还没有智能体' }}</p>
      <p>点击右上角 + 创建</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { store, loadAgents, api, getAgentColor, getAgentIcon } from '../store.js'

defineProps({ selectedId: String })

const emit = defineEmits(['open-detail', 'create-agent'])
const filter = ref('')
const sort = ref(localStorage.getItem('hub-agent-sort') || 'name')

watch(sort, (v) => localStorage.setItem('hub-agent-sort', v))

const agentIndex = (id) => store.agents.findIndex(a => a.id === id)

const filtered = computed(() => {
  let list = [...store.agents].filter(a => a.id !== 'user' && a.id !== 'system')
  if (filter.value) {
    const q = filter.value.toLowerCase()
    list = list.filter(a => (a.name || '').toLowerCase().includes(q) || (a.description || '').toLowerCase().includes(q))
  }
  if (sort.value === 'name') list.sort((a, b) => a.name.localeCompare(b.name))
  else if (sort.value === 'status') list.sort((a, b) => (a.status === 'online' ? -1 : 1) - (b.status === 'online' ? -1 : 1))
  else if (sort.value === 'newest') list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  // Pin __system__ to top
  const sysIdx = list.findIndex(a => a.id === '__system__')
  if (sysIdx > 0) {
    const [sys] = list.splice(sysIdx, 1)
    list.unshift(sys)
  }
  return list
})

async function startDM(agentId) {
  const data = await api('POST', `/admin/dm/${agentId}`)
  if (data.ok) {
    window.location.reload()
  }
}

onMounted(loadAgents)
</script>

<style scoped>
.agent-grid.list-view .agent-card {
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s;
}

.agent-grid.list-view .agent-card:hover {
  background: var(--surface2);
  border-color: var(--border-strong);
}

.agent-grid.list-view .agent-card.selected {
  background: var(--accent-soft);
  border-color: rgba(45, 106, 79, 0.28);
}

.avatar-wrap {
  position: relative;
  width: 44px;
  height: 44px;
}

.agent-avatar {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  color: #fff;
}

.status-dot {
  position: absolute;
  bottom: 1px;
  right: 1px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  border: 1.5px solid var(--surface);
  box-sizing: content-box;
}

.status-dot.online {
  background: #4ade80;
}

.status-dot.offline {
  background: #6b7280;
}

.info-block {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
}

.agent-desc {
  font-size: 12px;
  color: var(--text-2);
  line-height: 1.3;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.btn-dm {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: none;
  background: var(--surface);
  color: var(--text-dim);
  border: 1px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background 0.15s, color 0.15s;
  flex-shrink: 0;
}

.btn-dm:hover {
  background: var(--accent-soft);
  color: var(--accent);
  border-color: var(--accent);
}

/* System agent styling */
.agent-card.system-agent {
  border-left: 3px solid var(--accent, #2d6a4f);
  background: rgba(45, 106, 79, 0.04);
}
.sys-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: var(--accent-soft, rgba(45, 106, 79, 0.12));
  color: var(--accent, #2d6a4f);
  margin-left: 6px;
  vertical-align: middle;
}

@media (min-width: 768px) {
  .agent-grid.list-view {
    padding: 14px;
    gap: 8px;
  }

  .agent-grid.list-view .agent-card {
    grid-template-columns: 48px 1fr auto;
    gap: 12px;
    padding: 12px 14px;
    min-height: 72px;
    border-radius: var(--radius);
  }

  .avatar-wrap,
  .agent-avatar {
    width: 48px;
    height: 48px;
  }

  .agent-name {
    font-size: 15px;
  }

  .agent-desc {
    font-size: 13px;
    -webkit-line-clamp: 2;
  }

  .btn-dm {
    width: 34px;
    height: 34px;
    border-radius: var(--radius-sm);
  }
}
</style>

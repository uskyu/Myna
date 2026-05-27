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
    <div class="sort-bar">
      <div class="sort-controls">
        <select v-model="sort">
          <option value="name">名称排序</option>
          <option value="status">状态排序</option>
          <option value="newest">最新创建</option>
        </select>
      </div>
    </div>
    <div class="agent-grid list-view">
      <div v-for="a in filtered" :key="a.id" class="agent-card" @click="$emit('open-detail', a)">
        <div class="agent-avatar" :style="{ background: getAgentColor(agentIndex(a.id)) }">
          <span v-html="getAgentIcon(agentIndex(a.id))"></span>
        </div>
        <div class="info-block">
          <div class="agent-name">{{ a.name }}</div>
          <div class="agent-desc">{{ a.description || '通用智能体' }}</div>
        </div>
        <div class="agent-status">
          <span class="dot" :class="a.status === 'online' ? 'online' : 'offline'"></span>
          {{ a.status === 'online' ? '在线' : '离线' }}
        </div>
        <div class="card-actions">
          <button class="btn-chat" @click.stop="startDM(a.id)">发消息</button>
        </div>
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

const emit = defineEmits(['open-detail', 'create-agent'])
const filter = ref('')
const sort = ref(localStorage.getItem('hub-agent-sort') || 'name')

watch(sort, (v) => localStorage.setItem('hub-agent-sort', v))

const agentIndex = (id) => store.agents.findIndex(a => a.id === id)

const filtered = computed(() => {
  let list = [...store.agents]
  if (filter.value) {
    const q = filter.value.toLowerCase()
    list = list.filter(a => (a.name || '').toLowerCase().includes(q) || (a.description || '').toLowerCase().includes(q))
  }
  if (sort.value === 'name') list.sort((a, b) => a.name.localeCompare(b.name))
  else if (sort.value === 'status') list.sort((a, b) => (a.status === 'online' ? -1 : 1) - (b.status === 'online' ? -1 : 1))
  else if (sort.value === 'newest') list.sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
  return list
})

async function startDM(agentId) {
  const data = await api('POST', `/admin/dm/${agentId}`)
  if (data.ok) {
    // Navigate to chats and open DM
    window.location.reload() // Simple approach for now
  }
}

onMounted(loadAgents)
</script>

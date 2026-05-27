<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal members-modal">
      <div class="models-header">
        <h3>群成员</h3>
        <button class="close-x" @click="$emit('close')">×</button>
      </div>

      <div class="member-list">
        <div v-for="m in members" :key="m.id" class="member-row">
          <div class="member-avatar" :style="{ background: getAgentColor(agentColorIdx(m.id)) }">
            <span v-html="getAgentIcon(agentColorIdx(m.id))"></span>
          </div>
          <div class="member-info">
            <div class="member-name">{{ m.name }}</div>
            <div class="member-status">
              <span class="dot" :class="m.status === 'online' ? 'online' : 'offline'"></span>
              {{ m.status === 'online' ? '在线' : '离线' }}
            </div>
          </div>
          <button v-if="m.id !== 'user'" class="icon-btn danger" @click="removeMember(m)" title="移出群聊">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6L6 18M6 6l12 12"/></svg>
          </button>
        </div>
      </div>

      <div class="section-title-mini">添加智能体</div>
      <div class="member-list">
        <div v-if="!available.length" class="empty-mini" style="padding:14px">
          <p style="color:var(--text-dim);font-size:13px">所有可用智能体已加入</p>
        </div>
        <div v-for="a in available" :key="a.id" class="member-row" style="cursor:pointer" @click="addMember(a)">
          <div class="member-avatar" :style="{ background: getAgentColor(agentColorIdx(a.id)) }">
            <span v-html="getAgentIcon(agentColorIdx(a.id))"></span>
          </div>
          <div class="member-info">
            <div class="member-name">{{ a.name }}</div>
            <div class="member-status">
              <span class="dot" :class="a.status === 'online' ? 'online' : 'offline'"></span>
              {{ a.description || '通用智能体' }}
            </div>
          </div>
          <button class="icon-btn add">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14"/></svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api, store, getAgentColor, getAgentIcon, loadConversations } from '../store.js'

const props = defineProps({ room: Object })
const emit = defineEmits(['close', 'changed'])

const members = ref([])

async function load() {
  const data = await api('GET', '/admin/rooms')
  const room = (data.result || []).find(r => r.id === props.room.id)
  if (room) members.value = room.members || []
}

const available = computed(() => {
  const ids = new Set(members.value.map(m => m.id))
  return store.agents.filter(a => !ids.has(a.id))
})

const agentColorIdx = (id) => store.agents.findIndex(a => a.id === id)

async function addMember(a) {
  const res = await api('POST', `/admin/rooms/${props.room.id}/members`, { agent_id: a.id })
  if (res.ok || res.ok === undefined) {
    await load()
    await loadConversations()
    emit('changed')
  }
}

async function removeMember(m) {
  if (!confirm(`将「${m.name}」移出群聊？`)) return
  const res = await api('DELETE', `/admin/rooms/${props.room.id}/members/${m.id}`)
  if (res.ok || res.ok === undefined) {
    await load()
    await loadConversations()
    emit('changed')
  }
}

onMounted(load)
</script>

<style scoped>
.members-modal { max-width: 520px; max-height: 86vh; display: flex; flex-direction: column; }
.models-header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.models-header h3 { flex: 1; text-align: left; margin: 0; }
.close-x {
  background: transparent;
  border: 1px solid var(--border);
  width: 30px; height: 30px;
  border-radius: var(--radius-sm);
  font-size: 18px; line-height: 1;
  color: var(--text-dim);
  cursor: pointer;
}
.close-x:hover { background: var(--surface2); color: var(--text); }

.section-title-mini {
  font-size: 11px;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  margin: 16px 0 8px;
}

.member-list { overflow-y: auto; max-height: 30vh; }
.member-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 6px;
  background: var(--surface);
  transition: border-color 0.15s ease, background 0.15s ease;
}
.member-row:hover { background: var(--surface2); }

.member-avatar {
  width: 36px; height: 36px;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.member-avatar svg, .member-avatar span svg { width: 16px; height: 16px; color: white; }

.member-info { flex: 1; min-width: 0; }
.member-name { font-size: 14px; font-weight: 600; color: var(--text); }
.member-status { font-size: 12px; color: var(--text-dim); margin-top: 2px; display: flex; align-items: center; gap: 6px; }

.icon-btn {
  background: transparent; border: 1px solid var(--border);
  width: 32px; height: 32px;
  border-radius: var(--radius-sm);
  color: var(--text-2);
  cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
  transition: all 0.15s ease;
  flex-shrink: 0;
}
.icon-btn svg { width: 14px; height: 14px; }
.icon-btn.add:hover { color: var(--accent); border-color: var(--accent); background: var(--accent-soft); }
.icon-btn.danger:hover { color: var(--danger); border-color: var(--danger); background: var(--danger-soft); }

.empty-mini { text-align: center; }
.empty-mini p { margin: 0; }
</style>

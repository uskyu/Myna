<template>
  <div class="page active">
    <div class="header">
      <h1>消息</h1>
      <div class="actions">
        <button @click="$emit('create-room')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
      </div>
    </div>
    <!-- Tab navigation -->
    <div class="msg-tabs">
      <button class="msg-tab" :class="{ active: activeTab === 'group' }" @click="activeTab = 'group'">
        群聊
        <span v-if="groupUnread > 0" class="tab-badge">{{ groupUnread }}</span>
      </button>
      <button class="msg-tab" :class="{ active: activeTab === 'dm' }" @click="activeTab = 'dm'">
        私信
        <span v-if="dmUnread > 0" class="tab-badge">{{ dmUnread }}</span>
      </button>
    </div>
    <div class="sort-bar">
      <span class="sort-label">排序</span>
      <button
        v-for="option in sortOptions"
        :key="option.key"
        class="sort-btn"
        :class="{ active: sortBy === option.key }"
        @click="setSort(option.key)"
      >{{ option.label }}{{ sortBy === option.key ? (sortDesc ? ' ↓' : ' ↑') : '' }}</button>
    </div>
    <div class="chat-list">
      <!-- Group chats -->
      <template v-if="activeTab === 'group'">
        <div v-for="r in sortedRooms" :key="r.id" class="chat-item" @click="$emit('open-chat', r, 'group')">
          <div class="avatar" :style="{ background: getAgentColor(roomIndex(r.id) + 2) }">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
          <div class="info">
            <div class="name">{{ r.name }}</div>
            <div class="preview">{{ r.last_message ? r.last_message.sender_name + ': ' + r.last_message.text.slice(0, 30) : (r.members?.length || 0) + ' 个成员' }}</div>
          </div>
          <div class="meta">
            <span class="time">{{ r.last_message?.created_at?.slice(11, 16) || '' }}</span>
            <span v-if="store.unreadCounts[r.id] > 0" class="unread-badge">{{ store.unreadCounts[r.id] }}</span>
            <span v-else-if="isRoomActive(r.id)" class="active-badge"><span class="pulse-dot"></span>生成中</span>
          </div>
          <div class="item-actions" @click.stop>
            <button class="item-action-btn" @click.stop="startRename(r)" title="重命名">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button class="item-action-btn danger" @click.stop="deleteRoom(r)" title="删除">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
        <div v-if="!store.rooms.length" class="empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          <p>还没有群聊</p>
          <p>点击右上角 + 创建</p>
        </div>
      </template>
      <!-- DMs -->
      <template v-if="activeTab === 'dm'">
        <div v-for="dm in sortedDms" :key="dm.id" class="chat-item" @click="$emit('open-chat', dm, 'dm')">
          <div class="avatar round" :style="{ background: getAgentColor(agentIndex(dm.agent?.id)) }">
            <span v-html="getAgentIcon(agentIndex(dm.agent?.id))"></span>
          </div>
          <div class="info">
            <div class="name">{{ dm.agent?.name || '未知' }}</div>
            <div class="preview">{{ dm.last_message?.text?.slice(0, 30) || '开始对话' }}</div>
          </div>
          <div class="meta">
            <span class="time">{{ dm.last_message?.created_at?.slice(11, 16) || '' }}</span>
            <span v-if="store.unreadCounts[dm.id] > 0" class="unread-badge">{{ store.unreadCounts[dm.id] }}</span>
            <span v-else-if="isRoomActive(dm.id)" class="active-badge"><span class="pulse-dot"></span>生成中</span>
          </div>
          <div class="item-actions" @click.stop>
            <button class="item-action-btn danger" @click.stop="deleteRoom(dm)" title="删除">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            </button>
          </div>
        </div>
        <div v-if="!store.dms.length" class="empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <p>还没有私信</p>
          <p>在智能体列表中点击消息图标开始</p>
        </div>
      </template>
    </div>

    <!-- Rename modal -->
    <Teleport to="body">
      <div v-if="renamingRoom" class="rename-overlay" @click.self="renamingRoom = null">
        <div class="rename-modal">
          <h4>重命名对话</h4>
          <input v-model="renameText" @keydown.enter="confirmRename" placeholder="输入新名称" autofocus />
          <div class="rename-actions">
            <button class="btn-cancel" @click="renamingRoom = null">取消</button>
            <button class="btn-save" :disabled="!renameText.trim()" @click="confirmRename">确定</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { store, api, loadConversations, loadAgents, getAgentColor, getAgentIcon } from '../store.js'

defineEmits(['open-chat', 'create-room'])

const activeTab = ref('group')
const agentIndex = (id) => store.agents.findIndex(a => a.id === id)
const renamingRoom = ref(null)
const renameText = ref('')
const sortOptions = [
  { key: 'lastTime', label: '最后对话' },
  { key: 'name', label: '聊天框名' },
  { key: 'createdAt', label: '创建时间' },
]
const sortBy = ref(localStorage.getItem('chat_sort_by') || 'lastTime')
const sortDesc = ref(localStorage.getItem('chat_sort_desc') !== 'false')
const lastClickedSort = ref('')

function setSort(key) {
  if (lastClickedSort.value === key) {
    sortDesc.value = !sortDesc.value
  } else {
    sortBy.value = key
    sortDesc.value = false
    lastClickedSort.value = key
  }
  localStorage.setItem('chat_sort_by', sortBy.value)
  localStorage.setItem('chat_sort_desc', String(sortDesc.value))
}

const groupUnread = computed(() => {
  return store.rooms.reduce((sum, r) => sum + (store.unreadCounts[r.id] || 0), 0)
})
const dmUnread = computed(() => {
  return store.dms.reduce((sum, dm) => sum + (store.unreadCounts[dm.id] || 0), 0)
})

const sortedRooms = computed(() => sortConversations(store.rooms))
const sortedDms = computed(() => sortConversations(store.dms))

function sortConversations(items) {
  return [...items].sort((a, b) => {
    const prominentA = (store.unreadCounts[a.id] || 0) > 0 || isRoomActive(a.id)
    const prominentB = (store.unreadCounts[b.id] || 0) > 0 || isRoomActive(b.id)
    if (prominentA !== prominentB) return prominentA ? -1 : 1

    let result
    if (sortBy.value === 'name') {
      result = String(a.name || a.agent?.name || '').localeCompare(String(b.name || b.agent?.name || ''), 'zh-CN')
    } else if (sortBy.value === 'createdAt') {
      result = conversationCreateTime(a) - conversationCreateTime(b)
    } else {
      result = conversationTime(a) - conversationTime(b)
    }

    if (result === 0) {
      result = String(a.name || a.agent?.name || '').localeCompare(String(b.name || b.agent?.name || ''), 'zh-CN')
    }
    return sortDesc.value ? -result : result
  })
}

function conversationCreateTime(item) {
  return parseTimestamp(item.created_at)
}

function conversationTime(item) {
  for (const ts of [item.last_message?.created_at, item.updated_at, item.created_at]) {
    const parsed = parseTimestamp(ts)
    if (parsed) return parsed
  }
  return 0
}

function parseTimestamp(ts) {
  if (!ts) return 0
  if (typeof ts === 'number') return ts
  const value = String(ts)
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
  const normalized = value.replace(' ', 'T') + (hasZone ? '' : 'Z')
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? 0 : d.getTime()
}

function roomIndex(roomId) {
  return store.rooms.findIndex(r => r.id === roomId)
}

function isRoomActive(roomId) {
  return Object.values(store.activeStreams).some(s => s.roomId === roomId)
}

function startRename(room) {
  renamingRoom.value = room
  renameText.value = room.name || ''
}

async function confirmRename() {
  if (!renameText.value.trim() || !renamingRoom.value) return
  await api('PUT', `/admin/rooms/${renamingRoom.value.id}`, { name: renameText.value.trim() })
  renamingRoom.value.name = renameText.value.trim()
  renamingRoom.value = null
}

async function deleteRoom(room) {
  const name = room.name || room.agent?.name || '此对话'
  if (!confirm(`确定删除「${name}」？消息将被清除。`)) return
  await api('DELETE', `/admin/rooms/${room.id}`)
  loadConversations()
}

let timer
onMounted(() => {
  loadConversations()
  loadAgents()
  timer = setInterval(loadConversations, 5000)
})
onUnmounted(() => clearInterval(timer))
</script>

<style scoped>
/* Tab navigation */
.msg-tabs {
  display: flex;
  padding: 0 16px;
  gap: 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
}
.msg-tab {
  flex: 1;
  padding: 10px 0;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-dim);
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
  text-align: center;
  position: relative;
}
.msg-tab.active {
  color: var(--accent, #2d6a4f);
  font-weight: 600;
  border-bottom-color: var(--accent, #2d6a4f);
}
.msg-tab:not(.active):hover {
  color: var(--text);
}
.tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 8px;
  background: var(--danger, #e53e3e);
  color: white;
  font-size: 10px;
  font-weight: 700;
  margin-left: 4px;
  vertical-align: middle;
}

.unread-badge {
  background: var(--accent);
  color: white;
  font-size: 11px;
  min-width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
}

.sort-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border);
}
.sort-label {
  color: var(--text-dim);
  font-size: 12px;
}
.sort-btn {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-dim);
  cursor: pointer;
  font-size: 12px;
  padding: 5px 9px;
  transition: all 0.15s ease;
}
.sort-btn.active,
.sort-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}
.sort-btn.active {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

/* Item action buttons */
.chat-item {
  position: relative;
}
.item-actions {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  display: flex;
  gap: 4px;
  z-index: 5;
  opacity: 0.5;
  transition: opacity 0.15s ease;
}
.chat-item:hover .item-actions {
  opacity: 1;
}
.item-action-btn {
  width: 28px; height: 28px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-dim);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.15s ease;
}
.item-action-btn:hover { border-color: var(--accent); color: var(--accent); }
.item-action-btn.danger:hover { border-color: var(--danger, #e53e3e); color: var(--danger, #e53e3e); }

/* Rename modal */
.rename-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  padding: 20px;
}
.rename-modal {
  background: var(--bg);
  border-radius: var(--radius-lg, 16px);
  padding: 20px;
  width: 100%;
  max-width: 360px;
  box-shadow: var(--shadow-lg, 0 20px 60px rgba(0,0,0,0.3));
}
.rename-modal h4 {
  margin: 0 0 14px;
  font-size: 15px;
  font-weight: 700;
}
.rename-modal input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  font-size: 14px;
  background: var(--surface);
  color: var(--text);
  margin-bottom: 14px;
}
.rename-modal input:focus { outline: none; border-color: var(--accent); }
.rename-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
.btn-cancel {
  padding: 8px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  color: var(--text-2);
  font-size: 13px;
  cursor: pointer;
}
.btn-cancel:hover { background: var(--surface2); }
.btn-save {
  padding: 8px 16px;
  border: none;
  border-radius: var(--radius);
  background: var(--accent);
  color: white;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-save:not(:disabled):hover { opacity: 0.9; }
</style>

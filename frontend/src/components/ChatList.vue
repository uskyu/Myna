<template>
  <div class="page active">
    <div class="header">
      <h1>消息</h1>
      <div class="actions">
        <button @click="emit('create-room')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
      </div>
    </div>
    <div class="search-bar">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="search" v-model.trim="filter" placeholder="搜索聊天/room..." aria-label="搜索聊天或 room">
    </div>
    <div class="msg-tabs">
      <button class="msg-tab" :class="{ active: activeTab === 'group' }" @click="activeTab = 'group'">
        群聊 <span v-if="groupUnread > 0" class="tab-badge">{{ groupUnread }}</span>
      </button>
      <button class="msg-tab" :class="{ active: activeTab === 'dm' }" @click="activeTab = 'dm'">
        私信 <span v-if="dmUnread > 0" class="tab-badge">{{ dmUnread }}</span>
      </button>
    </div>
    <div class="sort-bar">
      <span class="sort-label">排序</span>
      <button v-for="option in sortOptions" :key="option.key" class="sort-btn" :class="{ active: sortBy === option.key }" @click="setSort(option.key)">{{ option.label }}{{ sortBy === option.key ? (sortDesc ? ' ↓' : ' ↑') : '' }}</button>
    </div>
    <div class="chat-list">
      <template v-if="activeTab === 'group'">
        <div v-for="r in sortedRooms" :key="r.id" class="chat-item-wrapper"
          @touchstart="onTouchStart($event, r, 'group')"
          @touchmove="onTouchMove($event, r, 'group')"
          @touchend="onTouchEnd($event, r, 'group')"
          @mousedown="onMouseDown($event, r, 'group')"
          >
          <div class="chat-item" :class="{ swiped: swipeOffsets[r.id] < 0, pinned: isPinned(r.id) }" :style="{ transform: `translateX(${swipeOffsets[r.id] || 0}px)` }" @click="onItemClick(r, 'group')">
            <div class="avatar" :style="{ background: getAgentColor(roomIndex(r.id) + 2) }">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </div>
            <div class="info">
              <div class="name">{{ r.name }}</div>
              <div class="preview">{{ r.last_message ? r.last_message.sender_name + ': ' + r.last_message.text.slice(0, 30) : (r.members?.length || 0) + ' 个成员' }}</div>
            </div>
            <div class="meta">
              <span class="time">{{ formatTime(r.last_message?.created_at || r.updated_at || r.created_at) }}</span>
              <span v-if="store.unreadCounts[r.id] > 0" class="unread-badge">{{ store.unreadCounts[r.id] }}</span>
              <span v-else-if="isRoomActive(r.id)" class="active-badge"><span class="pulse-dot"></span>生成中</span>
            </div>
          </div>
          <div class="swipe-actions">
            <button class="swipe-action-btn pin" :class="{ active: isPinned(r.id) }" @click.stop="togglePin(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 17v5"/><path d="M5 17h14"/><path d="M7 17 9 3h6l2 14"/></svg><span>{{ isPinned(r.id) ? '取消置顶' : '置顶' }}</span></button>
            <button class="swipe-action-btn rename" @click.stop="startRename(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg><span>重命名</span></button>
            <button class="swipe-action-btn delete" @click.stop="deleteRoom(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg><span>删除</span></button>
          </div>
        </div>
        <div v-if="!sortedRooms.length" class="empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          <p>{{ filter ? '没有匹配的群聊' : '还没有群聊' }}</p><p v-if="!filter">点击右上角 + 创建</p>
        </div>
      </template>
      <template v-if="activeTab === 'dm'">
        <div v-for="dm in sortedDms" :key="dm.id" class="chat-item-wrapper"
          @touchstart="onTouchStart($event, dm, 'dm')"
          @touchmove="onTouchMove($event, dm, 'dm')"
          @touchend="onTouchEnd($event, dm, 'dm')"
          @mousedown="onMouseDown($event, dm, 'dm')">
          <div class="chat-item" :class="{ swiped: swipeOffsets[dm.id] < 0, pinned: isPinned(dm.id) }" :style="{ transform: `translateX(${swipeOffsets[dm.id] || 0}px)` }" @click="onItemClick(dm, 'dm')">
            <div class="avatar round" :style="{ background: getAgentColor(agentIndex(dm.agent?.id)) }">
              <span v-html="getAgentIcon(agentIndex(dm.agent?.id))"></span>
            </div>
            <div class="info">
              <div class="name">{{ dm.agent?.name || '未知' }}</div>
              <div class="preview">{{ dm.last_message?.text?.slice(0, 30) || '开始对话' }}</div>
            </div>
            <div class="meta">
              <span class="time">{{ formatTime(dm.last_message?.created_at || dm.updated_at || dm.created_at) }}</span>
              <span v-if="store.unreadCounts[dm.id] > 0" class="unread-badge">{{ store.unreadCounts[dm.id] }}</span>
              <span v-else-if="isRoomActive(dm.id)" class="active-badge"><span class="pulse-dot"></span>生成中</span>
            </div>
          </div>
          <div class="swipe-actions">
            <button class="swipe-action-btn pin" :class="{ active: isPinned(dm.id) }" @click.stop="togglePin(dm)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 17v5"/><path d="M5 17h14"/><path d="M7 17 9 3h6l2 14"/></svg><span>{{ isPinned(dm.id) ? '取消置顶' : '置顶' }}</span></button>
            <button class="swipe-action-btn delete" @click.stop="deleteRoom(dm)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg><span>删除</span></button>
          </div>
        </div>
        <div v-if="!sortedDms.length" class="empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
          <p>{{ filter ? '没有匹配的私信' : '还没有私信' }}</p><p v-if="!filter">在智能体列表中点击消息图标开始</p>
        </div>
      </template>
    </div>

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

    <Teleport to="body">
      <div v-if="deletingRoom" class="delete-confirm-overlay" @click.self="closeDeleteConfirm">
        <div class="delete-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-room-title">
          <div class="delete-confirm-icon" aria-hidden="true">!</div>
          <h4 id="delete-room-title">确认删除对话？</h4>
          <p>即将删除「{{ deletingRoomName }}」。消息将被清除，此操作不可撤销，请确认是否继续。</p>
          <div class="delete-confirm-actions">
            <button class="btn-cancel" @click="closeDeleteConfirm">取消</button>
            <button class="btn btn-danger" @click="confirmDeleteRoom">确认删除</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { store, api, loadConversations, loadAgents, getAgentColor, getAgentIcon, togglePinnedConversation } from '../store.js'

const emit = defineEmits(['open-chat', 'create-room'])

const activeTab = ref('group')
const filter = ref('')
const agentIndex = (id) => store.agents.findIndex(a => a.id === id)
const renamingRoom = ref(null)
const renameText = ref('')
const deletingRoom = ref(null)
const sortOptions = [
  { key: 'lastTime', label: '最后对话' },
  { key: 'name', label: '聊天框名' },
  { key: 'createdAt', label: '创建时间' },
]
const sortBy = ref(localStorage.getItem('chat_sort_by') || 'lastTime')
const sortDesc = ref(localStorage.getItem('chat_sort_desc') !== 'false')
const lastClickedSort = ref(sortBy.value)

function normalizeSearch(value) {
  return String(value || '').toLowerCase()
}

function matchesSearch(values) {
  const q = normalizeSearch(filter.value)
  if (!q) return true
  return values.some(value => normalizeSearch(value).includes(q))
}

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

const groupUnread = computed(() => store.rooms.reduce((sum, r) => sum + (store.unreadCounts[r.id] || 0), 0))
const dmUnread = computed(() => store.dms.reduce((sum, dm) => sum + (store.unreadCounts[dm.id] || 0), 0))

const sortedRooms = computed(() => {
  const rooms = store.rooms.filter(r => matchesSearch([
    r.name,
    r.last_message?.text,
    r.last_message?.sender_name,
    ...(r.members || []).map(member => member?.name || member?.agent_name || member?.display_name || member?.id),
  ]))
  return sortConversations(rooms)
})
const sortedDms = computed(() => {
  const dms = store.dms.filter(dm => matchesSearch([
    dm.name,
    dm.agent?.name,
    dm.agent?.description,
    dm.last_message?.text,
    dm.last_message?.sender_name,
  ]))
  return sortConversations(dms)
})
function sortConversations(items) {
  return [...items].sort((a, b) => {
    const pinnedA = isPinned(a.id)
    const pinnedB = isPinned(b.id)
    if (pinnedA !== pinnedB) return pinnedA ? -1 : 1
    const pa = (store.unreadCounts[a.id] || 0) > 0 || isRoomActive(a.id)
    const pb = (store.unreadCounts[b.id] || 0) > 0 || isRoomActive(b.id)
    if (pa !== pb) return pa ? -1 : 1
    let r
    if (sortBy.value === 'name') r = String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN')
    else if (sortBy.value === 'createdAt') r = parseTimestamp(a.created_at) - parseTimestamp(b.created_at)
    else r = conversationTime(a) - conversationTime(b)
    if (r === 0) r = String(a.name || '').localeCompare(String(b.name || ''), 'zh-CN')
    return sortDesc.value ? -r : r
  })
}

function conversationTime(item) {
  for (const ts of [item.last_message?.created_at, item.updated_at, item.created_at]) {
    const p = parseTimestamp(ts); if (p) return p
  }
  return 0
}
function parseTimestamp(ts) {
  if (!ts) return 0
  if (typeof ts === 'number') return ts
  const v = String(ts).replace(' ', 'T')
  const d = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(v) ? v : v + 'Z')
  return isNaN(d.getTime()) ? 0 : d.getTime()
}

function roomIndex(roomId) { return store.rooms.findIndex(r => r.id === roomId) }
function isRoomActive(roomId) { return Object.values(store.activeStreams).some(s => s.roomId === roomId) }

function formatTime(ts) {
  const parsed = parseTimestamp(ts)
  if (!parsed) return ''
  const date = new Date(parsed)
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const yesterday = new Date(today)
  yesterday.setDate(yesterday.getDate() - 1)
  const timePart = String(date.getHours()).padStart(2, '0') + ':' + String(date.getMinutes()).padStart(2, '0')
  if (date >= today) return timePart
  if (date >= yesterday) return '昨天 ' + timePart
  if (date.getFullYear() === now.getFullYear()) return (date.getMonth() + 1) + '月' + date.getDate() + '日 ' + timePart
  return date.getFullYear() + '年' + (date.getMonth() + 1) + '月' + date.getDate() + '日 ' + timePart
}

function startRename(room) { renamingRoom.value = room; renameText.value = room.name || '' }
async function confirmRename() {
  if (!renameText.value.trim() || !renamingRoom.value) return
  await api('PUT', `/admin/rooms/${renamingRoom.value.id}`, { name: renameText.value.trim() })
  renamingRoom.value.name = renameText.value.trim()
  renamingRoom.value = null
}
const deletingRoomName = computed(() => deletingRoom.value?.name || deletingRoom.value?.agent?.name || '此对话')

function deleteRoom(room) {
  deletingRoom.value = room
}

function closeDeleteConfirm() {
  deletingRoom.value = null
}

async function confirmDeleteRoom() {
  if (!deletingRoom.value) return
  const roomId = deletingRoom.value.id
  closeDeleteConfirm()
  await api('DELETE', `/admin/rooms/${roomId}`)
  loadConversations()
}
function isPinned(roomId) { return store.pinnedConversations.includes(String(roomId)) }
function togglePin(room) {
  if (!room) return
  togglePinnedConversation(room.id)
  closeAllSwipes()
}

function onItemClick(item, type) {
  if ((swipeOffsets[item.id] || 0) < -10) { swipeOffsets[item.id] = 0; return }
  emit('open-chat', item, type)
}

const swipeOffsets = reactive({})

function closeAllSwipes(exceptId = null) {
  for (const key of Object.keys(swipeOffsets)) {
    if (key !== exceptId) swipeOffsets[key] = 0
  }
}

let touchStartX = 0, touchStartY = 0, touchStartTime = 0, isSwiping = false
let currentTouchItem = null, currentTouchType = null

function swipeWidth(type) { return type === 'group' ? -210 : -140 }

function onTouchStart(e, item, type) {
  const touch = e.touches[0]
  touchStartX = touch.clientX; touchStartY = touch.clientY
  touchStartTime = Date.now(); isSwiping = false
  currentTouchItem = item; currentTouchType = type
  closeAllSwipes(item.id)
}

function onTouchMove(e, item, type) {
  if (!currentTouchItem || currentTouchItem.id !== item.id) return
  const touch = e.touches[0]
  const dx = touch.clientX - touchStartX
  const dy = touch.clientY - touchStartY
  if (Math.abs(dy) > Math.abs(dx)) return
  if (dx > 0 && (swipeOffsets[item.id] || 0) >= 0) return
  if (Math.abs(dx) > 10) isSwiping = true
  if (isSwiping) { e.preventDefault(); swipeOffsets[item.id] = Math.min(0, Math.max(swipeWidth(type), dx)) }
}

function onTouchEnd(e, item, type) {
  const elapsed = Date.now() - touchStartTime
  const offset = swipeOffsets[item.id] || 0
  if (isSwiping) {
    const w = swipeWidth(type)
    if (offset < w * 0.4) swipeOffsets[item.id] = w
    else swipeOffsets[item.id] = 0
  }
  isSwiping = false; currentTouchItem = null; currentTouchType = null
}

function onMouseDown(e, item, type) {
  if (e.button !== 0) return
  touchStartX = e.clientX; touchStartY = e.clientY
  touchStartTime = Date.now(); isSwiping = false
  currentTouchItem = item; currentTouchType = type
  closeAllSwipes(item.id)

  const onMouseMove = (ev) => {
    const dx = ev.clientX - touchStartX
    const dy = ev.clientY - touchStartY
    if (Math.abs(dx) < 10) return
    if (Math.abs(dy) > Math.abs(dx)) { cleanup(); return }
    isSwiping = true
    swipeOffsets[item.id] = Math.min(0, Math.max(swipeWidth(type), dx))
  }
  const onMouseUp = () => {
    if (isSwiping) {
      const w = swipeWidth(type)
      const offset = swipeOffsets[item.id] || 0
      if (offset < w * 0.4) swipeOffsets[item.id] = w
      else swipeOffsets[item.id] = 0
    }
    cleanup()
  }
  const cleanup = () => {
    isSwiping = false; currentTouchItem = null; currentTouchType = null
    document.removeEventListener('mousemove', onMouseMove)
    document.removeEventListener('mouseup', onMouseUp)
  }
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
}

function onGlobalClick(e) {
  if (e.target && !e.target.closest('.chat-item-wrapper')) closeAllSwipes()
}

let timer
onMounted(() => {
  loadConversations(); loadAgents()
  timer = setInterval(loadConversations, 5000)
  document.addEventListener('click', onGlobalClick)
})
onUnmounted(() => { clearInterval(timer); document.removeEventListener('click', onGlobalClick) })
</script>

<style scoped>
.msg-tabs { display:flex; padding:0 16px; gap:0; border-bottom:1px solid var(--border); margin-bottom:4px; }
.msg-tab { flex:1; padding:10px 0; font-size:14px; font-weight:500; color:var(--text-dim); background:none; border:none; border-bottom:2px solid transparent; cursor:pointer; transition:all .2s ease; text-align:center; position:relative; }
.msg-tab.active { color:var(--accent,#2d6a4f); font-weight:600; border-bottom-color:var(--accent,#2d6a4f); }
.msg-tab:not(.active):hover { color:var(--text); }
.tab-badge { display:inline-flex; align-items:center; justify-content:center; min-width:16px; height:16px; padding:0 4px; border-radius:8px; background:var(--danger,#e53e3e); color:#fff; font-size:10px; font-weight:700; margin-left:4px; vertical-align:middle; }
.unread-badge { background:var(--accent); color:#fff; font-size:11px; min-width:18px; height:18px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; }
.sort-bar { display:flex; align-items:center; gap:6px; padding:8px 16px; border-bottom:1px solid var(--border); }
.sort-label { color:var(--text-dim); font-size:12px; }
.sort-btn { border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg); color:var(--text-dim); cursor:pointer; font-size:12px; padding:5px 9px; transition:all .15s ease; }
.sort-btn.active,.sort-btn:hover { border-color:var(--accent); color:var(--accent); }
.sort-btn.active { background:color-mix(in srgb,var(--accent) 12%,transparent); }

.chat-item-wrapper { position:relative; overflow:hidden; }
.chat-item { position:relative; display:flex; align-items:center; padding:12px 16px; gap:12px; background:var(--bg); transition:transform .3s cubic-bezier(.25,.46,.45,.94), background-color .2s ease; cursor:pointer; z-index:1; }
.chat-item.pinned { background:color-mix(in srgb,var(--surface,#f3f4f6) 82%,var(--accent,#2d6a4f) 18%); }
.chat-item:active { background:var(--surface,rgba(0,0,0,.03)); }
.chat-item.pinned:active { background:color-mix(in srgb,var(--surface,#f3f4f6) 74%,var(--accent,#2d6a4f) 26%); }

.swipe-actions { position:absolute; right:0; top:0; bottom:0; display:flex; z-index:0; }
.swipe-action-btn { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:3px; width:70px; height:100%; border:none; color:#fff; font-size:11px; font-weight:500; cursor:pointer; }
.swipe-action-btn:active { opacity:.8; }
.swipe-action-btn.pin { background:var(--accent,#2d6a4f); }
.swipe-action-btn.pin.active { background:var(--accent-hover,#1f4c38); }
.swipe-action-btn.rename { background:#f59e0b; }
.swipe-action-btn.delete { background:var(--danger,#e53e3e); }

.rename-overlay { position:fixed; inset:0; background:rgba(0,0,0,.4); display:flex; align-items:center; justify-content:center; z-index:2000; padding:20px; }
.rename-modal { background:var(--bg); border-radius:var(--radius-lg,16px); padding:20px; width:100%; max-width:360px; box-shadow:var(--shadow-lg,0 20px 60px rgba(0,0,0,.3)); }
.rename-modal h4 { margin:0 0 14px; font-size:15px; font-weight:700; }
.rename-modal input { width:100%; padding:10px 14px; border:1px solid var(--border); border-radius:var(--radius); font-size:14px; background:var(--surface); color:var(--text); margin-bottom:14px; box-sizing:border-box; }
.rename-modal input:focus { outline:none; border-color:var(--accent); }
.rename-actions { display:flex; justify-content:flex-end; gap:8px; }
.btn-cancel { padding:8px 16px; border:1px solid var(--border); border-radius:var(--radius); background:var(--surface); color:var(--text-2); font-size:13px; cursor:pointer; }
.btn-cancel:hover { background:var(--surface2); }
.btn-save { padding:8px 16px; border:none; border-radius:var(--radius); background:var(--accent); color:#fff; font-size:13px; font-weight:600; cursor:pointer; }
.btn-save:disabled { opacity:.5; cursor:not-allowed; }
.btn-save:not(:disabled):hover { opacity:.9; }

.delete-confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 2100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.52);
}
.delete-confirm-modal {
  width: min(100%, 420px);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg, 16px);
  background: var(--bg);
  box-shadow: var(--shadow-lg, 0 20px 60px rgba(0,0,0,0.3));
  padding: 24px;
  text-align: center;
}
.delete-confirm-icon {
  width: 44px;
  height: 44px;
  margin: 0 auto 12px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--danger) 14%, transparent);
  color: var(--danger);
  font-size: 22px;
  font-weight: 800;
}
.delete-confirm-modal h4 {
  margin: 0 0 8px;
  color: var(--text);
  font-size: 18px;
}
.delete-confirm-modal p {
  margin: 0;
  color: var(--text-2);
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
}
.delete-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 22px;
}
.delete-confirm-actions .btn,
.delete-confirm-actions .btn-cancel {
  min-width: 96px;
}
@media (max-width: 480px) {
  .delete-confirm-modal {
    padding: 22px 18px;
  }

  .delete-confirm-actions {
    flex-direction: column-reverse;
  }

  .delete-confirm-actions .btn,
  .delete-confirm-actions .btn-cancel {
    width: 100%;
    min-height: 40px;
  }
}
</style>

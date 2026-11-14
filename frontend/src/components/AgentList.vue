<template>
  <div class="page active">
    <div class="header">
      <h1>{{ tr('智能体') }}</h1>
      <div class="actions">
        <button @click="$emit('create-agent')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
      </div>
    </div>
    <div class="search-bar">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="text" v-model="filter" :placeholder="tr('搜索智能体...')">
    </div>
    <div class="sort-bar">
      <span class="sort-label">{{ tr('排序') }}</span>
      <button v-for="option in sortOptions" :key="option.key" class="sort-btn" :class="{ active: sortBy === option.key }" @click="setSort(option.key)">{{ tr(option.label) }}{{ sortBy === option.key ? (sortDesc ? ' ↓' : ' ↑') : '' }}</button>
    </div>
    <div class="agent-grid list-view">
      <div v-for="a in filtered" :key="a.id" class="agent-card-wrapper"
        @touchstart="onTouchStart($event, a)"
        @touchmove="onTouchMove($event, a)"
        @touchend="onTouchEnd($event, a)"
        @contextmenu.prevent="openContextMenu($event, a)">
        <div class="agent-card" :class="{ 'system-agent': a.id === '__system__', selected: a.id === selectedId, pinned: isPinned(a.id) }" :style="{ '--swipe-x': `${swipeOffsets[a.id] || 0}px` }" @click="onAgentClick(a)">
          <div class="avatar-wrap">
            <div class="agent-avatar" :style="{ background: getAgentColor(agentIndex(a.id)) }">
              <span v-html="getAgentIcon(agentIndex(a.id))"></span>
            </div>
            <span class="status-dot" :class="a.status === 'online' ? 'online' : 'offline'"></span>
          </div>
          <div class="info-block">
            <div class="agent-name">
              {{ a.name }}
              <span v-if="a.id === '__system__'" class="sys-badge">{{ tr('系统') }}</span>
              <span v-if="isPinned(a.id)" class="pin-badge">{{ tr('置顶') }}</span>
            </div>
            <div class="agent-desc">{{ a.description || tr('通用智能体') }}</div>
          </div>
        </div>
        <div class="swipe-actions">
          <button class="swipe-action-btn pin" @click.stop="togglePin(a)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 17v5"/><path d="M5 17h14"/><path d="M15 3l6 6-4 4v4H7v-4L3 9l6-6"/></svg>
            <span>{{ tr(isPinned(a.id) ? '取消置顶' : '置顶') }}</span>
          </button>
          <button class="swipe-action-btn delete" @click.stop="deleteAgent(a)">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
            <span>{{ tr('删除') }}</span>
          </button>
        </div>
      </div>
    </div>
    <div v-if="!filtered.length" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>
      <p>{{ filter ? tr('没有匹配的智能体') : tr('还没有智能体') }}</p>
      <p>{{ tr('点击右上角 + 创建') }}</p>
    </div>

    <Teleport to="body">
      <div v-if="contextMenu" class="agent-context-menu" :style="{ left: contextMenu.x + 'px', top: contextMenu.y + 'px' }" @click.stop>
        <button class="context-menu-item" @click="contextTogglePin">
          <span>{{ tr(isPinned(contextMenu.agent.id) ? '取消置顶' : '置顶') }}</span>
        </button>
        <button v-if="contextMenu.agent.id !== '__system__'" class="context-menu-item danger" @click="contextDeleteAgent">
          <span>{{ tr('删除') }}</span>
        </button>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="deletingAgent" class="delete-confirm-overlay" @click.self="closeDeleteConfirm">
        <div class="delete-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-agent-title">
          <div class="delete-confirm-icon" aria-hidden="true">!</div>
          <h4 id="delete-agent-title">{{ tr('确认删除智能体？') }}</h4>
          <p>{{ tr('即将删除') }}「{{ deletingAgent.name }}」。{{ tr('此操作不可撤销，请确认是否继续。') }}</p>
          <div class="delete-confirm-actions">
            <button class="btn-cancel" @click="closeDeleteConfirm">{{ tr('取消') }}</button>
            <button class="btn-danger" @click="confirmDeleteAgent">{{ tr('确认删除') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { store, loadAgents, api, getAgentColor, getAgentIcon } from '../store.js'
import { tr } from '../i18n.js'

const props = defineProps({ selectedId: String })
const emit = defineEmits(['open-detail', 'create-agent', 'deleted-agent'])
const filter = ref('')
const sortOptions = [
  { key: 'name', label: '智能体名' },
  { key: 'created_at', label: '创建时间' },
]
const sortBy = ref(localStorage.getItem('hub-agent-sort-by') || localStorage.getItem('hub-agent-sort') || 'name')
const sortDesc = ref(localStorage.getItem('hub-agent-sort-desc') === 'true')
const pinnedAgentIds = ref(readPinnedAgentIds())
const lastClickedSort = ref(sortBy.value)
const agentIndex = (id) => store.agents.findIndex(a => a.id === id)
const searchableAgents = computed(() => [...store.agents].filter(a => a.id !== 'user' && a.id !== 'system'))
const deletingAgent = ref(null)
const contextMenu = ref(null)
const swipeOffsets = reactive({})

function readPinnedAgentIds() {
  try {
    const parsed = JSON.parse(localStorage.getItem('hub-pinned-agent-ids') || '[]')
    return Array.isArray(parsed) ? parsed.filter(Boolean) : []
  } catch (e) {
    return []
  }
}

function savePinnedAgentIds() {
  localStorage.setItem('hub-pinned-agent-ids', JSON.stringify(pinnedAgentIds.value))
}

function isPinned(agentId) {
  return pinnedAgentIds.value.includes(agentId)
}

function setSort(key) {
  if (lastClickedSort.value === key) {
    sortDesc.value = !sortDesc.value
  } else {
    sortBy.value = key
    sortDesc.value = false
    lastClickedSort.value = key
  }
  localStorage.setItem('hub-agent-sort-by', sortBy.value)
  localStorage.setItem('hub-agent-sort-desc', String(sortDesc.value))
}

function parseTimestamp(ts) {
  if (!ts) return 0
  if (typeof ts === 'number') return ts
  const value = String(ts).replace(' ', 'T')
  const date = new Date(/(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : value + 'Z')
  return Number.isNaN(date.getTime()) ? 0 : date.getTime()
}

const filtered = computed(() => {
  let list = [...searchableAgents.value]
  if (filter.value) {
    const q = filter.value.toLowerCase()
    list = list.filter(a => (a.name || '').toLowerCase().includes(q) || (a.description || '').toLowerCase().includes(q))
  }
  list.sort((a, b) => {
    const pinnedResult = Number(isPinned(b.id)) - Number(isPinned(a.id))
    if (pinnedResult !== 0) return pinnedResult
    let result
    if (sortBy.value === 'created_at') result = parseTimestamp(a.created_at) - parseTimestamp(b.created_at)
    else result = (a.name || '').localeCompare(b.name || '', 'zh-Hans-CN')
    if (result === 0) result = (a.name || '').localeCompare(b.name || '', 'zh-Hans-CN')
    return sortDesc.value ? -result : result
  })
  const sysIdx = list.findIndex(a => a.id === '__system__')
  if (sysIdx > 0) {
    const [sys] = list.splice(sysIdx, 1)
    list.unshift(sys)
  }
  return list
})


function togglePin(agent) {
  if (!agent) return
  if (isPinned(agent.id)) pinnedAgentIds.value = pinnedAgentIds.value.filter(id => id !== agent.id)
  else pinnedAgentIds.value = [agent.id, ...pinnedAgentIds.value]
  savePinnedAgentIds()
  closeAllSwipes()
}

function deleteAgent(agent) {
  if (!agent || agent.id === '__system__') return
  deletingAgent.value = agent
  contextMenu.value = null
  closeAllSwipes()
}

function openContextMenu(event, agent) {
  if (!agent) return
  closeAllSwipes()
  contextMenu.value = {
    agent,
    x: Math.min(event.clientX, window.innerWidth - 180),
    y: Math.min(event.clientY, window.innerHeight - 120),
  }
}

function contextTogglePin() {
  if (!contextMenu.value) return
  const agent = contextMenu.value.agent
  contextMenu.value = null
  togglePin(agent)
}

function contextDeleteAgent() {
  if (!contextMenu.value) return
  const agent = contextMenu.value.agent
  contextMenu.value = null
  deleteAgent(agent)
}

function closeDeleteConfirm() {
  deletingAgent.value = null
}

async function confirmDeleteAgent() {
  if (!deletingAgent.value) return
  const agentId = deletingAgent.value.id
  closeDeleteConfirm()
  await api('DELETE', `/admin/agents/${agentId}`)
  pinnedAgentIds.value = pinnedAgentIds.value.filter(id => id !== agentId)
  savePinnedAgentIds()
  if (props.selectedId === agentId) emit('deleted-agent', agentId)
  await loadAgents()
}

function onAgentClick(agent) {
  if ((swipeOffsets[agent.id] || 0) < -10) { swipeOffsets[agent.id] = 0; return }
  emit('open-detail', agent)
}

function closeAllSwipes(exceptId = null) {
  for (const key of Object.keys(swipeOffsets)) {
    if (key !== exceptId) swipeOffsets[key] = 0
  }
}

const swipeWidth = -140
let touchStartX = 0, touchStartY = 0, isSwiping = false
let currentTouchAgent = null

function onTouchStart(e, agent) {
  const touch = e.touches[0]
  touchStartX = touch.clientX; touchStartY = touch.clientY
  isSwiping = false; currentTouchAgent = agent
  closeAllSwipes(agent.id)
}

function onTouchMove(e, agent) {
  if (!currentTouchAgent || currentTouchAgent.id !== agent.id) return
  const touch = e.touches[0]
  const dx = touch.clientX - touchStartX
  const dy = touch.clientY - touchStartY
  if (Math.abs(dy) > Math.abs(dx)) return
  if (dx > 0 && (swipeOffsets[agent.id] || 0) >= 0) return
  if (Math.abs(dx) > 10) isSwiping = true
  if (isSwiping) { e.preventDefault(); swipeOffsets[agent.id] = Math.min(0, Math.max(swipeWidth, dx)) }
}

function onTouchEnd(e, agent) {
  if (isSwiping) {
    const offset = swipeOffsets[agent.id] || 0
    swipeOffsets[agent.id] = offset < swipeWidth * 0.4 ? swipeWidth : 0
  }
  isSwiping = false; currentTouchAgent = null
}

function onGlobalClick(e) {
  if (e.target && !e.target.closest('.agent-card-wrapper')) closeAllSwipes()
  if (e.target && !e.target.closest('.agent-context-menu')) contextMenu.value = null
}

onMounted(() => {
  loadAgents()
  document.addEventListener('click', onGlobalClick)
})
onUnmounted(() => document.removeEventListener('click', onGlobalClick))
</script>

<style scoped>
.sort-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  scrollbar-width: none;
}

.sort-bar::-webkit-scrollbar {
  display: none;
}

.sort-label {
  color: var(--text-dim);
  font-size: 12px;
  flex-shrink: 0;
}

.sort-btn {
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--bg);
  color: var(--text-dim);
  cursor: pointer;
  font-size: 12px;
  padding: 5px 9px;
  transition: all .15s ease;
  white-space: nowrap;
  flex-shrink: 0;
}

.sort-btn.active,
.sort-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.sort-btn.active {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
}

.agent-grid.list-view .agent-card-wrapper {
  position: relative;
  overflow: hidden;
  width: 100%;
  min-width: 0;
  min-height: 62px;
  border-radius: 10px;
  background: var(--bg);
  touch-action: pan-y;
  -webkit-tap-highlight-color: transparent;
}

.agent-grid.list-view .agent-card {
  position: relative;
  display: grid;
  grid-template-columns: 44px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  width: 100%;
  min-width: 0;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.15s, transform .3s cubic-bezier(.25,.46,.45,.94);
  background: var(--bg);
  z-index: 1;
  transform: translate3d(var(--swipe-x, 0px), 0, 0);
  will-change: transform;
}

.agent-grid.list-view .agent-card:active {
  transform: translate3d(var(--swipe-x, 0px), 0, 0);
}

.agent-grid.list-view .agent-card:hover {
  background: var(--surface2);
  border-color: var(--border-strong);
}

.agent-grid.list-view .agent-card.selected {
  background: var(--accent-soft);
  border-color: rgba(45, 106, 79, 0.28);
}

.agent-grid.list-view .agent-card.pinned {
  background: color-mix(in srgb, var(--accent) 8%, var(--bg));
}

.swipe-actions {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 140px;
  display: flex;
  z-index: 0;
  pointer-events: auto;
}

.swipe-action-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  width: 70px;
  height: 100%;
  border: none;
  color: #fff;
  font-size: 11px;
  font-weight: 500;
  cursor: pointer;
}

.swipe-action-btn:active {
  opacity: .8;
}

.swipe-action-btn.pin {
  background: var(--accent, #2d6a4f);
}

.swipe-action-btn.delete {
  background: var(--danger, #e53e3e);
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

.pin-badge {
  display: inline-block;
  font-size: 10px;
  font-weight: 600;
  padding: 1px 6px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--accent) 16%, transparent);
  color: var(--accent, #2d6a4f);
  margin-left: 6px;
  vertical-align: middle;
}

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

.btn-cancel,
.btn-danger {
  min-width: 96px;
  padding: 8px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
}

.btn-cancel {
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text-2);
}

.btn-danger {
  border: none;
  background: var(--danger, #e53e3e);
  color: #fff;
  font-weight: 600;
}

@media (max-width: 767px) {
  .agent-grid.list-view {
    display: grid;
    grid-template-columns: minmax(0, 1fr);
    gap: 6px;
    padding: 8px 10px 16px;
    overflow-x: hidden;
  }

  .agent-grid.list-view .agent-card-wrapper {
    grid-column: 1 / -1;
    max-width: 100%;
  }

  .agent-grid.list-view .agent-card {
    min-height: 60px;
  }

  .swipe-actions {
    height: 100%;
  }
}

@media (max-width: 480px) {
  .delete-confirm-modal {
    padding: 22px 18px;
  }

  .delete-confirm-actions {
    flex-direction: column-reverse;
  }

  .btn-cancel,
  .btn-danger {
    width: 100%;
    min-height: 40px;
  }
}

@media (min-width: 768px) {
  .agent-grid.list-view {
    padding: 14px;
    gap: 12px;
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
}
</style>


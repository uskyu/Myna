<template>
  <div class="page active">
    <div class="header">
      <h1>{{ tr('Myna') }}</h1>
      <div class="actions">
        <slot name="header-actions"></slot>
        <button @click="emit('create-room')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
      </div>
    </div>
    <button class="sidebar-new-chat" @click="emit('create-room')">＋ {{ tr('新建对话') }}</button>
    <div class="search-bar">
      <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg>
      <input type="search" v-model.trim="filter" :placeholder="tr('搜索独立任务...')" :aria-label="tr('搜索聊天或 room')">
    </div>
    <div v-if="String(filter || '').trim().length >= 2" class="msg-search-panel">
      <div v-if="msgSearching" class="msr-status">{{ tr('搜索消息中…') }}</div>
      <template v-else-if="msgResults.length">
        <div class="msr-head">{{ tr('消息结果') }} · {{ msgResults.length }}</div>
        <button v-for="r in msgResults" :key="r.room_id + ':' + r.id" class="msr-item" @click="openMsgResult(r)">
          <span class="msr-meta"><b class="msr-room">{{ r.room_name }}</b><span class="msr-sender">{{ r.sender_name }}</span><span class="msr-time">{{ String(r.created_at || '').slice(0, 16).replace('T', ' ') }}</span></span>
          <span class="msr-snippet" v-html="hl(r.snippet)"></span>
        </button>
      </template>
      <div v-else class="msr-status">{{ tr('无匹配消息') }}</div>
    </div>
    <div class="sort-bar">
      <span class="sort-label">{{ tr('排序') }}</span>
      <button v-for="option in sortOptions" :key="option.key" class="sort-btn" :class="{ active: sortBy === option.key }" @click="setSort(option.key)">{{ tr(option.label) }}{{ sortBy === option.key ? (sortDesc ? ' ↓' : ' ↑') : '' }}</button>
      <div class="sort-spacer"></div>
      <button class="selection-toggle" :class="{ active: selectionMode }" @click="toggleSelectionMode" :title="tr('批量管理')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="4" width="16" height="16" rx="3"/><path v-if="selectionMode" d="m8 12 3 3 5-6"/></svg>
      </button>
    </div>
    <div v-if="selectionMode" class="selection-bar">
      <button @click="toggleSelectAll">{{ allSelected ? tr('取消全选') : tr('全选') }}</button>
      <span>{{ tr('已选择') }} {{ selectedIds.size }} {{ tr('项') }}</span>
      <button class="selection-delete" :disabled="!selectedIds.size" @click="batchDeleteOpen = true">{{ tr('删除') }}</button>
    </div>
    <div class="conversation-sections">
    <section v-if="pinnedConversations.length" class="list-section">
      <h3 class="list-section-title">{{ tr('置顶') }}</h3>
      <div v-for="r in pinnedConversations" :key="r.id" class="chat-item-wrapper"
        @touchstart="onTouchStart($event, r, r.conversationType)"
        @touchmove="onTouchMove($event, r, r.conversationType)"
        @touchend="onTouchEnd($event, r, r.conversationType)"
        @contextmenu="openRoomContextMenu($event, r, r.conversationType)"
        >
        <div class="chat-item pinned" :style="{ transform: `translateX(${swipeOffsets[r.id] || 0}px)` }" @click="onItemClick(r, r.conversationType)">
          <span v-if="selectionMode" class="conversation-checkbox" :class="{ checked: selectedIds.has(r.id) }"><svg v-if="selectedIds.has(r.id)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m5 12 4 4L19 7"/></svg></span>
          <div class="avatar" :class="{ round: r.conversationType === 'dm' }" :style="{ background: getAgentColor(r.conversationType === 'dm' ? agentIndex(r.agent?.id) : roomIndex(r.id) + 2) }">
            <span v-if="r.conversationType === 'dm'" v-html="getAgentIcon(agentIndex(r.agent?.id))"></span>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          </div>
          <div class="info"><div class="name">{{ conversationName(r) }}</div><div class="preview">{{ conversationPreview(r) }}</div></div>
          <div class="meta">
            <span class="time">{{ formatTime(r.last_message?.created_at || r.created_at) }}</span>
            <span v-if="store.unreadCounts[r.id] > 0" class="unread-badge">{{ store.unreadCounts[r.id] }}</span>
          </div>
        </div>
        <div class="swipe-actions">
          <button class="swipe-action-btn pin active" @click.stop="togglePin(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 17v5"/><path d="M5 17h14"/><path d="M7 17 9 3h6l2 14"/></svg><span>{{ tr('取消置顶') }}</span></button>
          <button v-if="r.conversationType === 'group'" class="swipe-action-btn rename" @click.stop="startRename(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg><span>{{ tr('重命名') }}</span></button>
          <button class="swipe-action-btn delete" @click.stop="deleteRoom(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg><span>{{ tr('删除') }}</span></button>
        </div>
      </div>
    </section>
    <section class="list-section">
      <div class="sidebar-section-heading"><h3 class="list-section-title">{{ tr('项目') }}</h3><button @click="openCreateProject" title="新建项目" aria-label="新建项目">+</button></div>
      <div v-for="project in projects" :key="project.id" class="project-group">
        <button class="project-group-head" @click="toggleProject(project.id)">
          <svg class="chevron" :class="{ open: expandedProjects[project.id] }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 6 6 6-6 6"/></svg>
          <svg class="folder" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
          <span class="project-group-name">{{ project.name }}</span>
          <span class="project-group-count">{{ projectChats(project.id).length }}</span>
        </button>
        <div v-if="expandedProjects[project.id]" class="project-group-body">
          <div v-for="chat in projectChats(project.id)" :key="chat.id" class="chat-item-wrapper"
            @touchstart="onTouchStart($event, chat, chat.conversationType)"
            @touchmove="onTouchMove($event, chat, chat.conversationType)"
            @touchend="onTouchEnd($event, chat, chat.conversationType)"
            @contextmenu="openRoomContextMenu($event, chat, chat.conversationType)"
            >
            <div class="chat-item" :style="{ transform: `translateX(${swipeOffsets[chat.id] || 0}px)` }" @click="onItemClick(chat, chat.conversationType)">
          <span v-if="selectionMode" class="conversation-checkbox" :class="{ checked: selectedIds.has(chat.id) }"><svg v-if="selectedIds.has(chat.id)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m5 12 4 4L19 7"/></svg></span>
              <div class="info"><div class="name">{{ conversationName(chat) }}</div><div class="preview">{{ conversationPreview(chat) }}</div></div>
              <div class="meta"><span class="time">{{ formatTime(chat.last_message?.created_at || chat.created_at) }}</span></div>
            </div>
            <div class="swipe-actions">
              <button class="swipe-action-btn pin" :class="{ active: isPinned(chat.id) }" @click.stop="togglePin(chat)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 17v5"/><path d="M5 17h14"/><path d="M7 17 9 3h6l2 14"/></svg><span>{{ tr(isPinned(chat.id) ? '取消置顶' : '置顶') }}</span></button>
              <button class="swipe-action-btn rename" @click.stop="startRename(chat)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg><span>{{ tr('重命名') }}</span></button>
              <button class="swipe-action-btn delete" @click.stop="deleteRoom(chat)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg><span>{{ tr('删除') }}</span></button>
            </div>
          </div>
          <p v-if="!projectChats(project.id).length" class="project-group-empty">{{ tr('暂无对话') }}</p>
          <button class="project-add-chat" @click="startProjectChat(project)">＋ {{ tr('新建对话') }}</button>
        </div>
      </div>
    </section>
    <h3 class="list-section-title">{{ tr('最近对话') }}</h3>
    <div class="chat-list">
        <div v-if="loadingConversations" class="empty loading-state">
          <div class="msg-loading-spinner"></div>
          <p>{{ tr('正在加载消息...') }}</p>
        </div>
        <template v-else>
        <div v-for="r in visibleConversations" :key="r.id" class="chat-item-wrapper"
          @touchstart="onTouchStart($event, r, r.conversationType)"
          @touchmove="onTouchMove($event, r, r.conversationType)"
          @touchend="onTouchEnd($event, r, r.conversationType)"
          @contextmenu="openRoomContextMenu($event, r, r.conversationType)"
          >
          <div class="chat-item" :class="{ swiped: swipeOffsets[r.id] < 0, pinned: isPinned(r.id) }" :style="{ transform: `translateX(${swipeOffsets[r.id] || 0}px)` }" @click="onItemClick(r, r.conversationType)">
            <span v-if="selectionMode" class="conversation-checkbox" :class="{ checked: selectedIds.has(r.id) }">
              <svg v-if="selectedIds.has(r.id)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3"><path d="m5 12 4 4L19 7"/></svg>
            </span>
            <div class="avatar" :class="{ round: r.conversationType === 'dm' }" :style="{ background: getAgentColor(r.conversationType === 'dm' ? agentIndex(r.agent?.id) : roomIndex(r.id) + 2) }">
              <span v-if="r.conversationType === 'dm'" v-html="getAgentIcon(agentIndex(r.agent?.id))"></span>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
            </div>
            <div class="info">
              <div class="name">{{ conversationName(r) }}</div>
              <div class="preview">{{ conversationPreview(r) }}</div>
            </div>
            <div class="meta">
              <span class="time">{{ formatTime(r.last_message?.created_at || r.updated_at || r.created_at) }}</span>
              <span v-if="store.unreadCounts[r.id] > 0" class="unread-badge">{{ store.unreadCounts[r.id] }}</span>
              <span v-else-if="isRoomActive(r.id)" class="active-badge"><span class="pulse-dot"></span>{{ tr('生成中') }}</span>
            </div>
          </div>
          <div class="swipe-actions">
            <button class="swipe-action-btn pin" :class="{ active: isPinned(r.id) }" @click.stop="togglePin(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M12 17v5"/><path d="M5 17h14"/><path d="M7 17 9 3h6l2 14"/></svg><span>{{ tr(isPinned(r.id) ? '取消置顶' : '置顶') }}</span></button>
            <button v-if="r.conversationType === 'group'" class="swipe-action-btn rename" @click.stop="startRename(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg><span>{{ tr('重命名') }}</span></button>
            <button class="swipe-action-btn delete" @click.stop="deleteRoom(r)"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg><span>{{ tr('删除') }}</span></button>
          </div>
        </div>
        <div v-if="!visibleConversations.length" class="empty">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>
          <p>{{ tr(filter ? '没有匹配的对话' : '还没有对话') }}</p><p v-if="!filter">{{ tr('点击右上角 + 创建') }}</p>
        </div>
      </template>
    </div>

    </div>
    <Teleport to="body">
      <div v-if="projectCreateOpen" class="rename-overlay" @click.self="!projectCreateBusy && (projectCreateOpen = false)" @keydown.esc="!projectCreateBusy && (projectCreateOpen = false)">
        <form class="rename-modal" role="dialog" aria-modal="true" aria-labelledby="create-project-title" @submit.prevent="submitCreateProject">
          <h4 id="create-project-title">{{ tr('新建项目') }}</h4>
          <input ref="projectNameInput" v-model="projectCreateName" :disabled="projectCreateBusy" maxlength="100" :placeholder="tr('项目名称')" aria-label="项目名称" />
          <p v-if="projectCreateError" class="move-project-error" role="alert">{{ projectCreateError }}</p>
          <div class="rename-actions">
            <button type="button" class="btn-cancel" :disabled="projectCreateBusy" @click="projectCreateOpen = false">{{ tr('取消') }}</button>
            <button type="submit" class="btn-save" :disabled="projectCreateBusy || !projectCreateName.trim()">{{ projectCreateBusy ? tr('创建中...') : tr('创建') }}</button>
          </div>
        </form>
      </div>
    </Teleport>
    <Teleport to="body">
      <div v-if="batchDeleteOpen" class="delete-confirm-overlay" @click.self="batchDeleteOpen = false">
        <div class="delete-confirm-modal" role="dialog" aria-modal="true">
          <div class="delete-confirm-icon" aria-hidden="true">!</div>
          <h4>{{ tr('批量删除') }} {{ selectedIds.size }} {{ tr('项') }}</h4>
          <p>删除会话会清除所选群聊或私信记录，无法撤销。你也可以同时删除所选私信对应的智能体；个人助手不会被删除。</p>
          <div class="batch-delete-options">
            <label><input v-model="deleteDmAgents" type="checkbox"> 同时删除私信对应智能体</label>
          </div>
          <div class="delete-confirm-actions">
            <button class="btn-cancel" @click="batchDeleteOpen = false">{{ tr('取消') }}</button>
            <button class="btn btn-danger" :disabled="batchDeleting" @click="confirmBatchDelete">{{ batchDeleting ? tr('删除中') : tr('确认删除') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="renamingRoom" class="rename-overlay" @click.self="renamingRoom = null">
        <div class="rename-modal">
          <h4>{{ tr('重命名对话') }}</h4>
          <input v-model="renameText" @keydown.enter="confirmRename" :placeholder="tr('输入新名称')" autofocus />
          <div class="rename-actions">
            <button class="btn-cancel" @click="renamingRoom = null">{{ tr('取消') }}</button>
            <button class="btn-save" :disabled="!renameText.trim()" @click="confirmRename">{{ tr('确定') }}</button>
          </div>
        </div>
      </div>
    </Teleport>

    <Teleport to="body">
      <div
        v-if="roomContextMenu.show"
        class="room-context-menu"
        :style="{ left: roomContextMenu.x + 'px', top: roomContextMenu.y + 'px' }"
        @click.stop
        @contextmenu.prevent
      >
        <button class="room-context-menu-item" @click="runRoomContextAction('pin')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 17v5"/><path d="M5 17h14"/><path d="M7 17 9 3h6l2 14"/></svg>
          <span>{{ tr(isPinned(roomContextMenu.item?.id) ? '取消置顶' : '置顶') }}</span>
        </button>
        <button v-if="roomContextMenu.type === 'group'" class="room-context-menu-item" @click="runRoomContextAction('rename')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
          <span>{{ tr('重命名') }}</span>
        </button>
        <button class="room-context-menu-item" @click="runRoomContextAction('move')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 7h7l2 2h9v11H3zM12 13h6m-3-3 3 3-3 3"/></svg>
          <span>{{ tr('移动到项目') }}</span>
        </button>
        <div class="room-context-menu-divider"></div>
        <button class="room-context-menu-item danger" @click="runRoomContextAction('delete')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
          <span>{{ tr('删除') }}</span>
        </button>
      </div>
    </Teleport>

    <Teleport to="body">
      <div v-if="movingRoom" class="rename-overlay" @click.self="!moveBusy && (movingRoom = null)" @keydown.esc="!moveBusy && (movingRoom = null)">
        <div class="rename-modal" role="dialog" aria-modal="true" aria-labelledby="move-project-title">
          <h4 id="move-project-title">{{ tr('移动到项目') }}</h4>
          <p class="move-project-note">{{ movingRoom.name || movingRoom.agent?.name }}</p>
          <select v-model="moveProjectId" :disabled="moveBusy || moveLoading" class="move-project-select" aria-label="选择已有项目">
            <option value="">{{ moveLoading ? tr('加载中...') : tr('请选择项目') }}</option>
            <option v-for="project in projects" :key="project.id" :value="project.id">{{ project.name }}</option>
          </select>
          <p v-if="moveError" role="alert" class="move-project-error">{{ moveError }}</p>
          <p v-else-if="!moveLoading && !projects.length" class="move-project-note">{{ tr('暂无项目，请先创建项目') }}</p>
          <div class="rename-actions">
            <button class="btn-cancel" :disabled="moveBusy" @click="movingRoom = null">{{ tr('取消') }}</button>
            <button class="btn-save" :disabled="moveBusy || moveLoading || !moveProjectId" @click="confirmMoveProject">{{ moveBusy ? tr('移动中...') : tr('移动') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
    <Teleport to="body">
      <div v-if="deletingRoom" class="delete-confirm-overlay" @click.self="closeDeleteConfirm">
        <div class="delete-confirm-modal" role="dialog" aria-modal="true" aria-labelledby="delete-room-title">
          <div class="delete-confirm-icon" aria-hidden="true">!</div>
          <h4 id="delete-room-title">{{ tr('确认删除对话？') }}</h4>
          <p>{{ tr('即将删除') }}「{{ deletingRoomName }}」。{{ tr('消息将被清除，此操作不可撤销，请确认是否继续。') }}</p>
          <div class="delete-confirm-actions">
            <button class="btn-cancel" @click="closeDeleteConfirm">{{ tr('取消') }}</button>
            <button class="btn btn-danger" @click="confirmDeleteRoom">{{ tr('确认删除') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, inject, onMounted, onUnmounted , watch, nextTick } from 'vue'
import { store, api, loadConversations, loadAgents, getAgentColor, getAgentIcon, togglePinnedConversation } from '../store.js'
import { translateText, tr as translate } from '../i18n.js'

const emit = defineEmits(['open-chat', 'create-room', 'create-project', 'conversations-deleted'])
const props = defineProps({ assistantName: String, orchestratorAgentId: String })

const filter = ref('')
const msgResults = ref([])
const msgSearching = ref(false)
let msgSearchTimer = null
function escapeHtmlS(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))
}
function hl(s) {
  const q = String(filter.value || '').trim()
  const safe = escapeHtmlS(s)
  if (!q) return safe
  const parts = safe.split(new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi'))
  return parts.map(p => p.toLowerCase() === q.toLowerCase() ? '<mark>' + p + '</mark>' : p).join('')
}
async function runMsgSearch(q) {
  if (!q || q.length < 2) { msgResults.value = []; return }
  msgSearching.value = true
  try {
    const res = await api('GET', '/admin/search?q=' + encodeURIComponent(q) + '&limit=30')
    msgResults.value = res?.ok ? (res.result || []) : []
  } catch { msgResults.value = [] }
  finally { msgSearching.value = false }
}
watch(filter, (v) => {
  clearTimeout(msgSearchTimer)
  msgSearchTimer = setTimeout(() => runMsgSearch(String(v || '').trim()), 300)
})
function openMsgResult(r) {
  emit('open-chat', { id: r.room_id, name: r.room_name }, 'group')
}


const isDesktop = inject('isDesktop', ref(false))
const agentIndex = (id) => store.agents.findIndex(a => a.id === id)
const renamingRoom = ref(null)
const renameText = ref('')
const deletingRoom = ref(null)
const roomContextMenu = ref({ show: false, x: 0, y: 0, item: null, type: null })
const selectionMode = ref(false)
const selectedIds = reactive(new Set())
const batchDeleteOpen = ref(false)
const batchDeleting = ref(false)
const deleteDmAgents = ref(false)
const sortOptions = [
  { key: 'lastTime', label: '最后对话' },
  { key: 'name', label: '聊天框名' },
  { key: 'createdAt', label: '创建时间' },
]
const sortBy = ref(localStorage.getItem('chat_sort_by') || 'lastTime')
const sortDesc = ref(localStorage.getItem('chat_sort_desc') !== 'false')
const lastClickedSort = ref(sortBy.value)

function tr(value, params) { return translate(value, params) }
function trMemberCount(count) { return tr('{count} 个成员').replace('{count}', count) }

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

const sortedConversations = computed(() => {
  const conversations = [
    ...store.rooms.map(room => ({ ...room, conversationType: 'group' })),
    ...store.dms.map(dm => ({ ...dm, conversationType: 'dm' })),
  ].filter(r => matchesSearch([
    r.name,
    r.agent?.name,
    r.agent?.description,
    r.last_message?.text,
    r.last_message?.sender_name,
    ...(r.members || []).map(member => member?.name || member?.agent_name || member?.display_name || member?.id),
  ]))
  return sortConversations(conversations)
})
const loadingConversations = computed(() => !store.initialized)
const pinnedConversations = computed(() => sortedConversations.value.filter(r => isPinned(r.id)))
function roomSettingsOf(room) {
  try { return typeof room.settings_json === 'string' ? JSON.parse(room.settings_json || '{}') : (room.settings_json || {}) } catch { return {} }
}
const projectCreateOpen = ref(false), projectCreateBusy = ref(false), projectCreateName = ref(''), projectCreateError = ref(''), projectNameInput = ref(null)
async function openCreateProject() {
  projectCreateName.value = ''; projectCreateError.value = ''; projectCreateOpen.value = true
  await nextTick(); projectNameInput.value?.focus()
}
async function submitCreateProject() {
  if (projectCreateBusy.value || !projectCreateName.value.trim()) return
  projectCreateBusy.value = true; projectCreateError.value = ''
  try {
    const result = await api('POST', '/admin/projects', { name: projectCreateName.value.trim() })
    if (!result?.ok) throw Error(result?.error || '创建项目失败')
    projects.value = [result.result, ...projects.value.filter(p => p.id !== result.result.id)]
    expandedProjects[result.result.id] = true
    projectCreateOpen.value = false
  } catch (e) { projectCreateError.value = e.message }
  finally { projectCreateBusy.value = false }
}
defineExpose({ openCreateProject })
const projects = ref([])
const expandedProjects = reactive({})
let rememberProjects = []
try { const saved = JSON.parse(localStorage.getItem('myna_expanded_projects') || '[]'); if (Array.isArray(saved)) rememberProjects = saved } catch {}
async function loadProjects() {
  const result = await api('GET', '/admin/projects')
  if (result?.ok) {
    projects.value = result.result || []
    for (const project of projects.value) if (!(project.id in expandedProjects)) expandedProjects[project.id] = rememberProjects.includes(project.id)
  }
}
function toggleProject(id) {
  expandedProjects[id] = !expandedProjects[id]
  localStorage.setItem('myna_expanded_projects', JSON.stringify(Object.keys(expandedProjects).filter(key => expandedProjects[key])))
}
function projectChats(projectId) { return sortedConversations.value.filter(r => roomSettingsOf(r).project_id === projectId || (r.id === projectId && r.last_message)) }
async function startProjectChat(project) {
  const result = await api('POST', '/admin/collaboration/planning-room', { task: '', mode: 'conversation', is_chat: true, project_id: project.id })
  if (!result?.ok) { window.alert(result?.error || tr('创建对话失败')); return }
  await loadConversations({ force: true })
  await loadProjects()
  emit('open-chat', { ...result.result, members: result.result.members || [] }, 'group')
}
const visibleConversations = computed(() => sortedConversations.value.filter(r => !isPinned(r.id) && !roomSettingsOf(r).project_id && !roomSettingsOf(r).is_project))
const selectableConversations = computed(() => {
  // Only rows the user can currently see; project containers are never deletable here.
  const items = [...pinnedConversations.value, ...visibleConversations.value]
  for (const project of projects.value) {
    if (expandedProjects[project.id]) items.push(...projectChats(project.id))
  }
  const seen = new Set()
  return items.filter(item => {
    if (roomSettingsOf(item).is_project || seen.has(item.id)) return false
    seen.add(item.id)
    return true
  })
})
const allSelected = computed(() => selectableConversations.value.length > 0 && selectableConversations.value.every(item => selectedIds.has(item.id)))
function toggleSelectionMode() {
  selectionMode.value = !selectionMode.value
  selectedIds.clear()
  batchDeleteOpen.value = false
}
function toggleSelectAll() {
  if (allSelected.value) selectedIds.clear()
  else selectableConversations.value.forEach(item => selectedIds.add(item.id))
}
async function confirmBatchDelete() {
  const items = sortedConversations.value.filter(item => selectedIds.has(item.id)).map(item => ({ id: item.id, type: item.conversationType }))
  if (!items.length || batchDeleting.value) return
  batchDeleting.value = true
  const result = await api('POST', '/admin/conversations/batch-delete', { items, delete_dm_agents: deleteDmAgents.value })
  batchDeleting.value = false
  if (!result?.ok) {
    window.alert(result?.error || tr('删除失败'))
    return
  }
  const deletedIds = items.map(item => item.id)
  batchDeleteOpen.value = false
  selectionMode.value = false
  selectedIds.clear()
  deleteDmAgents.value = false
  await loadConversations({ force: true })
  await loadAgents({ force: true })
  emit('conversations-deleted', deletedIds)
}
function conversationPreview(item) {
  if (item.last_message?.text) {
    const sender = item.conversationType === 'group' && item.last_message.sender_name ? item.last_message.sender_name + ': ' : ''
    const text = String(item.last_message.text).replace(/<!--myna-assistant:(?:fast|expert):(?:0(?:\.\d+)?|1(?:\.0+)?)-->\s*/i, '')
    return sender + text.slice(0, 30)
  }
  return item.conversationType === 'dm' ? tr('开始对话') : trMemberCount(item.members?.length || 0)
}
function conversationName(item) {
  if (item.conversationType !== 'dm') return item.name
  if (item.agent?.id && item.agent.id === props.orchestratorAgentId) return props.assistantName || item.agent?.name || tr('未知')
  return item.agent?.name || tr('未知')
}
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
function isPinned(roomId) { return Boolean(store.pinnedConversations[roomId]) }

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
  if (date >= yesterday) return tr('昨天') + ' ' + timePart
  if (date.getFullYear() === now.getFullYear()) return tr('{month}月{day}日', { month: date.getMonth() + 1, day: date.getDate() }) + ' ' + timePart
  return tr('{year}年{month}月{day}日', { year: date.getFullYear(), month: date.getMonth() + 1, day: date.getDate() }) + ' ' + timePart
}

function startRename(room) { renamingRoom.value = room; renameText.value = room.name || '' }
async function confirmRename() {
  if (!renameText.value.trim() || !renamingRoom.value) return
  await api('PUT', `/admin/rooms/${renamingRoom.value.id}`, { name: renameText.value.trim() })
  renamingRoom.value.name = renameText.value.trim()
  renamingRoom.value = null
}
const deletingRoomName = computed(() => deletingRoom.value?.name || deletingRoom.value?.agent?.name || tr('此对话'))

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
  const result = await api('DELETE', `/admin/rooms/${roomId}`)
  if (!result?.ok) {
    window.alert(result?.error || tr('删除失败'))
    return
  }
  await loadConversations({ force: true })
  emit('conversations-deleted', [roomId])
}
function togglePin(room) {
  if (!room) return
  togglePinnedConversation(room.id)
  closeAllSwipes()
}

function closeRoomContextMenu() {
  roomContextMenu.value = { show: false, x: 0, y: 0, item: null, type: null }
  document.removeEventListener('click', closeRoomContextMenu)
  document.removeEventListener('scroll', closeRoomContextMenu, true)
}

function isDesktopPointer() {
  return window.innerWidth >= 768
}

function openRoomContextMenu(e, item, type) {
  if (!item || !isDesktopPointer()) return
  e.preventDefault()
  e.stopPropagation()
  closeAllSwipes()
  const menuWidth = 168
  const menuMaxHeight = type === 'group' ? 198 : 156
  const margin = 8
  const x = Math.min(Math.max(e.clientX, margin), window.innerWidth - menuWidth - margin)
  const y = Math.min(Math.max(e.clientY, margin), window.innerHeight - menuMaxHeight - margin)
  roomContextMenu.value = { show: true, x, y, item, type }
  setTimeout(() => {
    document.addEventListener('click', closeRoomContextMenu, { once: true })
    document.addEventListener('scroll', closeRoomContextMenu, true)
  }, 0)
}

const movingRoom = ref(null), moveProjectId = ref(''), moveBusy = ref(false), moveLoading = ref(false), moveError = ref('')
async function openMoveProject(item) {
  movingRoom.value = item; moveProjectId.value = ''; moveError.value = ''; moveLoading.value = true
  try {
    const result = await api('GET', '/admin/projects')
    if (!result?.ok) throw Error(result?.error || '加载项目失败')
    projects.value = result.result || []
  } catch (e) { moveError.value = e.message }
  finally { moveLoading.value = false }
}
async function confirmMoveProject() {
  if (moveBusy.value || !movingRoom.value || !moveProjectId.value) return
  const roomId = movingRoom.value.id, projectId = moveProjectId.value
  moveBusy.value = true; moveError.value = ''
  try {
    const result = await api('POST', '/admin/rooms/' + encodeURIComponent(roomId) + '/project', { project_id: projectId })
    if (!result?.ok) throw Error(result?.error || '移动失败')
    await loadConversations({ force: true })
    expandedProjects[projectId] = true
    movingRoom.value = null
  } catch (e) { moveError.value = e.message }
  finally { moveBusy.value = false }
}

function runRoomContextAction(action) {
  const item = roomContextMenu.value.item
  const type = roomContextMenu.value.type
  if (!item) return
  closeRoomContextMenu()
  if (action === 'pin') togglePin(item)
  else if (action === 'rename' && type === 'group') startRename(item)
  else if (action === 'delete') deleteRoom(item)
  else if (action === 'move') openMoveProject(item)
}

function onItemClick(item, type) {
  if (selectionMode.value) {
    if (selectedIds.has(item.id)) selectedIds.delete(item.id)
    else selectedIds.add(item.id)
    return
  }
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


function onGlobalClick(e) {
  if (e.target && !e.target.closest('.chat-item-wrapper')) closeAllSwipes()
}

onMounted(() => {
  loadProjects()
  loadConversations()
  document.addEventListener('click', onGlobalClick)
})
onUnmounted(() => { document.removeEventListener('click', onGlobalClick); closeRoomContextMenu() })
</script>

<style scoped>
.unread-badge { background:var(--accent); color:#fff; font-size:11px; min-width:18px; height:18px; border-radius:50%; display:flex; align-items:center; justify-content:center; font-weight:700; }
.sort-bar { display:flex; align-items:center; gap:6px; padding:8px 16px; border-bottom:1px solid var(--border); }
.sort-spacer { flex:1; }
.selection-toggle { width:28px;height:28px;padding:5px;border:1px solid var(--border);border-radius:7px;background:var(--bg);color:var(--text-dim);cursor:pointer;display:grid;place-items:center; }
.selection-toggle svg { width:16px;height:16px; }.selection-toggle.active { color:var(--accent);border-color:var(--accent);background:color-mix(in srgb,var(--accent) 10%,transparent); }
.selection-bar { display:flex;align-items:center;gap:10px;padding:8px 16px;background:color-mix(in srgb,var(--accent) 7%,var(--bg));border-bottom:1px solid var(--border);font-size:12px;color:var(--text-dim); }
.selection-bar button { border:0;background:transparent;color:var(--accent);font-weight:700;cursor:pointer;padding:4px; }.selection-bar .selection-delete { margin-left:auto;color:var(--danger); }.selection-bar button:disabled{opacity:.4}
.conversation-checkbox { width:19px;height:19px;flex:0 0 19px;border:1.5px solid var(--border);border-radius:6px;display:grid;place-items:center;margin-top:8px;color:#fff;box-sizing:border-box; }.conversation-checkbox.checked{background:var(--accent);border-color:var(--accent)}.conversation-checkbox svg{width:13px;height:13px}
.sort-label { color:var(--text-dim); font-size:12px; }
.sort-btn { border:1px solid var(--border); border-radius:var(--radius-sm); background:var(--bg); color:var(--text-dim); cursor:pointer; font-size:12px; padding:5px 9px; transition:all .15s ease; }
.sort-btn.active,.sort-btn:hover { border-color:var(--accent); color:var(--accent); }
.sort-btn.active { background:color-mix(in srgb,var(--accent) 12%,transparent); }

.chat-item-wrapper { position:relative; overflow:hidden; }
.chat-item { position:relative; display:flex; align-items:flex-start; padding:12px 16px; gap:12px; background:var(--bg); transition:transform .3s cubic-bezier(.25,.46,.45,.94), background .18s ease; cursor:pointer; z-index:1; }
.chat-item.pinned { background:color-mix(in srgb,var(--surface,#f3f4f6) 82%,var(--accent,#2d6a4f) 18%); }
.chat-item:active { background:var(--surface,rgba(0,0,0,.03)); }
.chat-item.pinned:active { background:color-mix(in srgb,var(--surface,#f3f4f6) 74%,var(--accent,#2d6a4f) 26%); }
.info { min-width:0; flex:1; overflow:hidden; display:flex; flex-direction:column; gap:3px; }
.name,.preview {
  min-width:0;
  max-width:100%;
  overflow:hidden;
  white-space:nowrap;
  overflow-wrap:normal;
  word-break:normal;
  display:block;
  text-overflow:ellipsis;
}
.name { line-height:1.28; }
.preview { line-height:1.35; }
.meta { flex-shrink:0; align-self:flex-start; }

.swipe-actions { position:absolute; right:0; top:0; bottom:0; display:flex; z-index:0; }
.swipe-action-btn { display:flex; flex-direction:column; align-items:center; justify-content:center; gap:3px; width:70px; height:100%; border:none; color:#fff; font-size:11px; font-weight:500; cursor:pointer; }
.swipe-action-btn:active { opacity:.8; }
.swipe-action-btn.pin { background:var(--accent,#2d6a4f); }
.swipe-action-btn.pin.active { background:#2563eb; }
.swipe-action-btn.rename { background:#f59e0b; }
.swipe-action-btn.delete { background:var(--danger,#e53e3e); }


.room-context-menu {
  position: fixed;
  z-index: 2200;
  width: 168px;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface, var(--bg));
  color: var(--text);
  box-shadow: 0 12px 36px rgba(0,0,0,.18);
}
.room-context-menu-item {
  width: 100%;
  min-height: 34px;
  padding: 7px 9px;
  border: 0;
  border-radius: 8px;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 13px;
  line-height: 1.2;
  text-align: left;
  white-space: nowrap;
}
.room-context-menu-item svg {
  width: 15px;
  height: 15px;
  flex: 0 0 auto;
  color: var(--text-dim);
}
.room-context-menu-item:hover { background: var(--surface2); }
.room-context-menu-item.danger { color: var(--danger,#e53e3e); }
.room-context-menu-item.danger svg { color: currentColor; }
.room-context-menu-item.danger:hover { background: rgba(220,38,38,.1); }
.room-context-menu-divider { height: 1px; margin: 5px 4px; background: var(--border); }
@media (max-width: 767px), (hover: none), (pointer: coarse) {
  .room-context-menu { display: none; }
}
@media (min-width: 768px) and (hover: hover) and (pointer: fine) {
  .swipe-actions { display: none; }
}

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
.batch-delete-options { margin-top:16px;padding:11px 12px;border-radius:10px;background:var(--surface);text-align:left;color:var(--text-2);font-size:13px; }.batch-delete-options label{display:flex;align-items:center;gap:8px;cursor:pointer}.batch-delete-options input{accent-color:var(--accent)}
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
.move-project-select{width:100%;padding:10px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface);color:var(--text);font:inherit;font-size:13px}.move-project-note{margin:0 0 12px;font-size:12px;color:var(--text-dim);overflow-wrap:anywhere}.move-project-error{margin-top:10px;color:var(--danger);font-size:12px}
.sidebar-section-heading button{display:inline-flex;align-items:center;justify-content:center;width:30px;height:30px;border:1px solid transparent;border-radius:var(--radius-sm);background:transparent;color:var(--text-2);font:inherit;font-size:22px;cursor:pointer}.sidebar-section-heading button:hover{background:var(--surface2);color:var(--accent);border-color:var(--border)}
</style>

<template>
  <div class="app">
    <div class="app-inner">
      <ChatList v-if="page === 'chats'" @open-chat="openChat" @create-room="showModal('room')" />
      <AgentList v-if="page === 'agents'" @open-detail="openAgentDetail" @create-agent="showModal('agent')" />
      <SettingsPage v-if="page === 'settings'" />
      <ChatView v-if="currentRoom" :room="currentRoom" :type="currentRoomType" @close="closeChat" />
      <AgentDetail v-if="currentAgent" :agent="currentAgent" @close="currentAgent = null" @delete="deleteAgent" />
    </div>
    <div class="bottom-nav" v-if="!currentRoom && !currentAgent">
      <div class="nav-item" :class="{ active: page === 'chats' }" @click="page = 'chats'">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
        <span class="label">消息</span>
      </div>
      <div class="nav-item" :class="{ active: page === 'agents' }" @click="page = 'agents'">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>
        <span class="label">智能体</span>
      </div>
      <div class="nav-item" :class="{ active: page === 'settings' }" @click="page = 'settings'">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <span class="label">设置</span>
      </div>
    </div>
    <RoomModal v-if="modals.room" @close="modals.room = false" @created="onRoomCreated" />
    <AgentModal v-if="modals.agent" @close="modals.agent = false" @created="onAgentCreated" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, provide } from 'vue'
import ChatList from './components/ChatList.vue'
import ChatView from './components/ChatView.vue'
import AgentList from './components/AgentList.vue'
import AgentDetail from './components/AgentDetail.vue'
import SettingsPage from './components/SettingsPage.vue'
import RoomModal from './components/RoomModal.vue'
import AgentModal from './components/AgentModal.vue'
import { api, ws } from './store.js'

const page = ref('chats')
const currentRoom = ref(null)
const currentRoomType = ref('group')
const currentAgent = ref(null)
const modals = reactive({ room: false, agent: false })

provide('page', page)

function openChat(room, type) {
  currentRoom.value = room
  currentRoomType.value = type
  // Push history state so mobile back button works
  history.pushState({ view: 'chat', roomId: room.id }, '', `#chat/${room.id}`)
}

function closeChat() {
  currentRoom.value = null
  // Replace state to list view
  history.replaceState({ view: 'list' }, '', '#')
}

function openAgentDetail(agent) {
  currentAgent.value = agent
  history.pushState({ view: 'agent', agentId: agent.id }, '', `#agent/${agent.id}`)
}

// Handle browser back button (mobile)
function onPopState(e) {
  if (currentRoom.value) {
    currentRoom.value = null
  } else if (currentAgent.value) {
    currentAgent.value = null
  }
}

function showModal(name) { modals[name] = true }

function onRoomCreated(room) {
  modals.room = false
  openChat(room, 'group')
}

function onAgentCreated(agent) {
  modals.agent = false
}

async function deleteAgent(id) {
  await api('DELETE', `/admin/agents/${id}`)
  currentAgent.value = null
}

onMounted(() => {
  ws.connect()
  // Init theme
  const dark = localStorage.getItem('hub-theme') === 'dark'
  if (dark) document.documentElement.setAttribute('data-theme', 'dark')
  // Listen for back button
  window.addEventListener('popstate', onPopState)
  // Set initial state
  history.replaceState({ view: 'list' }, '', '#')
})

onUnmounted(() => {
  window.removeEventListener('popstate', onPopState)
})
</script>

<template>
  <!-- Login gate -->
  <LoginPage v-if="!isAuthenticated" @authenticated="onAuthenticated" />

  <div v-else class="app" :class="{ 'desktop-layout': isDesktop }">
    <!-- Desktop sidebar (icon bar) -->
    <div class="desktop-sidebar" v-if="isDesktop">
      <div class="sidebar-icon" :class="{ active: page === 'assistant' }" @click="openAssistantHome" :title="tr('首页')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3a6 6 0 0 0-6 6v2a4 4 0 0 1-2 3.46V17h16v-2.54A4 4 0 0 1 18 11V9a6 6 0 0 0-6-6Z"/><path d="M9 21h6"/><path d="M9 10h.01M15 10h.01"/></svg>
      </div>
      
      
      <div class="sidebar-icon" :class="{ active: page === 'agents' }" @click="page = 'agents'" :title="tr('智能体')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>
      </div>

      <div class="sidebar-icon" :class="{ active: page === 'admin' }" @click="page = 'admin'" :title="tr('管理中心')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
      </div>
      <div class="sidebar-icon" :class="{ active: page === 'settings' }" @click="page = 'settings'" :title="tr('设置')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
        <span v-if="updateInfo.available" class="red-dot"></span>
      </div>
    </div>

    <template v-if="isDesktop">
      <template v-if="page === 'assistant' || page === 'chats'">
        <div class="desktop-list-panel" :style="{ width: listW + 'px' }">
          <ChatList ref="homeChatList" :assistant-name="assistantName" :orchestrator-agent-id="orchestratorAgentId" @open-chat="openChat" @create-room="openAssistantHome" @create-project="manageHomeProjects(true)" @conversations-deleted="onConversationsDeleted" />
        </div>
        <div class="panel-drag-handle" :class="{ active: dragging === 'list' }" @pointerdown="startDrag($event, 'list')"></div>
        <div class="desktop-chat-panel">
          <AssistantHome v-if="page === 'assistant'" :assistant-name="assistantName" @renamed="assistantName = $event" @start-chat="startAssistantChat" @open-history="mobileHistoryOpen = true" @manage-projects="manageHomeProjects" @open-project="openProject" />
          <ChatView v-else-if="currentRoom" :key="`${currentRoom.id}-${pendingAssistantPromptId}`" :room="currentRoom" :type="currentRoomType" :display-name="isOrchestratorRoom(currentRoom) ? assistantName : ''" :initial-prompt="pendingAssistantPrompt" @prompt-consumed="pendingAssistantPrompt = ''" @close="closeChat" @open-chat="openChat" />
          <div v-else class="desktop-empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" width="48" height="48"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
            <p>{{ tr('选择一个对话开始聊天') }}</p>
          </div>
        </div>
        <div v-if="artifact.open" class="panel-drag-handle" :class="{ active: dragging === 'artifact' }" @pointerdown="startDrag($event, 'artifact')"></div>
        <div v-if="artifact.open" class="desktop-artifact-panel" :style="{ width: artW + 'px' }">
          <ArtifactPanel />
        </div>
      </template>

      <!-- Agents use a wider list and dedicated detail pane. -->
      <template v-else-if="page === 'agents'">
        <div class="desktop-agent-list-panel">
          <AgentList :selected-id="currentAgent?.id" @open-detail="openAgentDetail" @create-agent="showModal('agent')" @deleted-agent="onAgentDeleted" />
        </div>
        <div class="desktop-agent-detail-panel">
          <AgentDetail v-if="currentAgent" :key="currentAgent.id" :agent="currentAgent" @close="currentAgent = null" @delete="deleteAgent" />
          <div v-else class="desktop-empty-state agent-empty-state">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" width="48" height="48"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>
            <p>{{ tr('选择一个智能体查看配置') }}</p>
          </div>
        </div>
      </template>

      <!-- Projects page -->
      <template v-else-if="page === 'projects'">
        <div class="desktop-list-panel" :style="{ width: listW + 'px' }">
          <ProjectsView :create-on-open="createProjectOnOpen" @open-project="openProjectTask" />
        </div>
        <div class="desktop-chat-panel">
          <ChatView v-if="currentRoom" :key="currentRoom.id" :room="currentRoom" type="group" @close="closeChat" @open-chat="openProjectTask" />
          <div v-else class="desktop-empty-state"><p>{{ tr('选择项目中的任务') }}</p></div>
        </div>
        <div v-if="artifact.open" class="desktop-artifact-panel" :style="{ width: artW + 'px' }"><ArtifactPanel /></div>
      </template>

      <!-- Admin and Settings should use the full desktop workspace. -->
      <div v-else class="desktop-workspace-panel">
        <AdminCenter v-if="page === 'admin'" />
        <SettingsPage v-if="page === 'settings'" @open-room="openSettingsRoom" />
      </div>
    </template>

    <!-- Mobile layout (original) -->
    <template v-if="!isDesktop">
      <div class="app-inner">
        <ProjectsView v-if="page === 'projects'" :create-on-open="createProjectOnOpen" @open-project="openProjectTask" />
        <AssistantHome v-if="page === 'assistant'" :assistant-name="assistantName" @renamed="assistantName = $event" @start-chat="startAssistantChat" @open-history="mobileHistoryOpen = true" @manage-projects="manageHomeProjects" @open-project="openProject" @open-project-file="openProjectFile" />
        <ChatList v-if="page === 'chats'" :assistant-name="assistantName" :orchestrator-agent-id="orchestratorAgentId" @open-chat="openChat" @create-room="openAssistantHome" @create-project="manageHomeProjects(true)" @conversations-deleted="onConversationsDeleted" />
        <AgentList v-if="page === 'agents'" @open-detail="openAgentDetail" @create-agent="showModal('agent')" @deleted-agent="onAgentDeleted" />
        <AdminCenter v-if="page === 'admin'" />
        <SettingsPage v-if="page === 'settings'" @open-room="openSettingsRoom" />
        <ChatView v-if="currentRoom" :key="`${currentRoom.id}-${pendingAssistantPromptId}`" :room="currentRoom" :type="currentRoomType" :display-name="isOrchestratorRoom(currentRoom) ? assistantName : ''" :initial-prompt="pendingAssistantPrompt" @prompt-consumed="pendingAssistantPrompt = ''" @close="closeChat" @open-chat="openChat" />
        <AgentDetail v-if="currentAgent" :key="currentAgent.id" :agent="currentAgent" @close="currentAgent = null" @delete="deleteAgent" />
        <ArtifactPanel v-if="!isDesktop && artifact.open" :mobile="true" />
      </div>
      <div class="bottom-nav" v-if="!currentRoom && !currentAgent">
        <div class="nav-item" :class="{ active: page === 'assistant' }" @click="openAssistantHome">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 3a6 6 0 0 0-6 6v2a4 4 0 0 1-2 3.46V17h16v-2.54A4 4 0 0 1 18 11V9a6 6 0 0 0-6-6Z"/><path d="M9 21h6"/></svg>
          <span class="label">{{ tr('首页') }}</span>
        </div>
        
        
        <div class="nav-item" :class="{ active: page === 'agents' }" @click="page = 'agents'">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>
          <span class="label">{{ tr('智能体') }}</span>
        </div>

        <div class="nav-item" :class="{ active: page === 'admin' }" @click="page = 'admin'">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/></svg>
          <span class="label">{{ tr('管理') }}</span>
        </div>
        <div class="nav-item" :class="{ active: page === 'settings' }" @click="page = 'settings'">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>
          <span class="label">{{ tr('设置') }}</span>
          <span v-if="updateInfo.available" class="red-dot"></span>
        </div>
      </div>
    </template>

    <Teleport to="body">
      <div v-if="!isDesktop && mobileHistoryOpen" class="mobile-history-backdrop" @click.self="mobileHistoryOpen = false" @keydown.esc="mobileHistoryOpen = false">
        <aside class="mobile-history-drawer" role="dialog" aria-modal="true" aria-label="历史对话">
          <ChatList ref="mobileChatList" :assistant-name="assistantName" :orchestrator-agent-id="orchestratorAgentId" @open-chat="openChat" @create-room="openAssistantHome" @create-project="mobileHistoryOpen = false; manageHomeProjects(true)" @conversations-deleted="onConversationsDeleted">
            <template #header-actions><button @click="mobileHistoryOpen = false" aria-label="关闭历史对话">×</button></template>
          </ChatList>
        </aside>
      </div>
    </Teleport>
    <RoomModal v-if="modals.room" @close="modals.room = false" @created="onRoomCreated" />
    <AgentModal v-if="modals.agent" @close="modals.agent = false" @created="onAgentCreated" />
  </div>

</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, provide, computed, watch, nextTick, defineAsyncComponent } from 'vue'
import ChatList from './components/ChatList.vue'
import ChatView from './components/ChatView.vue'
import ArtifactPanel from './components/ArtifactPanel.vue'
import { artifact, openArtifact } from './store.js'
import AssistantHome from './AssistantHome.vue'
import RoomModal from './components/RoomModal.vue'
import LoginPage from './components/LoginPage.vue'

const AgentList = defineAsyncComponent(() => import('./components/AgentList.vue'))
const AgentDetail = defineAsyncComponent(() => import('./components/AgentDetail.vue'))
const SettingsPage = defineAsyncComponent(() => import('./components/SettingsPage.vue'))
const AdminCenter = defineAsyncComponent(() => import('./components/AdminCenter.vue'))
const ProjectsView = defineAsyncComponent(() => import('./components/ProjectsView.vue'))
const AgentModal = defineAsyncComponent(() => import('./components/AgentModal.vue'))
import { api, ws, auth, setAuthToken, clearAuth, updateInfo, checkForUpdate, store, loadConversations, loadAgents } from './store.js'
import { initI18n, tr } from './i18n.js'

const isAuthenticated = ref(false)
const page = ref('assistant')
const currentRoom = ref(null)
const mobileHistoryOpen = ref(false)
const currentRoomType = ref('group')
const currentAgent = ref(null)
const modals = reactive({ room: false, agent: false })
const defaultEntryOpened = ref(false)
const defaultEntryDismissed = ref(false)
const assistantName = ref('马哥')
const orchestratorAgentId = ref('')
const pendingAssistantPrompt = ref('')
const pendingAssistantPromptId = ref(0)
const pendingShareToken = ref(new URLSearchParams(window.location.search).get('continue_share') || sessionStorage.getItem('myna_continue_share') || '')
if (pendingShareToken.value) sessionStorage.setItem('myna_continue_share', pendingShareToken.value)

// Desktop detection (reactive)
const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 0)
const isDesktop = computed(() => windowWidth.value >= 768)

function onResize() {
  windowWidth.value = window.innerWidth
}


provide('page', page)
provide('isDesktop', isDesktop)

// Fix page overlap: clear opposite panel when switching pages
watch(page, (newPage) => {
  if (newPage === 'agents') currentRoom.value = null
  else if (newPage === 'chats') currentAgent.value = null
  else { currentRoom.value = null; currentAgent.value = null }
})

function openAssistantHome() {
  mobileHistoryOpen.value = false
  currentRoom.value = null
  currentAgent.value = null
  page.value = 'assistant'
  history.replaceState({ view: 'assistant' }, '', '#')
}

function isOrchestratorRoom(room) {
  return room?.agent?.id && room.agent.id === orchestratorAgentId.value
}

async function loadAssistantPreferences() {
  const result = await api('GET', '/admin/personal-assistant/preferences')
  if (result?.ok && result.result?.name) assistantName.value = result.result.name
  if (!store.agents.length) await loadAgents()
  const orchestrator = store.agents.find(item => item.name === '马哥') || store.agents.find(item => /统筹|协同/.test(item.name || item.description || ''))
  if (orchestrator) orchestratorAgentId.value = orchestrator.id
}

async function resolveOrchestratorRoom() {
  if (!store.agents.length) await loadAgents()
  let agent = orchestratorAgentId.value ? store.agents.find(item => item.id === orchestratorAgentId.value) : null
  if (!agent) agent = store.agents.find(item => item.name === '马哥')
  if (!agent) return null
  orchestratorAgentId.value = agent.id
  const dm = await api('POST', `/admin/dm/${agent.id}`)
  if (!dm?.ok || !dm.result?.room_id) return null
  await loadConversations({ force: true })
  return store.dms.find(item => item.id === dm.result.room_id) || null
}

async function startAssistantChat(options) {
  const prompt = String(options?.prompt || '').trim()
  const created = await api('POST', '/admin/collaboration/planning-room', { task: prompt, mode: options?.creationMode || 'work', is_chat: true })
  if (!created?.ok || !created.result?.id) return
  if (prompt) {
    const sent = await api('POST', `/admin/rooms/${created.result.id}/send`, { text: prompt, mentions: [] })
    if (sent?.ok === false) return
  }
  await loadConversations({ force: true })
  const room = store.rooms.find(item => item.id === created.result.id) || created.result
  pendingAssistantPrompt.value = ''
  pendingAssistantPromptId.value++
  page.value = 'chats'
  currentRoom.value = room
  currentRoomType.value = 'group'
  history.pushState({ view: 'chat', roomId: room.id }, '', `#chat/${room.id}`)
}

watch(() => store.initialized, (initialized) => {
  if (initialized && !currentRoom.value && /^#chat\//.test(window.location.hash)) {
    restoreRouteFromHash()
  }
})

function openChat(room, type) {
  mobileHistoryOpen.value = false
  page.value = 'chats'
  currentRoom.value = room
  currentRoomType.value = type
  // Push history state so mobile back button works
  history.pushState({ view: 'chat', roomId: room.id }, '', `#chat/${room.id}`)
}

function closeChat() {
  currentRoom.value = null
  defaultEntryDismissed.value = true
  // Replace state to list view
  history.replaceState({ view: 'list' }, '', '#')
}
function onConversationsDeleted(ids) {
  if (currentRoom.value && ids.includes(currentRoom.value.id)) currentRoom.value = null
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

const listW = ref(Number(localStorage.getItem('myna_list_w')) || 400)
const artW = ref(Number(localStorage.getItem('myna_art_w')) || 480)
const dragging = ref('')
function startDrag(e, which) {
  dragging.value = which
  const startX = e.clientX
  const startW = which === 'list' ? listW.value : artW.value
  const move = (ev) => {
    const delta = which === 'list' ? ev.clientX - startX : startX - ev.clientX
    const min = which === 'list' ? 280 : 320
    const max = which === 'list' ? 680 : 980
    const w = Math.max(min, Math.min(max, startW + delta))
    if (which === 'list') listW.value = w
    else artW.value = w
  }
  const up = () => {
    dragging.value = ''
    window.removeEventListener('pointermove', move)
    window.removeEventListener('pointerup', up)
    try {
      localStorage.setItem('myna_list_w', String(listW.value))
      localStorage.setItem('myna_art_w', String(artW.value))
    } catch {}
  }
  window.addEventListener('pointermove', move)
  window.addEventListener('pointerup', up)
}

function openSettingsRoom(room) {
  page.value = 'chats'
  openChat(room, 'group')
}

async function openDefaultEntryChat() {
  if (defaultEntryOpened.value || defaultEntryDismissed.value || currentRoom.value || currentAgent.value) return
  if (/^#(chat|agent)\//.test(window.location.hash)) return
  defaultEntryOpened.value = true
  try {
    if (!store.agents.length) await loadAgents()
    const settings = await api('GET', '/admin/settings')
    const configuredId = settings?.result?.orchestrator_agent_id || settings?.result?.default_orchestrator_agent_id || ''
    orchestratorAgentId.value = configuredId
    let agent = configuredId ? store.agents.find(a => a.id === configuredId) : null
    if (!agent) agent = store.agents.find(a => a.name === '马哥')
    if (!agent) agent = store.agents.find(a => /统筹|协同/.test(a.name || a.description || ''))
    if (!agent) return
    const dm = await api('POST', `/admin/dm/${agent.id}`)
    if (!dm.ok || !dm.result?.room_id) return
    await loadConversations({ force: true })
    const room = store.dms.find(item => item.id === dm.result.room_id)
    if (!room || currentRoom.value || defaultEntryDismissed.value) return
    page.value = 'chats'
    currentRoom.value = room
    currentRoomType.value = 'dm'
    history.replaceState({ view: 'default-chat', roomId: room.id }, '', '#')
  } catch (e) {
    console.warn('Failed to open default entry chat:', e)
  }
}


function onAgentCreated(agent) {
  modals.agent = false
}

function onAgentDeleted(agentId) {
  if (currentAgent.value?.id === agentId) {
    currentAgent.value = null
    if (window.location.hash === `#agent/${agentId}`) history.replaceState({ view: 'list' }, '', '#')
  }
}

async function onAuthenticated() {
  await Promise.all([loadConversations(), loadAgents()])
  isAuthenticated.value = true
  // Connect WS after auth
  ws.connect()
  restoreRouteFromHash()
  // Auto check for updates
  checkForUpdate()
  loadAssistantPreferences()
  if (!(await continueSharedConversation())) {
    if (!/^#(chat|agent)\//.test(window.location.hash)) openAssistantHome()
  }
}

async function continueSharedConversation() {
  const token = pendingShareToken.value
  if (!token) return false
  const result = await api('POST', `/admin/shares/${encodeURIComponent(token)}/continue`, {})
  if (!result?.ok || !result.result?.id) return false
  pendingShareToken.value = ''
  sessionStorage.removeItem('myna_continue_share')
  await loadConversations({ force: true })
  const room = store.rooms.find(item => item.id === result.result.id) || result.result
  page.value = 'chats'
  currentRoom.value = room
  currentRoomType.value = 'group'
  history.replaceState({ view: 'chat', roomId: room.id }, '', `#chat/${room.id}`)
  return true
}

async function checkAuth() {
  if (auth.token) {
    const res = await api('GET', '/auth/check')
    if (res.authenticated) {
      await Promise.all([loadConversations(), loadAgents()])
      isAuthenticated.value = true
      ws.connect()
      if (!(await continueSharedConversation())) restoreRouteFromHash()
      checkForUpdate()
      loadAssistantPreferences()
      return
    }
    clearAuth()
  }
  isAuthenticated.value = false
}

async function deleteAgent(id) {
  await api('DELETE', `/admin/agents/${id}`)
  currentAgent.value = null
}

async function restoreRouteFromHash() {
  const match = window.location.hash.match(/^#(chat|agent)\/([^?&]+)/)
  if (!match) {
    history.replaceState({ view: 'list' }, '', '#')
    openAssistantHome()
    return
  }

  const [, route, id] = match
  if (route === 'chat') {
    if (!store.initialized) await loadConversations()
    if (!store.rooms.length && !store.dms.length) await loadConversations()
    const room = [...store.rooms, ...store.dms].find(item => item.id === id)
    if (room) {
      page.value = 'chats'
      currentRoom.value = room
      currentRoomType.value = store.dms.some(item => item.id === id) ? 'dm' : 'group'
      history.replaceState({ view: 'chat', roomId: id }, '', `#chat/${id}`)
      return
    }
  }

  if (route === 'agent') {
    if (!store.agents.length) await loadAgents()
    const agent = store.agents.find(item => item.id === id)
    if (agent) {
      page.value = 'agents'
      currentAgent.value = agent
      history.replaceState({ view: 'agent', agentId: id }, '', `#agent/${id}`)
      return
    }
  }

  history.replaceState({ view: 'list' }, '', '#')
}

onMounted(() => {
  initI18n()
  // Init theme
  const dark = localStorage.getItem('hub-theme') === 'dark'
  if (dark) document.documentElement.setAttribute('data-theme', 'dark')
  // Check auth first, WS connects after auth
  checkAuth()
  // Listen for back button
  window.addEventListener('popstate', onPopState)
  // Listen for resize (desktop detection)
  window.addEventListener('resize', onResize)
  // Set initial state only when there is no deep link to restore after auth
  if (!pendingShareToken.value && !/^#(chat|agent)\//.test(window.location.hash)) {
    history.replaceState({ view: 'list' }, '', '#')
  }
})

onUnmounted(() => {
  window.removeEventListener('popstate', onPopState)
  window.removeEventListener('resize', onResize)
})

const createProjectOnOpen = ref(false)
const homeChatList = ref(null), mobileChatList = ref(null)
async function manageHomeProjects(create) {
  if (isDesktop.value) {
    if (page.value !== 'assistant' && page.value !== 'chats') openAssistantHome()
    await nextTick()
    if (create) homeChatList.value?.openCreateProject()
  } else {
    mobileHistoryOpen.value = true
    await nextTick()
    if (create) mobileChatList.value?.openCreateProject()
  }
}
function openProjectFile(room, file) {
  openArtifact({ name: file.name, path: file.path, url: file.url })
  openProject(room)
}
function openProjectTask(room) {
  page.value = 'chats'
  openChat(room, 'group')
}
function openProject(room) {
  page.value = 'chats'
  openChat(room, 'group')
}
</script>

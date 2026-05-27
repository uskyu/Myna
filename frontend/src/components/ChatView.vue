<template>
  <div class="chat-view active">
    <div class="chat-header">
      <button class="back-btn" @click="$emit('close')">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <span class="title">
        {{ title }}
        <span v-if="subtitle" style="font-size:12px;color:var(--text-dim);font-weight:400;margin-left:8px">{{ subtitle }}</span>
      </span>
      <button v-if="type === 'group'" class="more-btn" @click="showSettings = true">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>
      </button>
    </div>
    <div class="messages-area" ref="messagesArea">
      <template v-for="(group, gi) in messageGroups" :key="gi">
        <div v-if="group.separator" class="time-separator"><span>{{ group.separator }}</span></div>
        <div class="msg-group" :class="{ self: group.self }">
          <div v-for="(msg, mi) in group.messages" :key="msg.id || mi" class="msg" :class="{ self: group.self, streaming: msg.streaming }">
            <div v-if="msg.showName" class="sender-name">{{ msg.sender_name }}</div>
            <div class="msg-text" v-html="msg.streaming ? (msg.rendered + '<span class=stream-cursor>▊</span>') : msg.rendered"></div>
            <div class="msg-time">{{ msg.streaming ? '生成中...' : msg.time }}</div>
          </div>
        </div>
      </template>
      <div v-if="typingAgent" class="typing-indicator active">
        <span style="font-size:12px;color:var(--text-dim);margin-right:4px">{{ typingAgent }}</span>
        <div class="dots"><span></span><span></span><span></span></div>
      </div>
    </div>
    <div class="input-bar">
      <button class="at-btn" @click="triggerAt" title="@提及">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0V12a10 10 0 1 0-3.92 7.94"/></svg>
      </button>
      <textarea ref="inputEl" rows="1" placeholder="输入消息..." v-model="inputText" @keydown.enter.exact.prevent="send" @input="autoResize"></textarea>
      <button class="send-btn" @click="send">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'
import { store, api, ws, loadConversations, escapeHtml } from '../store.js'

const props = defineProps({ room: Object, type: String })
const emit = defineEmits(['close'])

const messagesArea = ref(null)
const inputEl = ref(null)
const inputText = ref('')
const messages = ref([])
const typingAgent = ref(null)
const showSettings = ref(false)
const streamingMessages = ref({}) // streamId -> { text, agentName }

let pollTimer = null

const title = computed(() => {
  if (props.type === 'dm') return props.room.agent?.name || '私聊'
  return props.room.name || '群聊'
})
const subtitle = computed(() => {
  if (props.type === 'group') return (props.room.members?.length || 0) + ' 个成员'
  return ''
})

// Render markdown
function renderMd(text) {
  if (!text) return ''
  try {
    marked.setOptions({ breaks: true, gfm: true })
    let html = marked.parse(text)
    html = html.replace(/<table>/g, '<div class="table-wrapper"><table>').replace(/<\/table>/g, '</table></div>')
    html = html.replace(/<img /g, '<img style="max-width:100%;max-height:300px;border-radius:8px;cursor:pointer;display:block;margin:4px 0" onclick="window.open(this.src)" ')
    return html
  } catch { return escapeHtml(text) }
}

// Message grouping - Vue reactivity handles diffing automatically
const messageGroups = computed(() => {
  const allMsgs = []
  // Existing messages from server
  messages.value.forEach(m => {
    const self = m.sender_id === 'user' || m.sender_id === 'system'
    allMsgs.push({
      id: m.id,
      sender_id: m.sender_id,
      sender_name: m.sender_name,
      text: m.text,
      rendered: self ? renderMd(m.text) : renderMd(m.text),
      time: (m.created_at || '').slice(11, 16),
      date: (m.created_at || '').slice(0, 10),
      self,
      showName: !self && props.type === 'group',
    })
  })
  // Streaming messages
  for (const sid in store.activeStreams) {
    const s = store.activeStreams[sid]
    if (s.roomId !== props.room.id) continue
    allMsgs.push({
      id: `stream-${sid}`,
      sender_id: s.agentId,
      sender_name: s.agentName,
      text: s.text,
      rendered: renderMd(s.text),
      time: '',
      date: '',
      self: false,
      showName: props.type === 'group',
      streaming: true,
    })
  }

  // Group by sender
  const groups = []
  let prevSender = null
  let prevDate = null
  for (const m of allMsgs) {
    if (m.date && prevDate && m.date !== prevDate) {
      groups.push({ separator: m.date, self: false, messages: [] })
    }
    if (m.sender_id !== prevSender) {
      groups.push({ self: m.self, messages: [m] })
    } else {
      groups[groups.length - 1].messages.push(m)
    }
    prevSender = m.sender_id
    prevDate = m.date
  }
  return groups
})

// Fetch messages
async function fetchMessages() {
  const data = await api('GET', `/admin/rooms/${props.room.id}/messages?limit=100`)
  messages.value = data.result || []
  await nextTick()
  scrollToBottom()
}

function scrollToBottom() {
  const el = messagesArea.value
  if (el) el.scrollTop = el.scrollHeight
}

// Send message
async function send() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''

  if (text.startsWith('/')) {
    handleCommand(text)
    return
  }

  // Extract @mentions
  const mentions = []
  const memberMap = {}
  if (props.room.members) {
    props.room.members.forEach(m => { memberMap[m.name] = m.id })
  }
  store.agents.forEach(a => { memberMap[a.name] = a.id })

  const mentionRegex = /@(\S+)/g
  let match
  while ((match = mentionRegex.exec(text)) !== null) {
    const id = memberMap[match[1]]
    if (id) mentions.push(id)
  }

  // Optimistic: add user message locally
  messages.value.push({
    id: Date.now(),
    sender_id: 'user',
    sender_name: '我',
    text,
    created_at: new Date().toISOString().replace('T', ' ').slice(0, 19),
  })
  await nextTick()
  scrollToBottom()

  await api('POST', `/admin/rooms/${props.room.id}/send`, { text, mentions })
}

async function handleCommand(text) {
  const cmd = text.split(' ')[0]
  if (cmd === '/clear') {
    const data = await api('DELETE', `/admin/rooms/${props.room.id}/messages`)
    if (data.ok) { messages.value = []; showToast('对话已清空') }
  } else if (cmd === '/members') {
    showSettings.value = true
  }
}

function triggerAt() {
  const el = inputEl.value
  if (!el) return
  const pos = el.selectionStart
  inputText.value = inputText.value.slice(0, pos) + '@' + inputText.value.slice(pos)
  nextTick(() => { el.focus(); el.selectionStart = el.selectionEnd = pos + 1 })
}

function autoResize(e) {
  const el = e.target
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 100) + 'px'
}

function showToast(msg) {
  const t = document.createElement('div')
  t.className = 'toast'
  t.textContent = msg
  document.body.appendChild(t)
  setTimeout(() => t.remove(), 2000)
}

// WebSocket handlers
function handleWS(msg) {
  if (msg.type === 'stream_start' && msg.room_id === props.room.id) {
    store.activeStreams[msg.stream_id] = { roomId: msg.room_id, agentId: msg.agent_id, agentName: msg.agent_name, text: '' }
    typingAgent.value = null
    nextTick(scrollToBottom)
  } else if (msg.type === 'stream_token' && store.activeStreams[msg.stream_id]) {
    store.activeStreams[msg.stream_id].text += msg.chunk
    nextTick(scrollToBottom)
  } else if (msg.type === 'stream_end' && store.activeStreams[msg.stream_id]) {
    delete store.activeStreams[msg.stream_id]
    // Fetch final message from server
    setTimeout(fetchMessages, 300)
  } else if (msg.type === 'new_message' && msg.room_id === props.room.id) {
    fetchMessages()
  } else if (msg.type === 'typing' && msg.room_id === props.room.id) {
    typingAgent.value = msg.from?.name || null
    setTimeout(() => { typingAgent.value = null }, 3000)
  }
}

onMounted(() => {
  fetchMessages()
  pollTimer = setInterval(fetchMessages, 3000)
  ws.onMessage(handleWS)
})

onUnmounted(() => {
  clearInterval(pollTimer)
})
</script>

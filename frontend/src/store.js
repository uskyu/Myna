import { reactive, ref } from 'vue'

const BASE = ''

export async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } }
  if (body) opts.body = JSON.stringify(body)
  try {
    const r = await fetch(BASE + path, opts)
    return await r.json()
  } catch (e) {
    return { ok: false, error: e.message }
  }
}

// Global state
export const store = reactive({
  agents: [],
  rooms: [],
  dms: [],
  activeStreams: {}, // streamId -> { roomId, agentId, agentName, text }
})

export async function loadAgents() {
  const data = await api('GET', '/admin/agents')
  store.agents = (data.result || []).filter(a => a.id !== 'system' && a.id !== 'user')
}

export async function loadConversations() {
  const [roomData, dmData] = await Promise.all([
    api('GET', '/admin/rooms'),
    api('GET', '/admin/dms'),
  ])
  store.rooms = (roomData.result || []).filter(r => r.type !== 'dm')
  store.dms = dmData.result || []
}

// WebSocket
export const ws = {
  _ws: null,
  _handlers: [],
  connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    this._ws = new WebSocket(`${proto}//${location.host}/ws?ui=1`)
    this._ws.onopen = () => console.log('[WS] Connected')
    this._ws.onclose = () => {
      console.log('[WS] Disconnected, reconnecting in 3s...')
      setTimeout(() => this.connect(), 3000)
    }
    this._ws.onerror = () => {}
    this._ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data)
        this._handlers.forEach(h => h(msg))
      } catch {}
    }
  },
  onMessage(handler) {
    this._handlers.push(handler)
  }
}

// AVATAR_COLORS
export const AVATAR_COLORS = [
  'linear-gradient(135deg, #667eea, #764ba2)',
  'linear-gradient(135deg, #f093fb, #f5576c)',
  'linear-gradient(135deg, #4facfe, #00f2fe)',
  'linear-gradient(135deg, #43e97b, #38f9d7)',
  'linear-gradient(135deg, #fa709a, #fee140)',
  'linear-gradient(135deg, #a18cd1, #fbc2eb)',
  'linear-gradient(135deg, #ffecd2, #fcb69f)',
  'linear-gradient(135deg, #89f7fe, #66a6ff)',
]

export const AGENT_ICONS = [
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2a4 4 0 0 1 4 4v2a4 4 0 0 1-8 0V6a4 4 0 0 1 4-4z"/><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/></svg>',
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>',
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>',
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
  '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
]

export function getAgentColor(idx) { return AVATAR_COLORS[idx % AVATAR_COLORS.length] }
export function getAgentIcon(idx) { return AGENT_ICONS[idx % AGENT_ICONS.length] }
export function escapeHtml(s) { if (!s) return ''; return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;') }

<template>
  <div class="assistant-home">
    <header class="assistant-topbar">
      <div class="assistant-brand"><span class="brand-mark">{{ assistantInitial }}</span><span>{{ assistantName }}</span></div>
      <button class="rename-button" @click="startRename" title="修改个人助手名称">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"/></svg>
        改名
      </button>
    </header>

    <main class="assistant-canvas">
      <section class="assistant-hero">
        <div class="hero-orbit">
          <span class="orbit-ring orbit-ring-one"></span>
          <span class="orbit-ring orbit-ring-two"></span>
          <span class="hero-core">{{ assistantInitial }}</span>
        </div>
        <p class="hero-eyebrow">PERSONAL INTELLIGENCE</p>
        <h1>你好，我是{{ assistantName }}</h1>
        <p>从最近的工作继续，或告诉我你现在想完成什么。</p>
      </section>

      <section class="recommendations">
        <button v-for="card in recommendationCards" :key="card.id" class="recommend-card" :title="`${card.title}\n${card.description}`" @click="submitPrompt(card.prompt)">
          <span class="recommend-type">{{ card.type }}</span>
          <strong>{{ card.title }}</strong>
          <span>{{ card.description }}</span>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
        </button>
      </section>

      <section class="assistant-composer" :class="{ 'drag-over': isDragging, uploading: isUploading }" @dragover.prevent="isDragging = true" @dragleave="isDragging = false" @drop.prevent="onDrop">
        <div v-if="isDragging" class="home-drop-hint">松开文件，交给{{ assistantName }}分析</div>
        <div v-if="attachments.length" class="home-attachments">
          <div v-for="(attachment, index) in attachments" :key="attachment.url" class="home-attachment">
            <span>{{ attachment.name }}</span>
            <button title="移除附件" @click="attachments.splice(index, 1)">×</button>
          </div>
        </div>
        <textarea v-model="prompt" rows="2" :placeholder="`给${assistantName}发消息，Enter 发送，Shift + Enter 换行`" @keydown.enter.exact.prevent="send"></textarea>
        <div class="composer-controls">
          <div class="temperature-control" title="控制回答的稳定性和创造性">
            <span>温度 {{ temperature.toFixed(1) }}</span>
            <input v-model.number="temperature" type="range" min="0" max="1" step="0.1">
          </div>
          <div class="mode-switch">
            <button :class="{ active: mode === 'fast' }" @click="mode = 'fast'">快速</button>
            <button :class="{ active: mode === 'expert' }" @click="mode = 'expert'">专家</button>
          </div>
          <div class="composer-spacer"></div>
          <button class="upload-home" :disabled="isUploading" @click="fileInput?.click()" title="上传文件">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m17 8-5-5-5 5M12 3v12"/></svg>
          </button>
          <input ref="fileInput" class="file-input" type="file" multiple :accept="fileAccept" @change="onFiles">
          <button class="send-home" :disabled="isUploading || (!prompt.trim() && !attachments.length)" @click="send" title="发送">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m22 2-7 20-4-9-9-4Z"/><path d="M22 2 11 13"/></svg>
          </button>
        </div>
        <div class="creation-tools">
          <button v-for="tool in creationTools" :key="tool.id" :disabled="tool.disabled" @click="applyTool(tool)">
            <span :class="`tool-icon ${tool.id}`">{{ tool.icon }}</span>{{ tool.label }}
          </button>
        </div>
      </section>
    </main>

    <Teleport to="body">
      <div v-if="renaming" class="assistant-modal-overlay" @click.self="renaming = false">
        <div class="assistant-modal">
          <p>个人助手名称</p>
          <input v-model.trim="renameValue" maxlength="40" autofocus @keydown.enter="saveName">
          <div><button @click="renaming = false">取消</button><button class="primary" :disabled="!renameValue" @click="saveName">保存</button></div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { store, auth } from './store.js'

const props = defineProps({ assistantName: { type: String, default: '马哥' } })
const emit = defineEmits(['start-chat', 'renamed'])
const prompt = ref('')
const mode = ref(localStorage.getItem('assistant_answer_mode') || 'fast')
const temperature = ref(Number(localStorage.getItem('assistant_temperature') || 0.3))
const renaming = ref(false)
const renameValue = ref('')
const fileInput = ref(null)
const attachments = ref([])
const isUploading = ref(false)
const isDragging = ref(false)
const fileAccept = '.doc,.docx,.pdf,.xls,.xlsx,.csv,.txt,.md,.markdown,.rtf,.odt,.ods,.ppt,.pptx,.json,.xml,.yaml,.yml,.zip,.rar,.7z,.tar,.gz,.tgz,.bz2,.xz,image/*,audio/*,video/*'
const assistantInitial = computed(() => {
  const name = String(props.assistantName || '').trim()
  const english = name.match(/[A-Za-z]/)
  return (english ? english[0].toUpperCase() : Array.from(name)[0]) || 'M'
})

const recentConversations = computed(() => [...store.rooms, ...store.dms]
  .filter(item => item.last_message?.text)
  .sort((a, b) => String(b.last_message?.created_at || '').localeCompare(String(a.last_message?.created_at || '')))
  .slice(0, 3))

const recommendationCards = computed(() => {
  const recent = recentConversations.value
  const topic = recent[0]?.name || recent[0]?.agent?.name || '近期关注方向'
  const unfinished = store.rooms.find(room => room.last_message?.text) || store.rooms[0]
  return [
    { id: 'continue', type: '继续任务', title: unfinished ? `继续推进：${unfinished.name}` : '梳理今天的待办', description: '根据已有上下文整理下一步和未完成事项', prompt: unfinished ? `请根据“${unfinished.name}”的已有对话，梳理未完成任务并继续推进。` : '请帮我梳理今天最重要的待办事项。' },
    { id: 'news', type: '相关新闻', title: `${topic} · 今日新进展`, description: '深度检索与你近期工作相关的可靠资讯', prompt: `请深度检索与“${topic}”相关的近期新闻和行业进展，给出来源、影响和行动建议。` },
    { id: 'recent', type: '最近对话', title: recent[1] ? (recent[1].name || recent[1].agent?.name) : '回顾最近的决策', description: recent[1]?.last_message?.text?.slice(0, 46) || '总结近期对话中的关键结论和决策', prompt: recent[1] ? `请回顾“${recent[1].name || recent[1].agent?.name}”相关对话，提炼关键结论并建议下一步。` : '请总结我最近的对话和关键决策。' },
  ]
})

const creationTools = [
  { id: 'translate', icon: '译', label: '翻译', prompt: '请翻译以下内容，并保留原有格式：\n' },
  { id: 'image', icon: '图', label: '图像生成', prompt: '请根据以下需求生成高质量图像，并先完善视觉提示词：\n' },
  { id: 'ppt', icon: 'P', label: 'PPT 生成', prompt: '请根据以下主题生成一份结构完整、可演示的 PPT：\n' },
  { id: 'soon', icon: '+', label: '敬请期待', disabled: true },
]

function answerInstruction() {
  localStorage.setItem('assistant_answer_mode', mode.value)
  localStorage.setItem('assistant_temperature', String(temperature.value))
  return `<!--myna-assistant:${mode.value}:${temperature.value.toFixed(1)}-->\n`
}
function submitPrompt(value) { emit('start-chat', { prompt: answerInstruction() + value, mode: mode.value, temperature: temperature.value }) }
function escapeMarkdownLabel(value) { return String(value || 'file').replace(/([\\\[\]])/g, '\\$1') }
function send() {
  if (!prompt.value.trim() && !attachments.value.length) return
  let value = prompt.value.trim() || '请分析这些附件，提炼关键信息、结论、风险和下一步建议。'
  for (const attachment of attachments.value) value += `\n[${escapeMarkdownLabel(attachment.name)}](${attachment.url})`
  submitPrompt(value)
}
async function uploadFiles(files) {
  const selected = Array.from(files || []).filter(file => file?.size >= 0)
  if (!selected.length) return
  isUploading.value = true
  try {
    for (const file of selected) {
      const body = new FormData()
      body.append('file', file, file.name)
      const token = auth.token || localStorage.getItem('hub_auth_token') || ''
      const response = await fetch(new URL('/admin/upload', window.location.href), {
        method: 'POST', body, credentials: 'same-origin', headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
      const result = await response.json().catch(() => ({}))
      if (!response.ok || !result.ok) throw new Error(result.error || `上传失败 (HTTP ${response.status})`)
      attachments.value.push({ url: result.url, name: result.name || file.name, size: result.size })
    }
  } catch (error) {
    window.alert(error?.message || '文件上传失败')
  } finally {
    isUploading.value = false
  }
}
async function onFiles(event) { await uploadFiles(event.target.files); event.target.value = '' }
async function onDrop(event) { isDragging.value = false; await uploadFiles(event.dataTransfer?.files) }
function applyTool(tool) { if (!tool.disabled) { prompt.value = tool.prompt; document.querySelector('.assistant-composer textarea')?.focus() } }
function startRename() { renameValue.value = props.assistantName; renaming.value = true }
async function saveName() {
  if (!renameValue.value) return
  localStorage.setItem('assistant_name', renameValue.value)
  emit('renamed', renameValue.value)
  renaming.value = false
}
</script>

<style scoped>
.assistant-home { height:100%; min-height:0; background:radial-gradient(circle at 50% 15%,color-mix(in srgb,var(--accent) 12%,transparent),transparent 32%),var(--bg); color:var(--text); overflow:hidden; }
.assistant-topbar { height:58px; display:flex; align-items:center; justify-content:space-between; padding:0 24px; border-bottom:1px solid color-mix(in srgb,var(--border) 65%,transparent); box-sizing:border-box; }
.assistant-brand { display:flex; align-items:center; gap:10px; font-weight:750; }.brand-mark,.hero-core { display:grid; place-items:center; color:#fff; background:linear-gradient(135deg,#65bc94,#2b7556,#418672,#65bc94); background-size:240% 240%; animation:assistant-gradient 5s ease infinite; }
.brand-mark { width:30px;height:30px;border-radius:10px;box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 32%,transparent);animation:assistant-gradient 5s ease infinite,brand-pulse 3s ease-in-out infinite; }.rename-button { display:flex;align-items:center;gap:6px;border:1px solid var(--border);background:var(--surface);color:var(--text-2);border-radius:10px;padding:7px 11px;cursor:pointer; }.rename-button svg{width:15px;height:15px}
.assistant-canvas { width:min(900px,calc(100% - 32px)); height:calc(100% - 58px); min-height:0; margin:auto; display:flex; flex-direction:column; justify-content:center; padding:24px 0 20px; box-sizing:border-box; }
.assistant-hero{text-align:center;flex:0 0 auto}.hero-orbit{position:relative;width:58px;height:58px;box-sizing:border-box;overflow:hidden;border:1px solid color-mix(in srgb,var(--accent) 25%,transparent);border-radius:20px;display:grid;place-items:center;margin:auto;box-shadow:0 14px 36px color-mix(in srgb,var(--accent) 16%,transparent);animation:orbit-float 4.2s ease-in-out infinite}.hero-core{position:relative;z-index:2;width:42px;height:42px;border-radius:14px;font-size:19px;box-shadow:0 7px 18px rgba(35,97,72,.25)}.orbit-ring{position:absolute;inset:2px;border-radius:17px;border:1px solid transparent;pointer-events:none}.orbit-ring-one{border-top-color:color-mix(in srgb,var(--accent) 75%,#fff);border-right-color:color-mix(in srgb,var(--accent) 25%,transparent);animation:orbit-spin 4.8s linear infinite}.orbit-ring-two{inset:7px;border-bottom-color:rgba(255,255,255,.55);border-left-color:color-mix(in srgb,var(--accent) 45%,transparent);animation:orbit-spin-reverse 3.4s linear infinite}
.hero-eyebrow{margin:17px 0 6px;color:var(--accent);font-size:9px;letter-spacing:.18em;font-weight:800}.assistant-hero h1{margin:0;font-size:clamp(26px,3.4vw,36px);letter-spacing:-.04em}.assistant-hero>p:last-child{color:var(--text-dim);margin:8px 0 0;font-size:13px}
.recommendations{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:24px 0 18px;flex:0 0 auto}.recommend-card{position:relative;height:122px;min-width:0;overflow:hidden;box-sizing:border-box;text-align:left;border:1px solid var(--border);border-radius:16px;padding:14px;background:color-mix(in srgb,var(--surface) 88%,transparent);color:var(--text);cursor:pointer;display:flex;flex-direction:column;gap:7px;transition:.2s}.recommend-card:hover{transform:translateY(-2px);border-color:color-mix(in srgb,var(--accent) 55%,var(--border));box-shadow:0 12px 28px rgba(0,0,0,.08)}.recommend-type{font-size:10px;line-height:14px;color:var(--accent);font-weight:750}.recommend-card strong{min-width:0;overflow:hidden;overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;font-size:14px;line-height:20px;padding-bottom:1px}.recommend-card>span:last-of-type{min-width:0;overflow:hidden;overflow-wrap:anywhere;display:-webkit-box;-webkit-box-orient:vertical;-webkit-line-clamp:2;color:var(--text-dim);font-size:11px;line-height:16px;padding:0 18px 1px 0}.recommend-card svg{position:absolute;right:12px;bottom:12px;width:15px}
.assistant-composer{position:relative;flex:0 0 auto;border:1px solid color-mix(in srgb,var(--accent) 24%,var(--border));border-radius:18px;background:var(--surface);padding:12px 13px;box-shadow:0 14px 38px rgba(0,0,0,.09)}.assistant-composer.drag-over{border-color:var(--accent);box-shadow:0 0 0 3px color-mix(in srgb,var(--accent) 18%,transparent)}.assistant-composer.uploading{opacity:.75}.home-drop-hint{position:absolute;inset:0;z-index:4;border-radius:17px;background:color-mix(in srgb,var(--surface) 94%,transparent);display:grid;place-items:center;color:var(--accent);font-size:13px;font-weight:750}.home-attachments{display:flex;gap:6px;overflow-x:auto;padding:0 2px 8px}.home-attachment{max-width:220px;display:flex;align-items:center;gap:5px;border:1px solid var(--border);border-radius:8px;padding:4px 6px;background:var(--bg);font-size:10px}.home-attachment span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.home-attachment button{border:0;background:transparent;color:var(--text-dim);cursor:pointer;padding:0;font-size:15px}.assistant-composer textarea{width:100%;resize:none;border:0;outline:0;background:transparent;color:var(--text);font:inherit;font-size:13px;line-height:1.45;box-sizing:border-box;padding:0 3px 8px;max-height:48px}.composer-controls{display:flex;align-items:center;gap:9px}.temperature-control{display:flex;align-items:center;gap:7px;font-size:10px;color:var(--text-dim);white-space:nowrap}.temperature-control input{width:68px;accent-color:var(--accent)}.mode-switch{display:flex;background:var(--bg);border-radius:8px;padding:2px}.mode-switch button{border:0;background:transparent;color:var(--text-dim);padding:5px 9px;border-radius:6px;cursor:pointer;font-size:12px}.mode-switch button.active{background:var(--surface);color:var(--accent);box-shadow:0 2px 8px rgba(0,0,0,.08);font-weight:700}.composer-spacer{flex:1}.file-input{display:none}.upload-home,.send-home{width:32px;height:32px;border:0;border-radius:10px;display:grid;place-items:center;cursor:pointer}.upload-home{background:var(--bg);color:var(--text-2);border:1px solid var(--border)}.send-home{background:var(--accent);color:#fff}.upload-home:disabled,.send-home:disabled{opacity:.4}.upload-home svg,.send-home svg{width:15px}.creation-tools{display:flex;gap:7px;margin-top:9px;padding-top:9px;border-top:1px solid var(--border);overflow-x:auto;overflow-y:hidden;scrollbar-width:none}.creation-tools::-webkit-scrollbar{display:none}.creation-tools button{display:flex;align-items:center;gap:5px;border:1px solid var(--border);background:var(--bg);color:var(--text-2);border-radius:9px;padding:5px 8px;white-space:nowrap;cursor:pointer;font-size:11px}.creation-tools button:disabled{opacity:.45;cursor:not-allowed}.tool-icon{width:17px;height:17px;display:grid;place-items:center;border-radius:5px;background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--accent);font-size:9px;font-weight:800}
.assistant-modal-overlay{position:fixed;inset:0;z-index:3000;background:rgba(0,0,0,.45);display:grid;place-items:center;padding:20px}.assistant-modal{width:min(360px,100%);background:var(--bg);border-radius:18px;padding:20px}.assistant-modal p{font-weight:750;margin:0 0 12px}.assistant-modal input{width:100%;box-sizing:border-box;border:1px solid var(--border);border-radius:10px;padding:10px;background:var(--surface);color:var(--text)}.assistant-modal>div{display:flex;justify-content:flex-end;gap:8px;margin-top:16px}.assistant-modal button{border:1px solid var(--border);background:var(--surface);color:var(--text);padding:8px 14px;border-radius:9px}.assistant-modal button.primary{background:var(--accent);color:#fff;border-color:var(--accent)}
@media(max-height:780px) and (min-width:768px){.assistant-canvas{padding:14px 0}.hero-orbit{width:50px;height:50px}.hero-core{width:36px;height:36px}.hero-eyebrow{margin-top:12px}.recommendations{margin:17px 0 14px}.recommend-card{height:112px;padding:12px}.recommend-card strong{line-height:19px}.recommend-card>span:last-of-type{line-height:15px}.assistant-composer{padding:10px 12px}.creation-tools{margin-top:7px;padding-top:7px}}
@media(max-width:767px){.assistant-home{height:100%}.assistant-topbar{height:50px;padding:0 14px}.brand-mark{width:27px;height:27px}.rename-button{padding:6px 9px;font-size:12px}.assistant-canvas{height:calc(100% - 50px);width:calc(100% - 20px);padding:12px 0 10px;justify-content:flex-start}.hero-orbit{width:46px;height:46px;border-radius:16px}.hero-core{width:34px;height:34px;border-radius:11px;font-size:16px}.hero-eyebrow{margin:10px 0 4px;font-size:8px}.assistant-hero h1{font-size:24px}.assistant-hero>p:last-child{font-size:11px;margin-top:5px}.recommendations{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px;margin:13px 0 11px;overflow:visible}.recommend-card{height:98px;min-width:0;padding:9px;border-radius:12px;gap:4px}.recommend-type{font-size:8px;line-height:12px}.recommend-card strong{font-size:10px;line-height:14px;-webkit-line-clamp:2;padding-bottom:1px}.recommend-card>span:last-of-type{font-size:8px;line-height:13px;padding:0 0 1px;-webkit-line-clamp:2}.recommend-card svg{right:7px;bottom:6px;width:11px}.assistant-composer{margin-top:auto;border-radius:15px;padding:10px}.assistant-composer textarea{font-size:12px;max-height:42px;padding-bottom:6px}.composer-controls{gap:6px}.temperature-control{height:26px;overflow:hidden;box-sizing:border-box;align-items:flex-start;flex-direction:column;gap:0;font-size:9px;line-height:11px}.temperature-control input{display:block;width:54px;height:10px;min-height:10px;margin:0}.mode-switch button{padding:4px 7px;font-size:11px}.send-home{width:30px;height:30px}.creation-tools{gap:6px;margin-top:7px;padding-top:7px}.creation-tools button{padding:4px 7px;font-size:10px}.tool-icon{width:15px;height:15px}}
@media(max-width:360px), (max-height:650px){.assistant-topbar{height:46px}.assistant-canvas{height:calc(100% - 46px);padding:7px 0}.hero-orbit{width:38px;height:38px}.hero-core{width:29px;height:29px;font-size:14px}.hero-eyebrow{margin-top:7px}.assistant-hero h1{font-size:21px}.assistant-hero>p:last-child{margin-top:3px}.recommendations{margin:9px 0 8px}.recommend-card{height:88px;padding:8px}.recommend-card strong{line-height:13px}.recommend-card>span:last-of-type{line-height:12px}.assistant-composer{padding:8px}.creation-tools{margin-top:5px;padding-top:5px}}
@keyframes assistant-gradient{0%,100%{background-position:0% 50%}50%{background-position:100% 50%}}
@keyframes brand-pulse{0%,100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--accent) 28%,transparent)}50%{box-shadow:0 0 0 6px transparent}}
@keyframes orbit-float{0%,100%{transform:translateY(0) rotate(5deg)}50%{transform:translateY(-4px) rotate(-3deg)}}
@keyframes orbit-spin{to{transform:rotate(360deg)}}
@keyframes orbit-spin-reverse{to{transform:rotate(-360deg)}}
@media(prefers-reduced-motion:reduce){.brand-mark,.hero-core,.hero-orbit,.orbit-ring{animation:none!important}}
</style>

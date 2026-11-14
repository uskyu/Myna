<template>
  <div v-if="artifact.open" ref="panel" class="office-shell" :class="{ mobile, fullscreen }">
    <header class="office-titlebar">
      <div class="office-brand">M</div>
      <div class="office-title"><strong>{{ artifact.name || '未命名文档' }}</strong><span>{{ dirty ? '有未保存修改' : '已加载 / 已保存' }}</span></div>
      <div class="title-actions">
        <button class="title-btn" @click="toggleFullscreen">{{ fullscreen ? '退出全屏' : '全屏' }}</button>
        <a class="title-btn" :href="downloadUrl" download>下载</a>
        <button class="title-btn close" @click="requestClose">✕</button>
      </div>
    </header>

    <nav class="office-tabs">
      <button class="office-tab active">开始</button>
      <button class="office-tab" @click="toggleMode" :disabled="!canEdit || loading || saving">{{ editing ? '预览' : '编辑' }}</button>
      <button class="office-tab" v-if="canEdit" @click="save" :disabled="saving || loading || !revision || !canEdit">{{ saving ? '保存中…' : '保存' }}</button>
      <span class="office-tab-spacer"></span>
      <button class="zoom-btn" disabled title="使用浏览器缩放" @click="zoom = Math.max(60, zoom - 10)">−</button>
      <span class="zoom-value">{{ zoom }}%</span>
      <button class="zoom-btn" disabled title="使用浏览器缩放" @click="zoom = Math.min(160, zoom + 10)">＋</button>
    </nav>

    <section class="office-ribbon">
      <div class="ribbon-group">
        <button class="ribbon-command" @click="toggleMode" :disabled="!canEdit || loading || saving"><span class="command-icon">✎</span><small>{{ editing ? '预览' : '编辑' }}</small></button>
        <button class="ribbon-command" @click="save" :disabled="saving || loading || !revision || !canEdit"><span class="command-icon">▣</span><small>保存</small></button>
      </div>
      <div class="ribbon-divider"></div>
      <div class="ribbon-group ribbon-format">
        <button class="format-btn" disabled title="基础编辑器不支持此操作"><b>B</b></button><button class="format-btn" disabled title="基础编辑器不支持此操作"><i>I</i></button><button class="format-btn" disabled title="基础编辑器不支持此操作"><u>U</u></button>
        <button class="format-btn" disabled title="基础编辑器不支持此操作">≡</button><button class="format-btn" disabled title="基础编辑器不支持此操作">☷</button>
      </div>
      <div class="ribbon-divider"></div>
      <div class="ribbon-context">{{ kindLabel }} · {{ editing ? '编辑模式' : '阅读模式' }}</div>
    </section>

    <main class="office-body">
      <div v-if="loading" class="office-status">正在打开文档…</div>
      <div v-if="error" class="office-status error" role="alert">{{ error }}</div>
      <template v-if="!loading && (supported || kind === 'pdf')">
        <section v-if="kind === 'pdf'" class="pdf-workspace">
          <div v-if="editing" class="pdf-note-editor">
            <p>PDF 基础编辑：添加逐页文字批注，不改动原正文排版。</p>
            <label>页码 <input v-model.number="pdfPage" type="number" min="1" :max="pdfPageCount"></label>
            <label>批注内容<textarea v-model="pdfNote" maxlength="4000" rows="4" placeholder="输入批注后点击保存"></textarea></label>
            <small>批注位于所选页左上角；部分浏览器需用 PDF 阅读器查看批注。</small>
          </div>
          <iframe class="pdf-frame" :src="pdfPreviewUrl" title="PDF 预览"></iframe>
        </section>
        <section v-else-if="kind === 'md' || kind === 'txt'" class="document-workspace">
          <div class="page-shadow markdown-page">
            <textarea v-if="editing" v-model="draft" class="page-editor" spellcheck="false"></textarea>
            <pre v-else-if="kind === 'txt'" class="page-content" style="white-space:pre-wrap;overflow-wrap:anywhere">{{ draft }}</pre>
            <article v-else class="page-content markdown-content" v-html="renderedMd"></article>
          </div>
        </section>

        <section v-else-if="kind === 'docx'" class="document-workspace">
          <div v-if="editing" class="page-shadow word-page word-editor">
            <div class="page-ruler"></div>
            <label v-for="(item, i) in paragraphs" :key="i" class="word-paragraph">
              <span class="paragraph-number">{{ i + 1 }}</span>
              <textarea v-model="item.text" rows="2"></textarea>
            </label>
          </div>
          <div v-else ref="docxHost" class="word-preview"></div>
        </section>

        <section v-else-if="kind === 'xlsx'" class="sheet-workspace">
          <div class="sheet-formula"><span class="name-box">{{ columnName(selectedCol) }}{{ selectedRow + 1 }}</span><span class="formula-sign">fx</span><span class="formula-value">{{ selectedCell }}</span></div>
          <div class="sheet-scroll"><table class="sheet-grid"><thead><tr><th class="corner"></th><th v-for="(_, ci) in columns" :key="ci">{{ columnName(ci) }}</th></tr></thead><tbody>
            <tr v-for="(row, ri) in rows" :key="ri"><th>{{ ri + 1 }}</th><td v-for="(_, ci) in columns" :key="ci" @click="selectedRow=ri;selectedCol=ci"><input v-if="editing" v-model="rows[ri][ci]" class="cell-input"><span v-else>{{ rows[ri][ci] }}</span></td></tr>
          </tbody></table></div>
        </section>

        <section v-else class="ppt-workspace">
          <aside class="slide-strip"><button v-for="(slide, si) in slides" :key="si" class="slide-thumb" :class="{ selected: si === selectedSlide }" @click="selectedSlide=si"><span>{{ si + 1 }}</span><div><p v-for="shape in slide.shapes.slice(0,3)" :key="shape.text">{{ shape.text }}</p></div></button></aside>
          <div class="slide-stage"><article v-if="slides[selectedSlide]" class="slide-canvas"><div v-for="(shape, pi) in slides[selectedSlide].shapes" :key="pi" class="slide-textbox"><textarea v-if="editing" v-model="shape.text" rows="2"></textarea><div v-else>{{ shape.text || ' ' }}</div></div></article><div v-else class="office-status">没有可显示的幻灯片</div></div>
        </section>
      </template>
      <div v-else class="office-status">当前仅支持 Word、Excel、PPT 和 Markdown。</div>
    </main>
    <footer class="office-statusbar"><span>{{ kindLabel }}</span><span>只读/编辑内容会写回原文件</span><span class="status-spacer"></span><span>{{ zoom }}%</span></footer>
  </div>
</template>

<script setup>
import { computed, nextTick, ref, watch, onBeforeUnmount } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { renderAsync } from 'docx-preview'
import { artifact, closeArtifact, api } from '../store.js'

defineProps({ mobile: Boolean })
const panel = ref(null), docxHost = ref(null), loading = ref(false), error = ref(''), saving = ref(false), editing = ref(false), fullscreen = ref(false), zoom = ref(100)
const draft = ref(''), renderedMd = ref(''), paragraphs = ref([]), slides = ref([]), rows = ref([]), selectedSlide = ref(0), selectedRow = ref(0), selectedCol = ref(0)
const ext = computed(() => { const v=String(artifact.path||artifact.name||artifact.url||'').toLowerCase(); const m=v.match(/\.([a-z0-9]+)(?:\?|$)/); return m?m[1]:'' })
const kind = computed(() => ({ md:'md',markdown:'md',txt:'txt',docx:'docx',xlsx:'xlsx',xlsm:'xlsx',pptx:'pptx',pdf:'pdf' }[ext.value] || 'unknown'))
const kindLabel = computed(() => ({ md:'Markdown',txt:'TXT 文本',pdf:'PDF 文档',docx:'Word 文档',xlsx:'Excel 工作簿',pptx:'PowerPoint 演示文稿' }[kind.value] || '文件'))
const supported = computed(() => ['md','txt','docx','xlsx','pptx','pdf'].includes(kind.value)), canEdit = computed(() => supported.value)
const viewUrl = computed(() => artifact.url || ''), downloadUrl = computed(() => viewUrl.value + (viewUrl.value.includes('?')?'&':'?')+'download=1')
const columns = computed(() => Array.from({length:Math.max(1,...rows.value.map(r=>r.length))},(_,i)=>i))
const selectedCell = computed(() => rows.value[selectedRow.value]?.[selectedCol.value] || '')
function columnName(i){ let n=''; do { n=String.fromCharCode(65+i%26)+n; i=Math.floor(i/26)-1 } while(i>=0); return n }
const revision = ref(''), snapshot = ref('')
const pdfNote = ref(''), pdfPage = ref(1), pdfPageCount = ref(1)
const pdfPreviewUrl = computed(() => viewUrl.value + (viewUrl.value.includes('?') ? '&' : '?') + 'revision=' + encodeURIComponent(revision.value))
let loadSequence = 0
const payload = () => ({ paragraphs: paragraphs.value, slides: slides.value, rows: rows.value, content: draft.value, annotation: { text: pdfNote.value, page: pdfPage.value } })
const dirty = computed(() => !!revision.value && JSON.stringify(payload()) !== snapshot.value)
const identity = () => artifact.path + '\n' + artifact.url
function requestClose() {
  if (saving.value || (dirty.value && !window.confirm('放弃未保存修改？'))) return
  closeArtifact()
}
function beforeUnload(event) {
  if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = '' }
}
window.addEventListener('beforeunload', beforeUnload)
watch(dirty, value => { artifact.dirty = value })
watch(saving, value => { artifact.saving = value })
onBeforeUnmount(() => {
  ++loadSequence
  window.removeEventListener('beforeunload', beforeUnload)
  artifact.dirty = false
  artifact.saving = false
})
watch(() => [artifact.open, artifact.url, artifact.path], load, { immediate: true })
async function load() {
  const sequence = ++loadSequence
  if (!artifact.open || !artifact.url) return
  const fileIdentity = identity(), fileKind = kind.value, path = artifact.path
  loading.value = true; error.value = ''; revision.value = ''; editing.value = false
  draft.value = ''; paragraphs.value = []; slides.value = []; rows.value = []; renderedMd.value = ''
  selectedSlide.value = 0; selectedRow.value = 0; selectedCol.value = 0
  pdfNote.value = ''; pdfPage.value = 1; pdfPageCount.value = 1
  try {
    if (!supported.value) return
    const r = await api('GET', '/admin/workspace/office?path=' + encodeURIComponent(path) + '&kind=' + fileKind)
    if (sequence !== loadSequence || identity() !== fileIdentity) return
    if (!r?.ok) throw Error(r?.error || '加载失败')
    paragraphs.value = r.result.paragraphs || []; slides.value = r.result.slides || []; rows.value = r.result.rows || []
    draft.value = r.result.content || ''; revision.value = r.result.revision
    pdfPageCount.value = r.result.page_count || 1
    snapshot.value = JSON.stringify(payload()); renderMarkdown()
  } catch (e) { if (sequence === loadSequence) error.value = e.message }
  finally {
    if (sequence === loadSequence) {
      loading.value = false
      if (kind.value === 'docx' && revision.value) {
        try { await renderDocx() } catch (e) { if (sequence === loadSequence) error.value = e.message }
      }
    }
  }
}
function renderMarkdown() { renderedMd.value = DOMPurify.sanitize(marked.parse(draft.value || ''), { USE_PROFILES: { html: true } }) }
async function renderDocx() {
  await nextTick()
  const host = docxHost.value, fileIdentity = identity()
  if (!host) return
  const r = await fetch(viewUrl.value, { cache: 'no-store' })
  if (!r.ok) throw Error('Word 文件加载失败')
  const bytes = await r.arrayBuffer()
  if (identity() !== fileIdentity || docxHost.value !== host) return
  host.replaceChildren()
  await renderAsync(bytes, host, undefined, { inWrapper: true, ignoreWidth: false })
}
async function toggleMode() {
  if (!canEdit.value || loading.value || saving.value) return
  if (editing.value && kind.value === 'docx' && dirty.value) { error.value = '请先保存，再查看 Word 原格式预览'; return }
  editing.value = !editing.value
  try {
    if (!editing.value && kind.value === 'md') renderMarkdown()
    if (!editing.value && kind.value === 'docx') await renderDocx()
  } catch (e) { error.value = e.message }
}
async function save() {
  if (saving.value || loading.value || !revision.value || !canEdit.value) return
  const fileIdentity = identity(), fileKind = kind.value
  const body = JSON.parse(JSON.stringify({ ...payload(), path: artifact.path, kind: fileKind, revision: revision.value }))
  const submitted = JSON.stringify(payload())
  saving.value = true; error.value = ''
  try {
    const r = await api('POST', '/admin/workspace/office', body)
    if (identity() !== fileIdentity) return
    if (!r?.ok) throw Error(r?.error || '保存失败')
    revision.value = r.result.revision; snapshot.value = submitted
    if (fileKind === 'pdf' && JSON.stringify(payload()) === submitted) { pdfNote.value = ''; snapshot.value = JSON.stringify(payload()) }
  } catch (e) { if (identity() === fileIdentity) error.value = e.message }
  finally { saving.value = false }
}
async function toggleFullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await panel.value?.requestFullscreen?.()}catch{}}
document.addEventListener('fullscreenchange',()=>{fullscreen.value=document.fullscreenElement===panel.value})
</script>

<style scoped>
.office-shell{width:100%;height:100dvh;display:flex;flex-direction:column;background:#e9edf2;color:#202124;min-width:0}.office-titlebar{height:44px;flex:0 0 44px;display:flex;align-items:center;padding:0 12px;gap:10px;background:#fff;border-bottom:1px solid #d7dbe0}.office-brand{width:27px;height:27px;border-radius:7px;background:#2563a8;color:#fff;display:grid;place-items:center;font-weight:800}.office-title{display:flex;flex-direction:column;gap:1px;min-width:0;flex:1}.office-title strong{font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.office-title span{font-size:10px;color:#69737e}.title-actions{display:flex;gap:5px}.title-btn{border:1px solid #d7dbe0;border-radius:5px;background:#fff;color:#4d5660;padding:5px 9px;font-size:11px;text-decoration:none;cursor:pointer}.title-btn:hover{background:#f0f4f8}.title-btn.close{font-size:14px;padding:3px 8px}.office-tabs{height:34px;display:flex;align-items:center;padding:0 14px;gap:15px;background:#fff;border-bottom:1px solid #d7dbe0}.office-tab{height:34px;border:0;background:none;color:#59636e;font-size:12px;cursor:pointer}.office-tab.active{color:#2563a8;border-bottom:2px solid #2563a8;font-weight:700}.office-tab:disabled{opacity:.5}.office-tab-spacer{flex:1}.zoom-btn{border:0;background:none;color:#59636e;font-size:17px;cursor:pointer}.zoom-value{font-size:11px;color:#59636e;min-width:35px;text-align:center}.office-ribbon{height:61px;flex:0 0 61px;display:flex;align-items:center;padding:5px 15px;gap:13px;background:#f8fafc;border-bottom:1px solid #cfd5dc;box-shadow:0 1px 2px #0000000b}.ribbon-group{display:flex;align-items:center;gap:6px;height:100%}.ribbon-command{height:48px;min-width:47px;border:0;background:transparent;border-radius:5px;color:#3f4b56;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;cursor:pointer}.ribbon-command:hover{background:#e5edf6}.ribbon-command:disabled{opacity:.5}.command-icon{font-size:22px;line-height:20px;color:#2563a8}.ribbon-command small{font-size:10px}.ribbon-divider{height:42px;border-left:1px solid #d4d9df}.format-btn{width:30px;height:28px;border:0;background:transparent;color:#3f4b56;font-size:15px;border-radius:4px;cursor:pointer}.format-btn:hover{background:#e3e9ef}.ribbon-context{font-size:11px;color:#7a838d;margin-left:3px}.office-body{flex:1;min-height:0;overflow:hidden;display:flex;position:relative}.pdf-workspace{flex:1;min-height:0;display:flex;background:#dfe4ea}.pdf-frame{width:100%;height:100%;border:0;background:#fff}.office-status{margin:auto;padding:30px;color:#77818b;font-size:13px;text-align:center}.office-status.error{color:#b42318}.document-workspace{flex:1;overflow:auto;padding:34px 30px 60px;background:#e9edf2}.page-shadow{width:min(820px,100%);min-height:1050px;margin:0 auto;background:#fff;box-shadow:0 2px 10px #26374a24}.markdown-page{display:flex}.page-editor{width:100%;min-height:1050px;padding:74px 82px;border:0;outline:0;resize:none;background:#fff;color:#202124;font:14px/1.8 var(--font-mono)}.page-content{padding:74px 82px;color:#202124;font:14px/1.8 var(--font-sans)}.page-content :deep(h1),.page-content :deep(h2),.page-content :deep(h3){margin:18px 0 8px}.page-content :deep(pre){padding:14px;background:#1f2933;color:#f5f7fa;overflow:auto;border-radius:5px}.word-page{position:relative;padding:62px 74px}.page-ruler{position:absolute;top:25px;left:74px;right:74px;border-top:1px solid #b9c1ca}.word-paragraph{display:flex;gap:9px;margin-bottom:10px}.paragraph-number{width:24px;padding-top:9px;text-align:right;color:#a0a8b0;font-size:9px}.word-paragraph textarea{flex:1;resize:vertical;border:1px solid transparent;border-radius:3px;padding:8px;color:#202124;background:transparent;font:14px/1.7 var(--font-sans)}.word-paragraph textarea:focus{border-color:#8bb7e2;background:#fafdff;outline:0}.word-preview{flex:1;overflow:auto;padding:32px;background:#e9edf2}.word-preview :deep(.docx-wrapper){padding:0!important;background:transparent!important}.word-preview :deep(.docx){margin:0 auto 24px!important;max-width:none!important;box-shadow:0 2px 10px #26374a24}.sheet-workspace{flex:1;min-width:0;display:flex;flex-direction:column;background:#fff}.sheet-formula{height:34px;flex:0 0 34px;display:flex;align-items:center;gap:8px;border-bottom:1px solid #cbd2d9;background:#f7f9fb;font-size:12px;color:#4e5964}.name-box{width:55px;height:25px;margin-left:8px;padding:5px 8px;border:1px solid #adb7c1;border-radius:3px;background:#fff}.formula-sign{font-weight:700;font-style:italic;color:#2563a8}.formula-value{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sheet-scroll{flex:1;overflow:auto}.sheet-grid{border-collapse:collapse;min-width:100%;font-size:12px}.sheet-grid th{position:sticky;top:0;z-index:2;height:25px;background:#eef2f5;border:1px solid #cbd2d9;color:#5f6a75;font-weight:600;min-width:110px}.sheet-grid th:first-child{left:0;z-index:3;min-width:42px;width:42px}.sheet-grid tbody th{position:sticky;left:0;z-index:1}.sheet-grid td{height:29px;min-width:110px;max-width:280px;border:1px solid #d8dde2;padding:0;color:#202124;vertical-align:top}.sheet-grid td span{display:block;padding:6px 8px;white-space:pre-wrap;word-break:break-word}.cell-input{width:100%;height:28px;border:2px solid #2b78c5;outline:0;padding:4px 7px;background:#fff;font:12px var(--font-sans)}.ppt-workspace{flex:1;display:flex;min-width:0;background:#dfe4ea}.slide-strip{width:178px;flex:0 0 178px;overflow:auto;padding:15px 11px;background:#f2f4f7;border-right:1px solid #cbd2d9}.slide-thumb{width:100%;min-height:85px;display:flex;gap:5px;margin-bottom:10px;padding:5px;border:1px solid #ccd3db;border-radius:4px;background:#fff;cursor:pointer;text-align:left}.slide-thumb.selected{border:2px solid #2563a8;padding:4px}.slide-thumb>span{font-size:10px;color:#67717c;padding-top:2px}.slide-thumb div{flex:1;overflow:hidden;background:#fff}.slide-thumb p{margin:2px 0;color:#34404b;font-size:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.slide-stage{flex:1;min-width:0;overflow:auto;display:flex;align-items:flex-start;justify-content:center;padding:35px}.slide-canvas{width:min(960px,100%);aspect-ratio:16/9;background:#fff;box-shadow:0 3px 16px #27384c2e;padding:55px;overflow:auto}.slide-textbox{margin:10px 0;min-height:30px;color:#202124;font-size:18px;line-height:1.5}.slide-textbox textarea{width:100%;resize:vertical;border:1px dashed #b9c4cf;padding:8px;color:#202124;font:18px/1.5 var(--font-sans)}.office-statusbar{height:24px;flex:0 0 24px;display:flex;align-items:center;gap:18px;padding:0 12px;background:#2563a8;color:#fff;font-size:10px}.status-spacer{flex:1}.office-shell.mobile{position:fixed;inset:0;z-index:60;border:0}@media(max-width:700px){.office-ribbon{padding:4px 8px;gap:5px}.ribbon-format,.ribbon-divider{display:none}.document-workspace{padding:15px 8px 30px}.page-editor,.page-content{padding:42px 28px}.word-page{padding:45px 20px}.slide-strip{width:115px;flex-basis:115px}.slide-stage{padding:15px 8px}.slide-canvas{padding:25px 18px}.slide-textbox{font-size:12px}.slide-textbox textarea{font-size:12px}.title-btn{padding:5px 6px}}
.pdf-workspace{flex-direction:column;min-width:0}.pdf-frame{flex:1;min-height:0}.pdf-note-editor{padding:12px;background:var(--surface);color:var(--text);font-size:12px;flex-shrink:0}.pdf-note-editor label{display:block;margin:8px 0}.pdf-note-editor textarea{display:block;width:100%;background:var(--bg);color:var(--text);border:1px solid var(--border);padding:8px}.pdf-note-editor input{width:70px;background:var(--bg);color:var(--text);border:1px solid var(--border)}
</style>

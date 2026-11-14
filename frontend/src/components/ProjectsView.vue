<template>
  <div class="page projects-page">
    <div class="header">
      <h1>{{ tr('项目') }}</h1>
      <div class="actions">
        <button @click="showCreate = true" :title="tr('新建项目')" :aria-label="tr('新建项目')">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
        </button>
      </div>
    </div>

    <p v-if="error" role="alert" style="color:var(--danger,#b42318)">{{ error }}</p>
    <div v-if="loading" class="empty">
      <div class="msg-loading-spinner"></div>
      <p>{{ tr('加载中...') }}</p>
    </div>

    <div v-else-if="!projects.length" class="empty">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="48" height="48"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
      <p>{{ tr('还没有项目') }}</p>
      <p>{{ tr('点击右上角新建项目') }}</p>
    </div>

    <div v-else class="project-list">
      <div v-for="p in projects" :key="p.id" class="project-row" @click="openProject(p)">
        <div class="project-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="24" height="24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
        </div>
        <div class="project-info">
          <div class="project-name">{{ p.name }}</div>
          <div class="project-summary">{{ p.summary || tr('暂无描述') }}</div>
          <div class="project-meta">
            <span>{{ tr('项目') }}</span>
            <span v-if="p.last_message">· {{ tr('最近活动') }} {{ formatTime(p.last_message.created_at) }}</span>
          </div>
        </div>
        <div class="project-arrow">›</div>
      </div>
    </div>

    <section v-if="selectedProject" class="project-tasks">
      <div class="project-tasks-heading"><strong>{{ selectedProject.name }}</strong><button :disabled="creatingTask" @click="createProjectTask" title="新建任务" aria-label="新建任务">+</button></div>
      <p v-if="tasksLoading">{{ tr('加载任务中...') }}</p>
      <p v-else-if="!projectTasks.length">{{ tr('暂无任务，点击 + 创建') }}</p>
      <button v-for="task in projectTasks" :key="task.id" class="project-task-row" @click="emit('open-project', task)">{{ task.name }}</button>
    </section>
    <!-- Create project modal -->
    <Teleport to="body">
      <div v-if="showCreate" class="modal-overlay" @click.self="showCreate = false">
        <div class="modal-content">
          <h3>{{ tr('新建项目') }}</h3>
          <p v-if="error" role="alert" style="color:var(--danger,#b42318)">{{ error }}</p>
          <div class="form-group">
            <label>{{ tr('项目名称') }}</label>
            <input v-model="form.name" :placeholder="tr('例如：官网重构项目')" />
          </div>
          <div class="form-group">
            <label>{{ tr('项目目标') }}</label>
            <textarea v-model="form.summary" :placeholder="tr('简要描述项目目标和范围...')" rows="3"></textarea>
          </div>
          <div class="modal-actions">
            <button class="btn-cancel" @click="showCreate = false">{{ tr('取消') }}</button>
            <button class="btn-primary" :disabled="!canSubmit || submitting" @click="submit">
              {{ submitting ? tr('创建中...') : tr('创建项目') }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue'
import { api } from '../store.js'
import { tr } from '../i18n.js'

const emit = defineEmits(['open-project'])

const projects = ref([])
const error = ref('')
const loading = ref(true)
const props = defineProps({ createOnOpen: Boolean })
const showCreate = ref(props.createOnOpen)
const submitting = ref(false)

const form = reactive({
  name: '',
  summary: '',
  roles: [{ name: '', responsibility: '' }],
})

const canSubmit = computed(() => Boolean(form.name.trim()))

function addRole() {
  form.roles.push({ name: '', responsibility: '' })
}

function formatTime(t) {
  if (!t) return ''
  const d = new Date(t)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function loadProjects() {
  loading.value = true
  try {
    const res = await api('GET', '/admin/projects')
    if (!res?.ok) throw Error(res?.error || '加载项目失败')
    projects.value = res.result || []
  } catch (e) { error.value = e.message }
  finally { loading.value = false }
}

async function submit() {
  if (!canSubmit.value || submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    const res = await api('POST', '/admin/projects', { name: form.name.trim() })
    if (!res?.ok) throw Error(res?.error || '创建项目失败')
    if (res?.ok) {
      showCreate.value = false
      form.name = ''
      form.summary = ''
      form.roles = [{ name: '', responsibility: '' }]
      await loadProjects()
      if (res.result?.id) { await openProject(res.result) }
    }
  } catch (e) { error.value = e.message }
  finally { submitting.value = false }
}

const selectedProject = ref(null), projectTasks = ref([]), tasksLoading = ref(false), creatingTask = ref(false)
let taskRequest = 0
async function openProject(project) {
  selectedProject.value = project
  projectTasks.value = []; tasksLoading.value = true; error.value = ''
  const sequence = ++taskRequest
  try {
    const result = await api('GET', '/admin/projects/' + project.id + '/tasks')
    if (sequence !== taskRequest) return
    if (!result?.ok) throw Error(result?.error || '加载任务失败')
    projectTasks.value = result.result || []
  } catch (e) { if (sequence === taskRequest) error.value = e.message }
  finally { if (sequence === taskRequest) tasksLoading.value = false }
}
async function createProjectTask() {
  if (!selectedProject.value || creatingTask.value) return
  const title = window.prompt('任务名称', '新任务')?.trim()
  if (!title) return
  const project = selectedProject.value
  creatingTask.value = true
  try {
    const result = await api('POST', '/admin/collaboration/planning-room', { task: title, project_id: project.id, mode: 'conversation' })
    if (!result?.ok) throw Error(result?.error || '创建任务失败')
    await openProject(project)
    emit('open-project', result.result)
  } catch (e) { error.value = e.message }
  finally { creatingTask.value = false }
}

onMounted(loadProjects)
</script>

<style scoped>
.projects-page{background:var(--bg)}
.projects-page>.header{margin-bottom:0}
.projects-page>.header h1{font-size:20px;color:var(--text)}
.project-primary{display:inline-flex;align-items:center;gap:6px;height:36px;padding:0 12px;border:1px solid var(--accent);border-radius:var(--radius-sm);background:var(--accent);color:#fff;font-size:12px;font-weight:600;cursor:pointer}
.project-primary:hover{background:var(--accent-hover)}
.project-primary:disabled{opacity:.5;cursor:default}
.projects-page>p[role=alert]{margin:12px 20px;color:var(--danger)!important;font-size:12px}
.empty{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:48px 20px;color:var(--text-dim);text-align:center}
.empty svg{color:var(--text-faint);margin-bottom:12px}.empty p{margin:4px 0;font-size:13px}
.project-list{margin:0 20px;border-top:1px solid var(--border)}
.project-row{display:flex;align-items:center;gap:12px;width:100%;padding:14px 4px;border:0;border-bottom:1px solid var(--border);background:transparent;color:var(--text);text-align:left;cursor:pointer}.project-row:hover{background:var(--surface2)}
.project-icon{width:34px;height:34px;display:grid;place-items:center;flex-shrink:0;border-radius:var(--radius-sm);background:var(--accent-soft);color:var(--accent)}.project-icon svg{width:18px;height:18px}.project-info{min-width:0;flex:1}.project-name{font-size:13px;font-weight:650;margin-bottom:3px}.project-summary{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text-dim);font-size:12px}.project-meta{margin-top:4px;color:var(--text-faint);font-size:11px}.project-arrow{color:var(--text-faint);font-size:20px}
.modal-overlay{position:fixed;inset:0;z-index:100;display:grid;place-items:center;padding:20px;background:rgba(26,25,22,.28)}.modal-content{width:min(480px,100%);max-height:85vh;overflow:auto;padding:20px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow-lg)}.modal-content h3{margin:0 0 18px;color:var(--text);font-size:16px}.modal-content p[role=alert]{color:var(--danger)!important;font-size:12px}.form-group{margin-bottom:14px}.form-group label{display:block;margin-bottom:6px;color:var(--text-2);font-size:12px;font-weight:600}.form-group input,.form-group textarea{width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--bg);color:var(--text);font-size:13px}.form-group input:focus,.form-group textarea:focus{outline:0;border-color:var(--accent);box-shadow:var(--shadow-glow)}.btn-link{padding:0;border:0;background:transparent;color:var(--accent);font-size:12px;cursor:pointer}.role-row{display:flex;gap:6px;margin-bottom:7px}.role-name{width:120px;flex-shrink:0}.role-resp{flex:1}.btn-remove{border:0;background:transparent;color:var(--danger);cursor:pointer}.modal-actions{display:flex;justify-content:flex-end;gap:7px;margin-top:18px}.btn-cancel{padding:8px 12px;border:1px solid var(--border);border-radius:var(--radius-sm);background:var(--surface2);color:var(--text-2);font-size:12px;cursor:pointer}.btn-cancel:hover{background:var(--surface3)}
@media(max-width:700px){.project-list{margin:0 12px}.projects-page>.header{padding:0 14px}.role-row{flex-wrap:wrap}.role-name{width:calc(50% - 3px)}.role-resp{width:calc(50% - 3px);flex:auto}.btn-remove{margin-left:auto}}
.projects-page{position:relative;height:100%;min-height:0;overflow-y:auto}.project-list{flex-shrink:0}.project-tasks{padding:12px 20px;border-top:1px solid var(--border);margin-top:16px}.project-tasks-heading{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:13px}.project-tasks-heading button{border:0;background:transparent;color:var(--text-2);font-size:22px;width:32px;height:32px}.project-task-row{display:block;width:100%;padding:12px 0;text-align:left;border:0;border-bottom:1px solid var(--border);background:transparent;color:var(--text);font:inherit;font-size:13px}.project-task-row:hover{color:var(--accent)}.project-tasks p{font-size:12px;color:var(--text-dim);padding:10px 0}
</style>

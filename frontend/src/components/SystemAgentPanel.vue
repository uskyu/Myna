<template>
  <div class="system-agent-panel">
    <!-- Status Card -->
    <div class="agent-status-card">
      <div class="status-header">
        <span class="status-icon">🔐</span>
        <span class="status-title">System Agent</span>
        <span class="status-badge" :class="status.status">{{ status.status === 'online' ? '运行中' : '离线' }}</span>
      </div>
      <div class="status-stats">
        <div class="stat-item">
          <span class="stat-value">{{ status.credentials_count }}</span>
          <span class="stat-label">凭据</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ status.repos_count }}</span>
          <span class="stat-label">仓库</span>
        </div>
        <div class="stat-item">
          <span class="stat-value">{{ status.recent_requests }}</span>
          <span class="stat-label">请求</span>
        </div>
      </div>
    </div>

    <!-- Credentials Section -->
    <div class="section">
      <div class="section-header">
        <h3>🔑 凭据管理</h3>
        <button class="btn-add" @click="showAddForm = true">+ 添加</button>
      </div>
      <p class="section-desc">存储 GitHub PAT、SSH Key、API Key 等凭据，系统智能体按需分发给其他智能体使用。凭据加密存储，其他智能体无法直接获取明文。</p>

      <!-- Add Form -->
      <div v-if="showAddForm" class="add-form">
        <div class="form-row">
          <label>名称</label>
          <input v-model="newCred.name" placeholder="如：GitHub PAT (uskyu)" />
        </div>
        <div class="form-row">
          <label>类型</label>
          <select v-model="newCred.type">
            <option value="github_pat">GitHub PAT</option>
            <option value="ssh_key">SSH Key</option>
            <option value="api_key">API Key</option>
            <option value="custom">自定义</option>
          </select>
        </div>
        <div class="form-row">
          <label>值</label>
          <textarea v-model="newCred.value" :placeholder="valuePlaceholder" rows="3"></textarea>
        </div>
        <div class="form-row">
          <label>备注（可选）</label>
          <input v-model="newCred.note" placeholder="如：scope=repo, 过期时间等" />
        </div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showAddForm = false; resetForm()">取消</button>
          <button class="btn-save" @click="addCredential" :disabled="!newCred.name || !newCred.value">保存</button>
        </div>
      </div>

      <!-- Credential List -->
      <div class="cred-list">
        <div v-if="credentials.length === 0 && !showAddForm" class="empty-state">
          暂无凭据，点击「添加」配置第一个
        </div>
        <div v-for="cred in credentials" :key="cred.id" class="cred-item">
          <div class="cred-info">
            <span class="cred-type-badge" :class="cred.type">{{ typeLabel(cred.type) }}</span>
            <span class="cred-name">{{ cred.name }}</span>
            <span class="cred-preview">{{ cred.value_preview }}</span>
          </div>
          <div class="cred-actions">
            <button class="btn-icon" title="删除" @click="deleteCredential(cred)">🗑</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Workspace Section -->
    <div class="section">
      <div class="section-header">
        <h3>📂 工作区仓库</h3>
        <button class="btn-add" @click="showCloneForm = true">+ Clone</button>
      </div>
      <p class="section-desc">系统智能体管理的 Git 仓库。其他智能体可通过 @system 请求 clone、pull、push 操作。</p>

      <!-- Clone Form -->
      <div v-if="showCloneForm" class="add-form">
        <div class="form-row">
          <label>仓库 URL</label>
          <input v-model="cloneUrl" placeholder="https://github.com/user/repo.git" />
        </div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showCloneForm = false; cloneUrl = ''">取消</button>
          <button class="btn-save" @click="cloneRepo" :disabled="!cloneUrl">Clone</button>
        </div>
      </div>

      <!-- Repo List -->
      <div class="repo-list">
        <div v-if="repos.length === 0 && !showCloneForm" class="empty-state">
          暂无仓库
        </div>
        <div v-for="repo in repos" :key="repo.name" class="repo-item">
          <div class="repo-info">
            <span class="repo-name">{{ repo.name }}</span>
            <span class="repo-branch">{{ repo.branch }}</span>
          </div>
          <div class="repo-path">{{ repo.path }}</div>
        </div>
      </div>
    </div>

    <!-- Access Log Section -->
    <div class="section">
      <div class="section-header">
        <h3>📋 访问日志</h3>
        <button class="btn-refresh" @click="loadAccessLog">刷新</button>
      </div>
      <div class="log-list">
        <div v-if="accessLog.length === 0" class="empty-state">暂无访问记录</div>
        <div v-for="(entry, i) in accessLog" :key="i" class="log-item">
          <span class="log-time">{{ formatTime(entry.time) }}</span>
          <span class="log-requester">{{ entry.requester }}</span>
          <span class="log-action">{{ entry.action }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { api } from '../store.js'

const status = reactive({
  status: 'offline',
  credentials_count: 0,
  repos_count: 0,
  recent_requests: 0,
})

const credentials = ref([])
const repos = ref([])
const accessLog = ref([])
const showAddForm = ref(false)
const showCloneForm = ref(false)
const cloneUrl = ref('')

const newCred = reactive({
  name: '',
  type: 'github_pat',
  value: '',
  note: '',
})

const valuePlaceholder = computed(() => {
  switch (newCred.type) {
    case 'github_pat': return 'ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
    case 'ssh_key': return '-----BEGIN OPENSSH PRIVATE KEY-----\n...'
    case 'api_key': return 'sk-xxxxxxxxxxxxxxxxxxxxxxxx'
    default: return '凭据值'
  }
})

function typeLabel(type) {
  const labels = {
    github_pat: 'GitHub',
    ssh_key: 'SSH',
    api_key: 'API Key',
    custom: '自定义',
  }
  return labels[type] || type
}

function resetForm() {
  newCred.name = ''
  newCred.type = 'github_pat'
  newCred.value = ''
  newCred.note = ''
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

async function loadStatus() {
  try {
    const res = await api('/admin/system-agent/status')
    Object.assign(status, res)
  } catch (e) {
    console.error('Failed to load system agent status:', e)
  }
}

async function loadCredentials() {
  try {
    const res = await api('/admin/system-agent/credentials')
    credentials.value = res.credentials || []
  } catch (e) {
    console.error('Failed to load credentials:', e)
  }
}

async function loadRepos() {
  try {
    const res = await api('/admin/system-agent/repos')
    repos.value = res.data?.repos || []
  } catch (e) {
    console.error('Failed to load repos:', e)
  }
}

async function loadAccessLog() {
  try {
    const res = await api('/admin/system-agent/access-log')
    accessLog.value = (res.log || []).reverse()
  } catch (e) {
    console.error('Failed to load access log:', e)
  }
}

async function addCredential() {
  try {
    const metadata = {}
    if (newCred.note) metadata.note = newCred.note
    await api('/admin/system-agent/credentials', {
      method: 'POST',
      body: JSON.stringify({
        name: newCred.name,
        type: newCred.type,
        value: newCred.value,
        metadata,
      }),
    })
    showAddForm.value = false
    resetForm()
    await loadCredentials()
    await loadStatus()
  } catch (e) {
    alert('添加失败: ' + (e.message || e))
  }
}

async function deleteCredential(cred) {
  if (!confirm(`确定删除凭据「${cred.name}」？`)) return
  try {
    await api(`/admin/system-agent/credentials/${cred.id}`, { method: 'DELETE' })
    await loadCredentials()
    await loadStatus()
  } catch (e) {
    alert('删除失败: ' + (e.message || e))
  }
}

async function cloneRepo() {
  try {
    await api('/admin/system-agent/execute', {
      method: 'POST',
      body: JSON.stringify({
        action: 'git_clone',
        params: { url: cloneUrl.value },
        requester: 'admin',
      }),
    })
    showCloneForm.value = false
    cloneUrl.value = ''
    await loadRepos()
    await loadStatus()
  } catch (e) {
    alert('Clone 失败: ' + (e.message || e))
  }
}

onMounted(() => {
  loadStatus()
  loadCredentials()
  loadRepos()
  loadAccessLog()
})
</script>

<style scoped>
.system-agent-panel {
  padding: 0;
}

.agent-status-card {
  background: linear-gradient(135deg, var(--accent, #2d6a4f) 0%, #1b4332 100%);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  color: #fff;
}
.status-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}
.status-icon {
  font-size: 20px;
}
.status-title {
  font-size: 16px;
  font-weight: 600;
  flex: 1;
}
.status-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 10px;
  background: rgba(255,255,255,0.2);
}
.status-badge.online {
  background: rgba(74, 222, 128, 0.3);
  color: #bbf7d0;
}
.status-stats {
  display: flex;
  gap: 24px;
}
.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
}
.stat-label {
  font-size: 12px;
  opacity: 0.8;
  margin-top: 2px;
}

.section {
  margin-bottom: 24px;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.section-header h3 {
  font-size: 15px;
  font-weight: 600;
  margin: 0;
}
.section-desc {
  font-size: 13px;
  color: var(--text-dim);
  margin: 0 0 12px;
  line-height: 1.5;
}

.btn-add, .btn-refresh {
  font-size: 13px;
  padding: 4px 12px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-card, #fff);
  color: var(--accent, #2d6a4f);
  cursor: pointer;
  font-weight: 500;
}
.btn-add:hover, .btn-refresh:hover {
  background: var(--accent, #2d6a4f);
  color: #fff;
}

/* Add Form */
.add-form {
  background: var(--bg-card, #fff);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 12px;
}
.form-row {
  margin-bottom: 12px;
}
.form-row label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  margin-bottom: 4px;
  color: var(--text-dim);
}
.form-row input,
.form-row select,
.form-row textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 14px;
  background: var(--bg, #faf9f7);
  color: var(--text);
  box-sizing: border-box;
  font-family: inherit;
}
.form-row textarea {
  resize: vertical;
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 13px;
}
.form-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}
.btn-cancel {
  padding: 6px 16px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-dim);
  cursor: pointer;
  font-size: 13px;
}
.btn-save {
  padding: 6px 16px;
  border-radius: 6px;
  border: none;
  background: var(--accent, #2d6a4f);
  color: #fff;
  cursor: pointer;
  font-size: 13px;
  font-weight: 500;
}
.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Credential List */
.cred-list, .repo-list, .log-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.empty-state {
  text-align: center;
  padding: 24px;
  color: var(--text-dim);
  font-size: 13px;
}
.cred-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  background: var(--bg-card, #fff);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.cred-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}
.cred-type-badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
  white-space: nowrap;
}
.cred-type-badge.github_pat {
  background: #dbeafe;
  color: #1e40af;
}
.cred-type-badge.ssh_key {
  background: #fef3c7;
  color: #92400e;
}
.cred-type-badge.api_key {
  background: #d1fae5;
  color: #065f46;
}
.cred-type-badge.custom {
  background: #f3e8ff;
  color: #6b21a8;
}
.cred-name {
  font-size: 14px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cred-preview {
  font-size: 12px;
  color: var(--text-dim);
  font-family: 'SF Mono', 'Fira Code', monospace;
  white-space: nowrap;
}
.cred-actions {
  display: flex;
  gap: 4px;
}
.btn-icon {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  padding: 4px;
  border-radius: 4px;
  opacity: 0.6;
}
.btn-icon:hover {
  opacity: 1;
  background: rgba(0,0,0,0.05);
}

/* Repo List */
.repo-item {
  padding: 12px 14px;
  background: var(--bg-card, #fff);
  border: 1px solid var(--border);
  border-radius: 8px;
}
.repo-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.repo-name {
  font-size: 14px;
  font-weight: 600;
}
.repo-branch {
  font-size: 12px;
  padding: 1px 6px;
  background: #d1fae5;
  color: #065f46;
  border-radius: 4px;
}
.repo-path {
  font-size: 12px;
  color: var(--text-dim);
  margin-top: 4px;
  font-family: 'SF Mono', 'Fira Code', monospace;
}

/* Access Log */
.log-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--bg-card, #fff);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
}
.log-time {
  color: var(--text-dim);
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
  white-space: nowrap;
}
.log-requester {
  font-weight: 500;
  color: var(--accent, #2d6a4f);
}
.log-action {
  color: var(--text);
  font-family: 'SF Mono', 'Fira Code', monospace;
  font-size: 12px;
}
</style>

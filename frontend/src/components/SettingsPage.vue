<template>
  <div class="page active">
    <div class="header"><h1>设置</h1></div>
    <div class="settings-page">
      <div class="settings-section">
        <div class="section-title">外观</div>
        <div class="setting-item" @click="toggleTheme">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
          <span class="setting-label">深色模式</span>
          <div class="toggle" :class="{ on: isDark }"></div>
        </div>
      </div>
      <div class="settings-section">
        <div class="section-title">聊天</div>
        <div class="setting-item" style="cursor:default;flex-wrap:wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>
          <span class="setting-label">工具调用显示</span>
          <div class="tool-display-options">
            <label class="radio-option" :class="{ active: chatSettings.toolCallDisplay === 'expanded' }">
              <input type="radio" name="tool-display" value="expanded" :checked="chatSettings.toolCallDisplay === 'expanded'" @change="onToolDisplayChange('expanded')">
              <span>展开</span>
            </label>
            <label class="radio-option" :class="{ active: chatSettings.toolCallDisplay === 'collapsed' }">
              <input type="radio" name="tool-display" value="collapsed" :checked="chatSettings.toolCallDisplay === 'collapsed'" @change="onToolDisplayChange('collapsed')">
              <span>折叠</span>
            </label>
            <label class="radio-option" :class="{ active: chatSettings.toolCallDisplay === 'collapsed-after-complete' }">
              <input type="radio" name="tool-display" value="collapsed-after-complete" :checked="chatSettings.toolCallDisplay === 'collapsed-after-complete'" @change="onToolDisplayChange('collapsed-after-complete')">
              <span>完成后折叠</span>
            </label>
          </div>
        </div>
      </div>
      <div class="settings-section">
        <div class="section-title">智能体执行</div>
        <div class="setting-item" style="cursor:default;flex-wrap:wrap">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
          <span class="setting-label">最大执行轮数</span>
          <span class="setting-desc">智能体单次响应的最大 API 调用轮数（每轮可执行多个工具），到达后自动停止</span>
          <div class="timeout-options">
            <label v-for="opt in roundOptions" :key="opt.value" class="radio-option" :class="{ active: hubSettings.agent_max_rounds === opt.value }">
              <input type="radio" name="rounds" :value="opt.value" :checked="hubSettings.agent_max_rounds === opt.value" @change="onRoundsChange(opt.value)">
              <span>{{ opt.label }}</span>
            </label>
          </div>
        </div>
      </div>
      <div class="settings-section">
        <div class="section-title">模型配置</div>
        <div class="setting-item" @click="showModels = true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>
          <span class="setting-label">供应商管理</span>
          <span class="setting-value">{{ models.length }} 个配置</span>
          <span class="chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg></span>
        </div>
      </div>
      <div class="settings-section">
        <div class="section-title">关于</div>
        <div class="setting-item" style="cursor:default">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
          <span class="setting-label">Hermes Hub</span>
          <span class="setting-value">v0.2.0</span>
        </div>
      </div>
    </div>

    <ModelsModal v-if="showModels" @close="showModels = false" @changed="loadModels" />
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { api, chatSettings, saveChatSettings } from '../store.js'
import ModelsModal from './ModelsModal.vue'

const isDark = ref(false)
const showModels = ref(false)
const models = ref([])
const hubSettings = reactive({
  agent_max_rounds: '50',
})

const roundOptions = [
  { label: '15 轮', value: '15' },
  { label: '30 轮', value: '30' },
  { label: '50 轮（推荐）', value: '50' },
  { label: '90 轮', value: '90' },
  { label: '无限制', value: '0' },
]

function toggleTheme() {
  isDark.value = !isDark.value
  if (isDark.value) {
    document.documentElement.setAttribute('data-theme', 'dark')
    localStorage.setItem('hub-theme', 'dark')
  } else {
    document.documentElement.removeAttribute('data-theme')
    localStorage.setItem('hub-theme', 'light')
  }
}

function onToolDisplayChange(val) {
  chatSettings.toolCallDisplay = val
  saveChatSettings()
}

async function onRoundsChange(val) {
  hubSettings.agent_max_rounds = val
  await api('PUT', '/admin/settings', { agent_max_rounds: val })
}

async function loadModels() {
  const data = await api('GET', '/admin/models')
  models.value = data.result || []
}

async function loadHubSettings() {
  try {
    const data = await api('GET', '/admin/settings')
    if (data.result) {
      Object.assign(hubSettings, data.result)
    }
  } catch {}
}

onMounted(async () => {
  isDark.value = localStorage.getItem('hub-theme') === 'dark'
  await loadModels()
  await loadHubSettings()
})
</script>

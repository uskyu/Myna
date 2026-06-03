<template>
  <div class="page active settings-shell">
    <div class="header"><h1>设置</h1></div>
    <div class="settings-page">
      <aside class="desktop-settings-nav" aria-label="设置分类">
        <button
          v-for="item in navItems"
          :key="item.id"
          type="button"
          class="settings-nav-item"
          :class="{ active: activeSection === item.id }"
          @pointerdown.prevent="selectSection(item.id)"
          @click="selectSection(item.id)"
        >
          <span class="nav-title">{{ item.label }}</span>
          <span class="nav-desc">{{ item.desc }}</span>
        </button>
      </aside>

      <main class="desktop-settings-detail">
        <section v-if="activeSection === 'quickstart'" class="detail-panel">
          <div class="detail-heading">
            <p class="eyebrow">Quick Start</p>
            <h2>样例模板 / 快速建队</h2>
            <p>选择一个模板，系统会自动创建或复用智能体，创建群聊并加入成员，完成后直接打开样例群聊。</p>
          </div>
          <div class="template-grid">
            <article v-for="tpl in teamTemplates" :key="tpl.id" class="template-card">
              <div class="template-card-head">
                <div>
                  <h3>{{ tpl.name }}</h3>
                  <p>{{ tpl.description }}</p>
                </div>
                <span class="member-count">{{ tpl.members.length }} 人</span>
              </div>
              <div class="role-list">
                <span v-for="member in tpl.members" :key="member.name" class="role-chip">{{ member.name }}</span>
              </div>
              <div v-if="templateResult[tpl.id]" class="template-status success">
                已创建「{{ templateResult[tpl.id].roomName }}」，{{ templateResult[tpl.id].memberCount }} 名成员已加入。
              </div>
              <div v-if="templateErrors[tpl.id]" class="template-status error">{{ templateErrors[tpl.id] }}</div>
              <button
                type="button"
                class="primary-action"
                :disabled="creatingTemplate === tpl.id"
                @click="createTemplateTeam(tpl)"
              >
                {{ creatingTemplate === tpl.id ? '正在创建...' : '一键创建并打开' }}
              </button>
            </article>
          </div>
        </section>

        <section v-else-if="activeSection === 'appearance'" class="detail-panel compact-panel">
          <div class="detail-heading">
            <p class="eyebrow">Appearance</p>
            <h2>外观</h2>
            <p>调整当前设备上的界面显示偏好。</p>
          </div>
          <button type="button" class="detail-row" @click="toggleTheme">
            <span>
              <strong>深色模式</strong>
              <small>切换暖白与深色显示，设置会保存在本机。</small>
            </span>
            <span class="toggle" :class="{ on: isDark }"></span>
          </button>
        </section>

        <section v-else-if="activeSection === 'models'" class="detail-panel compact-panel">
          <div class="detail-heading">
            <p class="eyebrow">Models</p>
            <h2>模型配置</h2>
            <p>管理模型供应商和可用配置。当前已有 {{ models.length }} 个配置。</p>
          </div>
          <div class="action-card">
            <div>
              <h3>供应商管理</h3>
              <p>打开模型配置窗口，新增、修改或删除模型供应商。</p>
            </div>
            <button type="button" class="secondary-action" @click="showModels = true">打开管理</button>
          </div>
        </section>

        <section v-else-if="activeSection === 'performance'" class="detail-panel performance-panel">
          <div class="detail-heading">
            <p class="eyebrow">Performance</p>
            <h2>系统性能</h2>
            <p>这些参数影响 Agent 调度、单次任务轮数和上下文窗口。输入框在桌面尺寸下完整可见，可直接编辑后保存。</p>
          </div>
          <div class="perf-grid">
            <article v-for="item in perfItems" :key="item.key" class="perf-card">
              <div>
                <h3>{{ item.label }}</h3>
                <p>{{ item.desc }}</p>
              </div>
              <label class="number-field">
                <span>{{ item.unit }}</span>
                <input
                  type="number"
                  v-model.number="perfSettings[item.key]"
                  :min="item.min"
                  :max="item.max"
                  @input="markPerfDirty"
                >
              </label>
            </article>
          </div>
          <div class="perf-actions">
            <p class="save-status" :class="perfStatusClass">{{ perfStatusText }}</p>
            <button type="button" class="primary-action narrow" :disabled="perfSaving" @click="savePerfSettings">
              {{ perfSaving ? '保存中...' : '保存系统性能' }}
            </button>
          </div>
        </section>

        <section v-else-if="activeSection === 'security'" class="detail-panel security-panel">
          <div class="detail-heading">
            <p class="eyebrow">Security</p>
            <h2>安全</h2>
            <p>修改登录密码或退出当前会话。</p>
          </div>
          <form class="desktop-pwd-form" @submit.prevent="doChangePassword">
            <label>
              <span>当前密码</span>
              <input type="password" v-model="currentPwd" autocomplete="current-password">
            </label>
            <label>
              <span>新密码</span>
              <input type="password" v-model="newPwd" autocomplete="new-password" placeholder="至少 4 位">
            </label>
            <label>
              <span>确认新密码</span>
              <input type="password" v-model="confirmPwd" autocomplete="new-password">
            </label>
            <p v-if="pwdError" class="error-text">{{ pwdError }}</p>
            <p v-if="pwdSuccess" class="success-text">{{ pwdSuccess }}</p>
            <div class="security-actions">
              <button type="submit" class="primary-action narrow">确认修改</button>
              <button type="button" class="danger-action" @click="doLogout">退出登录</button>
            </div>
          </form>
        </section>

        <section v-else class="detail-panel about-panel">
          <div class="detail-heading">
            <p class="eyebrow">About</p>
            <h2>关于 Myna</h2>
            <p>查看版本、检查更新和打开项目链接。</p>
          </div>
          <div class="about-list">
            <div class="about-row">
              <span>Myna</span>
              <strong>{{ (updateInfo.currentVersion || 'v0.3.7').replace(/^(?!v)/, 'v') }}</strong>
              <span v-if="updateInfo.available" class="update-dot"></span>
            </div>
            <button v-if="updateInfo.available && updateInfo.isDocker" type="button" class="about-row clickable" @click="handleUpdate">
              <span>{{ updateInfo.updating ? '更新中...' : '一键更新' }}</span>
              <strong class="amber-text">{{ updateInfo.latestVersion }}</strong>
            </button>
            <a v-else-if="updateInfo.available" class="about-row clickable" href="https://github.com/uskyu/myna/releases" target="_blank">
              <span>发现新版本</span>
              <strong class="amber-text">{{ updateInfo.latestVersion }}</strong>
            </a>
            <button v-else type="button" class="about-row clickable" @click="doCheckUpdate">
              <span>检查更新</span>
              <strong v-if="updateInfo.checking">检查中...</strong>
              <strong v-else-if="updateInfo.error" class="danger-text">{{ updateInfo.error }}</strong>
              <strong v-else-if="updateInfo.checked" class="green-text">已是最新</strong>
              <strong v-else>立即检查</strong>
            </button>
            <div v-if="updateInfo.updating" class="update-progress detail-progress">
              <div class="progress-bar">
                <div class="progress-fill" :style="{ width: updateInfo.percent + '%' }"></div>
              </div>
              <div class="progress-text">{{ updateInfo.message || '准备中...' }}</div>
            </div>
            <a class="about-row clickable" href="https://github.com/uskyu/myna" target="_blank">
              <span>GitHub 仓库</span>
              <strong>uskyu/myna</strong>
            </a>
            <a class="about-row clickable" href="https://github.com/uskyu/myna/releases" target="_blank">
              <span>更新日志</span>
              <strong>打开</strong>
            </a>
          </div>
        </section>
      </main>

      <div class="mobile-settings-stack">
        <div class="settings-section quickstart-section">
          <div class="section-title">快速开始</div>
          <div class="mobile-template-list">
            <div v-for="tpl in teamTemplates" :key="tpl.id" class="mobile-template-card">
              <div>
                <strong>{{ tpl.name }}</strong>
                <p>{{ tpl.members.map(m => m.name).join('、') }}</p>
              </div>
              <button type="button" class="mini-action" :disabled="creatingTemplate === tpl.id" @click="createTemplateTeam(tpl)">
                {{ creatingTemplate === tpl.id ? '创建中' : '创建' }}
              </button>
              <p v-if="templateResult[tpl.id]" class="template-status success">已创建「{{ templateResult[tpl.id].roomName }}」</p>
              <p v-if="templateErrors[tpl.id]" class="template-status error">{{ templateErrors[tpl.id] }}</p>
            </div>
          </div>
        </div>
        <div class="settings-section">
          <div class="section-title">外观</div>
          <div class="setting-item" @click="toggleTheme">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            <span class="setting-label">深色模式</span>
            <div class="toggle" :class="{ on: isDark }"></div>
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
          <div class="section-title">系统性能</div>
          <div v-for="item in perfItems" :key="item.key" class="setting-item" style="cursor:default">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 12h-4l-3 9L9 3l-3 9H2"/></svg>
            <span class="setting-label">{{ item.label }}</span>
            <div class="inline-input">
              <input type="number" v-model.number="perfSettings[item.key]" :min="item.min" :max="item.max" @input="markPerfDirty" class="mini-input">
            </div>
          </div>
          <div class="mobile-perf-save">
            <p class="setting-hint">并发数影响同时运行的 Agent；轮数限制单次对话 API 调用；上下文消息数影响智能体能看到的最近消息条数。</p>
            <button type="button" class="mini-action save" :disabled="perfSaving" @click="savePerfSettings">{{ perfSaving ? '保存中' : '保存' }}</button>
          </div>
          <p class="setting-hint" :class="perfStatusClass">{{ perfStatusText }}</p>
        </div>
        <div class="settings-section">
          <div class="section-title">安全</div>
          <div class="setting-item" @click="showChangePwd = true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            <span class="setting-label">修改密码</span>
            <span class="chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg></span>
          </div>
          <div class="setting-item" @click="doLogout">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>
            <span class="setting-label">退出登录</span>
          </div>
        </div>
        <div class="settings-section">
          <div class="section-title">关于</div>
          <div class="setting-item" style="cursor:default">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
            <span class="setting-label">Myna</span>
            <span class="setting-value">{{ (updateInfo.currentVersion || 'v0.3.7').replace(/^(?!v)/, 'v') }}</span>
            <span v-if="updateInfo.available" class="update-dot"></span>
          </div>
          <div v-if="updateInfo.available && updateInfo.isDocker" class="setting-item update-item" @click="handleUpdate" style="cursor:pointer">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
            <span class="setting-label">{{ updateInfo.updating ? '更新中...' : '一键更新' }}</span>
            <span class="setting-value amber-text">{{ updateInfo.latestVersion }}</span>
          </div>
          <div v-if="updateInfo.updating" class="update-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: updateInfo.percent + '%' }"></div>
            </div>
            <div class="progress-text">{{ updateInfo.message || '准备中...' }}</div>
          </div>
          <a v-else-if="updateInfo.available" class="setting-item update-item" href="https://github.com/uskyu/myna/releases" target="_blank" style="text-decoration:none;color:inherit">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
            <span class="setting-label">发现新版本</span>
            <span class="setting-value amber-text">{{ updateInfo.latestVersion }}</span>
            <span class="chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></span>
          </a>
          <div v-else class="setting-item" @click="doCheckUpdate" style="cursor:pointer">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/></svg>
            <span class="setting-label">检查更新</span>
            <span v-if="updateInfo.checking" class="setting-value">检查中...</span>
            <span v-else-if="updateInfo.error" class="setting-value danger-text">{{ updateInfo.error }}</span>
            <span v-else-if="updateInfo.checked" class="setting-value green-text">已是最新</span>
          </div>
          <a class="setting-item" href="https://github.com/uskyu/myna" target="_blank" style="text-decoration:none;color:inherit">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 19c-5 1.5-5-2.5-7-3m14 6v-3.87a3.37 3.37 0 0 0-.94-2.61c3.14-.35 6.44-1.54 6.44-7A5.44 5.44 0 0 0 20 4.77 5.07 5.07 0 0 0 19.91 1S18.73.65 16 2.48a13.38 13.38 0 0 0-7 0C6.27.65 5.09 1 5.09 1A5.07 5.07 0 0 0 5 4.77a5.44 5.44 0 0 0-1.5 3.78c0 5.42 3.3 6.61 6.44 7A3.37 3.37 0 0 0 9 18.13V22"/></svg>
            <span class="setting-label">GitHub 仓库</span>
            <span class="setting-value">uskyu/myna</span>
            <span class="chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></span>
          </a>
          <a class="setting-item" href="https://github.com/uskyu/myna/releases" target="_blank" style="text-decoration:none;color:inherit">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>
            <span class="setting-label">更新日志</span>
            <span class="chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></span>
          </a>
        </div>
      </div>
    </div>

    <ModelsModal v-if="showModels" @close="showModels = false" @changed="onModelsChanged" />

    <div v-if="showChangePwd" class="modal-overlay" @click.self="showChangePwd = false">
      <div class="modal-card">
        <h3>修改密码</h3>
        <form @submit.prevent="doChangePassword" class="pwd-form">
          <input type="password" v-model="currentPwd" placeholder="当前密码" />
          <input type="password" v-model="newPwd" placeholder="新密码（至少4位）" />
          <input type="password" v-model="confirmPwd" placeholder="确认新密码" />
          <p v-if="pwdError" class="error-text">{{ pwdError }}</p>
          <p v-if="pwdSuccess" class="success-text">{{ pwdSuccess }}</p>
          <div class="modal-actions">
            <button type="button" class="btn-cancel" @click="showChangePwd = false">取消</button>
            <button type="submit" class="btn-confirm">确认修改</button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="showUpdateConfirm" class="modal-overlay" @click.self="showUpdateConfirm = false">
      <div class="modal-card">
        <h3>发现新版本</h3>
        <div class="update-confirm-content">
          <p>检测到新版本 <strong class="green-text">{{ updateInfo.latestVersion }}</strong></p>
          <p class="confirm-hint">更新过程中容器将重启，正在进行的对话会中断。建议在空闲时更新。</p>
        </div>
        <div class="modal-actions">
          <button type="button" class="btn-cancel" @click="showUpdateConfirm = false">稍后</button>
          <button type="button" class="btn-confirm" @click="confirmUpdate">立即更新</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, reactive, ref, onMounted, onUnmounted } from 'vue'
import { api, clearAuth, setAuthToken, updateInfo, checkForUpdate, doUpdate, loadAgents, loadConversations, store, ws } from '../store.js'
import ModelsModal from './ModelsModal.vue'

const emit = defineEmits(['open-room'])

const isDark = ref(false)
const showModels = ref(false)
const showChangePwd = ref(false)
const showUpdateConfirm = ref(false)
const models = ref([])
const activeSection = ref('quickstart')
const perfSettings = reactive({ agent_concurrency: 10, agent_max_rounds: 50, context_messages_limit: 20 })
const perfSaving = ref(false)
const perfDirty = ref(false)
const perfMessage = ref('已加载当前配置')
const perfError = ref('')

const currentPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const pwdError = ref('')
const pwdSuccess = ref('')

const creatingTemplate = ref('')
const templateErrors = reactive({})
const templateResult = reactive({})

const navItems = [
  { id: 'quickstart', label: '快速开始', desc: '样例模板建队' },
  { id: 'appearance', label: '外观', desc: '主题显示' },
  { id: 'models', label: '模型配置', desc: '供应商管理' },
  { id: 'performance', label: '系统性能', desc: '并发与上下文' },
  { id: 'security', label: '安全', desc: '密码与登录' },
  { id: 'about', label: '关于', desc: '版本与更新' },
]

const perfItems = [
  { key: 'agent_concurrency', label: 'Agent 并发数', unit: '同时运行', min: 1, max: 100, desc: '控制系统同一时间最多调度多少个 Agent。提高数值可增强吞吐，但会增加模型调用和机器负载，通常重启后完整生效。' },
  { key: 'agent_max_rounds', label: '单次最大轮数', unit: '轮', min: 1, max: 500, desc: '限制一次对话或任务中最多执行多少轮 Agent/API 调用，避免复杂任务无限循环或成本失控。' },
  { key: 'context_messages_limit', label: '上下文消息数', unit: '条最近消息', min: 1, max: 200, desc: '决定智能体默认能看到多少条最近消息。数值越大上下文越完整，但 token 消耗也越高，房间仍可单独覆盖。' },
]

const teamTemplates = [
  {
    id: 'product-launch',
    name: '产品落地小队',
    description: '适合把一个想法拆成需求、界面、接口和验收清单。',
    roomDescription: '样例团队：围绕产品需求、前后端实现和测试验收协作。',
    members: [
      { name: '产品经理', description: '负责澄清目标、拆解需求、定义验收标准，并推动团队形成可落地方案。' },
      { name: '前端工程师', description: '负责页面结构、交互体验、状态管理和前端实现建议。' },
      { name: '后端工程师', description: '负责接口设计、数据流、服务端边界和轻后端实现建议。' },
      { name: '测试员', description: '负责测试用例、边界条件、回归验证和发布风险检查。' },
    ],
  },
  {
    id: 'content-creation',
    name: '内容创作小队',
    description: '适合从选题到资料、文案和视觉表达完整产出内容。',
    roomDescription: '样例团队：围绕内容策划、资料研究、文案编辑和视觉表达协作。',
    members: [
      { name: '选题策划', description: '负责定位受众、筛选选题角度、规划内容结构和传播目标。' },
      { name: '资料研究员', description: '负责收集事实、提炼资料、标注不确定信息并补充背景。' },
      { name: '文案编辑', description: '负责撰写、润色、统一语气，并把资料整理成可发布文本。' },
      { name: '视觉设计师', description: '负责画面风格、版式建议、封面方向和视觉素材提示词。' },
    ],
  },
  {
    id: 'code-fix',
    name: '代码修复小队',
    description: '适合定位 bug、实施修复、审查风险并设计回归验证。',
    roomDescription: '样例团队：围绕问题定位、代码实现、审查和回归测试协作。',
    members: [
      { name: '问题定位员', description: '负责复现问题、缩小范围、分析日志和提出根因假设。' },
      { name: '实现工程师', description: '负责以最小改动实现修复，并说明关键取舍。' },
      { name: '代码审查员', description: '负责检查行为回归、边界条件、安全风险和维护性。' },
      { name: '回归测试员', description: '负责设计验证步骤、覆盖关键路径并整理验收结果。' },
    ],
  },
]

const perfStatusClass = computed(() => ({
  success: !perfDirty.value && !perfError.value,
  error: !!perfError.value,
  pending: perfDirty.value && !perfError.value,
}))

const perfStatusText = computed(() => {
  if (perfError.value) return perfError.value
  if (perfSaving.value) return '正在保存系统性能配置...'
  if (perfDirty.value) return '有未保存的修改，请点击保存。'
  return perfMessage.value
})

function selectSection(id) {
  activeSection.value = id
}

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

async function doChangePassword() {
  pwdError.value = ''
  pwdSuccess.value = ''
  if (!currentPwd.value || !newPwd.value) {
    pwdError.value = '请填写所有字段'
    return
  }
  if (newPwd.value.length < 4) {
    pwdError.value = '新密码至少4位'
    return
  }
  if (newPwd.value !== confirmPwd.value) {
    pwdError.value = '两次密码不一致'
    return
  }
  const res = await api('POST', '/auth/change-password', {
    current_password: currentPwd.value,
    new_password: newPwd.value,
  })
  if (res.ok) {
    pwdSuccess.value = '密码已修改'
    currentPwd.value = ''
    newPwd.value = ''
    confirmPwd.value = ''
    if (res.token) setAuthToken(res.token)
    setTimeout(() => { showChangePwd.value = false }, 1500)
  } else {
    pwdError.value = res.error || '修改失败'
  }
}

function doLogout() {
  clearAuth()
  location.reload()
}

async function doCheckUpdate() {
  await checkForUpdate()
}

async function handleUpdate() {
  if (updateInfo.updating) return
  showUpdateConfirm.value = true
}

async function confirmUpdate() {
  showUpdateConfirm.value = false
  await doUpdate()
}

async function loadModels() {
  const data = await api('GET', '/admin/models')
  models.value = data.result || []
}

async function onModelsChanged() {
  await loadModels()
  showModels.value = false
}

async function loadPerfSettings() {
  const data = await api('GET', '/admin/settings')
  if (data.ok && data.result) {
    perfSettings.agent_concurrency = parseInt(data.result.agent_concurrency) || 10
    perfSettings.agent_max_rounds = parseInt(data.result.agent_max_rounds) || 50
    perfSettings.context_messages_limit = parseInt(data.result.context_messages_limit) || 20
    perfDirty.value = false
    perfError.value = ''
    perfMessage.value = '已加载当前配置'
  }
}

function markPerfDirty() {
  perfDirty.value = true
  perfError.value = ''
}

function normalizePerfValue(key, fallback) {
  const value = parseInt(perfSettings[key])
  return Number.isFinite(value) && value > 0 ? value : fallback
}

async function savePerfSettings() {
  perfSaving.value = true
  perfError.value = ''
  const payload = {
    agent_concurrency: String(normalizePerfValue('agent_concurrency', 10)),
    agent_max_rounds: String(normalizePerfValue('agent_max_rounds', 50)),
    context_messages_limit: String(normalizePerfValue('context_messages_limit', 20)),
  }
  const res = await api('PUT', '/admin/settings', payload)
  perfSaving.value = false
  if (res.ok === false) {
    perfError.value = res.error || '保存失败，请重试'
    return
  }
  perfSettings.agent_concurrency = parseInt(payload.agent_concurrency)
  perfSettings.agent_max_rounds = parseInt(payload.agent_max_rounds)
  perfSettings.context_messages_limit = parseInt(payload.context_messages_limit)
  perfDirty.value = false
  perfMessage.value = '系统性能配置已保存'
}

function setTemplateError(id, message) {
  templateErrors[id] = message
  delete templateResult[id]
}

function clearTemplateState(id) {
  templateErrors[id] = ''
  delete templateResult[id]
}

async function createTemplateTeam(template) {
  if (creatingTemplate.value) return
  creatingTemplate.value = template.id
  clearTemplateState(template.id)
  try {
    const agentData = await api('GET', '/admin/agents')
    if (agentData.ok === false) throw new Error(agentData.error || '读取智能体失败')
    const existingAgents = agentData.result || []
    const createdOrReused = []

    for (const member of template.members) {
      let agent = existingAgents.find(a => a.name === member.name && a.id !== 'system' && a.id !== 'user')
      if (!agent) {
        const created = await api('POST', '/admin/agents', { name: member.name, description: member.description })
        if (created.ok === false || !created.result) throw new Error(created.error || `创建智能体「${member.name}」失败`)
        agent = created.result
        existingAgents.push(agent)
      }
      createdOrReused.push(agent)
    }

    const now = new Date().toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
    const roomName = `样例：${template.name} ${now}`
    const roomData = await api('POST', '/admin/rooms', { name: roomName, description: template.roomDescription })
    if (roomData.ok === false || !roomData.result) throw new Error(roomData.error || '创建群聊失败')
    const room = roomData.result

    for (const agent of createdOrReused) {
      const memberData = await api('POST', `/admin/rooms/${room.id}/members`, { agent_id: agent.id })
      if (memberData.ok === false) throw new Error(memberData.error || `加入成员「${agent.name}」失败`)
    }

    await Promise.all([loadAgents(), loadConversations()])
    const openedRoom = store.rooms.find(r => r.id === room.id) || { ...room, members: createdOrReused }
    templateResult[template.id] = { roomName, memberCount: createdOrReused.length }
    emit('open-room', openedRoom)
  } catch (e) {
    setTemplateError(template.id, e.message || '创建失败，请稍后重试')
  } finally {
    creatingTemplate.value = ''
  }
}

let updateHandler

onMounted(async () => {
  isDark.value = localStorage.getItem('hub-theme') === 'dark'
  await loadModels()
  await loadPerfSettings()

  updateHandler = (msg) => {
    if (msg.type === 'update_available' && updateInfo.isDocker) {
      showUpdateConfirm.value = true
    }
  }
  ws.onMessage(updateHandler)
})

onUnmounted(() => {
  if (!updateHandler) return
  ws.offMessage(updateHandler)
})
</script>

<style scoped>
.desktop-settings-nav,
.desktop-settings-detail {
  display: none;
}

.mobile-settings-stack {
  display: block;
}

.quickstart-section {
  background: #faf9f7;
}

[data-theme="dark"] .quickstart-section {
  background: var(--surface);
}

.mobile-template-list {
  display: grid;
  gap: 10px;
  padding: 12px 14px 16px;
  border-top: 1px solid var(--border);
}

.mobile-template-card {
  border: 1px solid rgba(45, 106, 79, 0.18);
  border-radius: 12px;
  padding: 12px;
  background: var(--surface);
}

.mobile-template-card strong {
  color: var(--text);
  font-size: 14px;
}

.mobile-template-card p {
  margin: 5px 0 10px;
  color: var(--text-dim);
  font-size: 12px;
  line-height: 1.5;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}
.modal-card {
  background: white;
  border-radius: 14px;
  padding: 24px;
  width: 90%;
  max-width: 360px;
}
[data-theme="dark"] .modal-card {
  background: #2a2a2a;
  color: #e5e5e5;
}
.modal-card h3 {
  margin: 0 0 16px;
  font-size: 17px;
}
.pwd-form {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.pwd-form input {
  padding: 10px 14px;
  border: 1.5px solid #e0e0e0;
  border-radius: 8px;
  font-size: 14px;
  outline: none;
}
[data-theme="dark"] .pwd-form input {
  background: #1a1a1a;
  border-color: #444;
  color: #e5e5e5;
}
.pwd-form input:focus {
  border-color: var(--accent, #2d6a4f);
}
.error-text { color: #e53e3e; font-size: 13px; margin: 0; }
.success-text { color: var(--accent, #2d6a4f); font-size: 13px; margin: 0; }
.modal-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}
.btn-cancel {
  flex: 1;
  padding: 10px;
  border: 1.5px solid #e0e0e0;
  border-radius: 8px;
  background: none;
  cursor: pointer;
  font-size: 14px;
}
[data-theme="dark"] .btn-cancel {
  border-color: #444;
  color: #e5e5e5;
}
.btn-confirm {
  flex: 1;
  padding: 10px;
  border: none;
  border-radius: 8px;
  background: var(--accent, #2d6a4f);
  color: white;
  cursor: pointer;
  font-size: 14px;
}
.update-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #e53e3e;
  flex-shrink: 0;
  margin-left: 6px;
}
.update-item {
  background: rgba(217, 119, 6, 0.06);
  border-radius: 8px;
}
.inline-input {
  margin-left: auto;
  flex-shrink: 0;
}
.mini-input {
  width: 78px;
  padding: 6px 10px;
  border: 1.5px solid var(--border, #e0e0e0);
  border-radius: 6px;
  font-size: 14px;
  text-align: center;
  background: var(--surface, #fff);
  color: var(--text, #1a1a1a);
}
.mini-input:focus {
  outline: none;
  border-color: var(--accent, #2d6a4f);
}
[data-theme="dark"] .mini-input {
  background: #2a2a2a;
  border-color: #444;
  color: #e5e5e5;
}
.setting-hint {
  font-size: 12px;
  color: var(--text-dim, #999);
  margin: 4px 0 0 0;
  padding: 0 4px;
  line-height: 1.5;
}
.mobile-perf-save {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 12px 18px 4px;
  border-top: 1px solid var(--border);
}
.mini-action {
  border: none;
  border-radius: 9px;
  background: #2d6a4f;
  color: white;
  font-weight: 700;
  padding: 8px 12px;
  cursor: pointer;
}
.mini-action.save {
  background: #d97706;
}
.mini-action:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}
.template-status {
  border-radius: 10px;
  font-size: 12px;
  line-height: 1.45;
}
.template-status.success,
.save-status.success,
.setting-hint.success {
  color: #2d6a4f;
}
.template-status.error,
.save-status.error,
.setting-hint.error,
.danger-text {
  color: #e53e3e;
}
.save-status.pending,
.setting-hint.pending,
.amber-text {
  color: #d97706;
}
.green-text {
  color: #2d6a4f;
}

.update-progress {
  padding: 8px 16px 12px;
  margin: -4px 0 8px;
}
.progress-bar {
  height: 6px;
  background: var(--border, #e0e0e0);
  border-radius: 3px;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2d6a4f, #40916c);
  border-radius: 3px;
  transition: width 0.3s ease;
}
.progress-text {
  font-size: 11px;
  color: var(--text-dim, #999);
  margin-top: 4px;
  text-align: center;
}
.confirm-hint {
  color: var(--text-secondary,#666);
  font-size: 0.9em;
  margin-top: 0.5em;
}

@media (min-width: 768px) {
  :global(.desktop-workspace-panel .settings-shell) {
    display: flex;
    flex-direction: column;
    min-height: 0;
  }

  :global(.desktop-workspace-panel .settings-page) {
    display: grid !important;
    grid-template-columns: 236px minmax(0, 1fr) !important;
    gap: 20px;
    flex: 1;
    min-height: 0;
    overflow: hidden;
    padding: 20px 24px 24px;
    align-content: stretch;
  }

  .mobile-settings-stack {
    display: none;
  }

  .desktop-settings-nav {
    display: flex;
    flex-direction: column;
    gap: 8px;
    min-height: 0;
    overflow-y: auto;
    padding: 14px;
    border: 1px solid rgba(45, 106, 79, 0.18);
    border-radius: 20px;
    background: #faf9f7;
    box-shadow: var(--shadow-sm);
  }

  [data-theme="dark"] .desktop-settings-nav {
    background: var(--surface);
    border-color: var(--border);
  }

  .settings-nav-item {
    border: 1px solid transparent;
    border-radius: 14px;
    background: transparent;
    color: var(--text);
    text-align: left;
    padding: 12px 13px;
    cursor: pointer;
    transition: background 0.15s ease, border-color 0.15s ease, color 0.15s ease;
  }

  .settings-nav-item:hover {
    background: rgba(45, 106, 79, 0.07);
  }

  .settings-nav-item.active {
    background: rgba(45, 106, 79, 0.12);
    border-color: rgba(45, 106, 79, 0.28);
    color: #2d6a4f;
  }

  .nav-title,
  .nav-desc {
    display: block;
  }

  .nav-title {
    font-size: 14px;
    font-weight: 800;
  }

  .nav-desc {
    margin-top: 4px;
    font-size: 12px;
    color: var(--text-dim);
    line-height: 1.3;
  }

  .desktop-settings-detail {
    display: block;
    min-width: 0;
    min-height: 0;
    overflow-y: auto;
    overflow-x: hidden;
    padding-right: 2px;
  }

  .detail-panel {
    min-height: min(620px, 100%);
    border: 1px solid rgba(45, 106, 79, 0.16);
    border-radius: 24px;
    background: var(--surface, #fff);
    box-shadow: var(--shadow-sm);
    padding: clamp(20px, 2.2vw, 32px);
  }

  .compact-panel {
    max-width: 860px;
  }

  .detail-heading {
    max-width: 780px;
    margin-bottom: 22px;
  }

  .eyebrow {
    margin: 0 0 8px;
    color: #d97706;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .detail-heading h2 {
    margin: 0;
    color: var(--text);
    font-size: clamp(22px, 2vw, 30px);
    letter-spacing: -0.04em;
  }

  .detail-heading p:not(.eyebrow) {
    margin: 10px 0 0;
    color: var(--text-dim);
    font-size: 14px;
    line-height: 1.7;
  }

  .template-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 16px;
  }

  .template-card,
  .action-card,
  .perf-card,
  .about-row,
  .detail-row {
    border: 1px solid var(--border);
    background: #faf9f7;
    border-radius: 18px;
  }

  [data-theme="dark"] .template-card,
  [data-theme="dark"] .action-card,
  [data-theme="dark"] .perf-card,
  [data-theme="dark"] .about-row,
  [data-theme="dark"] .detail-row {
    background: var(--surface2);
  }

  .template-card {
    display: flex;
    flex-direction: column;
    gap: 16px;
    padding: 18px;
  }

  .template-card-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 12px;
  }

  .template-card h3,
  .action-card h3,
  .perf-card h3 {
    margin: 0;
    color: var(--text);
    font-size: 16px;
  }

  .template-card p,
  .action-card p,
  .perf-card p {
    margin: 7px 0 0;
    color: var(--text-dim);
    font-size: 13px;
    line-height: 1.6;
  }

  .member-count {
    flex-shrink: 0;
    border-radius: 999px;
    background: rgba(217, 119, 6, 0.12);
    color: #d97706;
    font-size: 12px;
    font-weight: 800;
    padding: 6px 10px;
  }

  .role-list {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .role-chip {
    border: 1px solid rgba(45, 106, 79, 0.18);
    border-radius: 999px;
    color: #2d6a4f;
    background: rgba(45, 106, 79, 0.07);
    font-size: 12px;
    font-weight: 700;
    padding: 6px 9px;
  }

  .primary-action,
  .secondary-action,
  .danger-action {
    border: none;
    border-radius: 13px;
    color: white;
    font-weight: 800;
    padding: 11px 16px;
    cursor: pointer;
  }

  .primary-action {
    background: #2d6a4f;
  }

  .secondary-action {
    background: #d97706;
  }

  .danger-action {
    background: #9b2c2c;
  }

  .primary-action.narrow {
    width: fit-content;
  }

  .primary-action:disabled,
  .secondary-action:disabled {
    opacity: 0.65;
    cursor: not-allowed;
  }

  .detail-row,
  .action-card,
  .about-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 18px;
  }

  .detail-row {
    width: 100%;
    color: var(--text);
    cursor: pointer;
  }

  .detail-row strong {
    display: block;
    font-size: 16px;
  }

  .detail-row small {
    display: block;
    margin-top: 6px;
    color: var(--text-dim);
    font-size: 13px;
  }

  .performance-panel {
    display: flex;
    flex-direction: column;
  }

  .perf-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }

  .perf-card {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: 18px;
    min-height: 240px;
    padding: 18px;
  }

  .number-field {
    display: grid;
    gap: 8px;
  }

  .number-field span {
    color: var(--text-dim);
    font-size: 12px;
    font-weight: 800;
  }

  .number-field input,
  .desktop-pwd-form input {
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
    border: 1.5px solid var(--border);
    border-radius: 13px;
    background: var(--surface);
    color: var(--text);
    font-size: 16px;
    padding: 12px 13px;
    outline: none;
  }

  .number-field input:focus,
  .desktop-pwd-form input:focus {
    border-color: #2d6a4f;
    box-shadow: 0 0 0 3px rgba(45, 106, 79, 0.12);
  }

  .perf-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
    margin-top: 18px;
    padding-top: 18px;
    border-top: 1px solid var(--border);
  }

  .save-status {
    margin: 0;
    color: var(--text-dim);
    font-size: 13px;
  }

  .desktop-pwd-form {
    display: grid;
    gap: 14px;
    max-width: 560px;
  }

  .desktop-pwd-form label {
    display: grid;
    gap: 7px;
  }

  .desktop-pwd-form label span {
    color: var(--text-dim);
    font-size: 13px;
    font-weight: 800;
  }

  .security-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-top: 4px;
  }

  .about-list {
    display: grid;
    gap: 10px;
    max-width: 760px;
  }

  .about-row {
    color: var(--text);
    text-decoration: none;
  }

  .about-row.clickable {
    cursor: pointer;
  }

  .about-row strong {
    font-size: 13px;
  }

  .detail-progress {
    margin: 0;
    padding: 2px 2px 8px;
  }
}

@media (min-width: 768px) and (max-width: 1180px) {
  :global(.desktop-workspace-panel .settings-page) {
    grid-template-columns: 214px minmax(0, 1fr) !important;
    gap: 16px;
    padding: 18px;
  }

  .perf-grid {
    grid-template-columns: 1fr;
  }

  .perf-card {
    min-height: 0;
  }

  .detail-panel {
    min-height: 0;
  }
}

@media (min-width: 1181px) and (max-height: 820px) {
  .perf-card {
    min-height: 210px;
  }

  .detail-heading {
    margin-bottom: 16px;
  }
}
</style>

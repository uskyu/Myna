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
      <button class="thread-toggle-btn" @click="shareChatContent" title="分享聊天链接" aria-label="分享聊天链接">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><path d="M8.59 13.51l6.83 3.98M15.41 6.51L8.59 10.49"/></svg>
      </button>
      <button v-if="type === 'group'" class="more-btn" :class="{ active: showSettings }" @click="showSettings = !showSettings" :title="showSettings ? '返回聊天' : '群聊信息'">
        <svg v-if="!showSettings" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/></svg>
        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M18 6L6 18M6 6l12 12"/></svg>
      </button>
    </div>

    <!-- Group info panel (replaces messages area when active) -->
    <div v-if="type === 'group' && showSettings" class="group-info-panel">
      <RoomInfoPanel ref="roomInfoPanel" :room="room" @changed="onMembersChanged" @close="showSettings = false" @deleted="$emit('close')" @create-agent="showSettings = false; $emit('close')" />
    </div>

    <!-- Chat body with optional thread panel -->
    <div v-if="messages.length" class="perf-bar" aria-label="当前已加载消息统计">
      <span title="当前已加载的用户消息数，不等于模型调用次数">用户提问 {{ sessionStats.turns }} 次</span>
      <span title="已记录回复的总处理时间，包含工具执行，不是纯模型耗时">总处理耗时 {{ sessionStats.hasTime ? fmtMs(totalLlmMs) : '未采集' }}</span>
      <span title="请求开始到首次输出文本的平均时间">平均首字等待 {{ sessionStats.avgTtft != null ? fmtMs(sessionStats.avgTtft) : '未采集' }}</span>
      <span title="仅按提供缓存数据的回复计算：缓存读取 Token / 输入 Token">输入缓存占比 {{ sessionStats.cachePct != null ? sessionStats.cachePct + '%' : '未提供' }}</span>
      <span title="模型读取的上下文量，不是字数；缺失的历史记录无法还原">输入 Token {{ sessionStats.hasUsage ? fmtK(sessionStats.inTok) : '未采集' }}</span>
      <span title="模型生成的 Token 数，不是字数；仅累计有统计的回复">输出 Token {{ sessionStats.hasUsage ? fmtK(sessionStats.outTok) : '未采集' }}</span>
    </div>
  <div v-if="!(type === 'group' && showSettings)" class="chat-body-wrapper">
      <!-- Messages area -->
      <div class="messages-area" ref="messagesArea" @scroll="onScroll">
      <template v-for="(group, gi) in messageGroups" :key="gi">
        <div v-if="group.separator" class="time-separator"><span>{{ group.separator }}</span></div>
        <div class="msg-group" :class="{ self: group.self, event: group.event }">
          <div
            v-for="(msg, mi) in group.messages"
            :key="msg.id || mi"
            class="msg"
            :class="{ self: group.self, streaming: msg.streaming, event: msg.event, rich: msg.event && msg.text && (String(msg.text).length > 80 || String(msg.text).includes('\n')), 'has-citations': msg.sources?.length }"
          >
            <div v-if="msg.showName" class="sender-name">{{ msg.sender_name }}</div>
            <div v-if="msg.sources?.length" class="message-citations" aria-label="网页来源">
              <a v-for="source in msg.sources" :key="source.url" class="citation-badge" :href="source.url" target="_blank" rel="noopener noreferrer" :title="`来源 ${source.index}：${source.host}`">[{{ source.index }}]</a>
            </div>
            <div v-if="getThinkingEvents(msg).length || getProcessTools(msg).length" class="thinking-bubble" :class="{ collapsed: !msg.thinkingExpanded }">
              <div class="thinking-header" @click.stop="toggleThinkingExpand(msg)">
                <span class="thinking-dot" :class="{ active: msg.streaming }"></span>
                <span class="thinking-label">执行过程</span>
                <span class="thinking-count">{{ getThinkingEvents(msg).length || getProcessTools(msg).length }} 步</span>
                <svg class="thinking-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
              </div>
              <div v-if="!msg.thinkingExpanded" class="thinking-summary"><span v-html="getThinkingSummary(msg)"></span></div>
              <div v-if="msg.thinkingExpanded" class="thinking-steps">
                <div v-for="(ev, ei) in getThinkingEvents(msg)" :key="`ev-${ei}`" class="thinking-step" :class="{ running: ev.status === 'running', error: ev.status === 'error' }">
                  <span v-if="thinkingStageLabel(ev.stage)" class="thinking-step-stage">{{ thinkingStageLabel(ev.stage) }}</span>
                  <span class="thinking-step-content">{{ processEventText(ev) }}</span>
                </div>
                <div v-if="getProcessTools(msg).length" class="process-tool-list">
                  <div v-for="(tc, ti) in getProcessTools(msg)" :key="`tool-${ti}`" class="process-tool-card" :class="{ running: tc.status === 'running', done: tc.status === 'done', error: tc.status === 'error' }">
                    <div class="process-tool-head">
                      <span class="process-tool-status">{{ toolStatusLabel(tc.status) }}</span>
                      <span class="process-tool-name">{{ toolLabel(cleanText(tc.name || tc.tool) || 'tool') }}</span>
                    </div>
                    <div v-if="cleanText(tc.summary || tc.args_summary)" class="process-tool-summary">{{ cleanText(tc.summary || tc.args_summary) }}</div>
                    <div v-if="cleanText(tc.result)" class="process-tool-result" :class="{ error: tc.status === 'error' }">{{ cleanText(tc.result) }}</div>
                  </div>
                </div>
              </div>
            </div>
            <!-- Text/tools content in chronological order -->
            <template v-if="msg.parts && msg.parts.length">
              <template v-for="(part, pi) in msg.parts" :key="pi">
                <div v-if="part.type === 'tool' && !getProcessTools(msg).length" class="working-bubble inline-tool" :class="{ collapsed: !getPartToolExpanded(msg, pi), done: part.status !== 'running' }">
                  <div class="working-header" @click.stop="togglePartToolExpand(msg, pi)">
                    <div v-if="part.status === 'running'" class="working-spinner"></div>
                    <svg v-else-if="part.status === 'done'" class="working-done-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
                    <svg v-else class="working-done-icon error" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
                    <span class="working-label">{{ part.status === 'running' ? '调用工具' : '工具完成' }}</span>
                    <span class="working-count">{{ toolLabel(part.name) }}</span>
                    <svg class="working-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
                  </div>
                  <div v-if="getPartToolExpanded(msg, pi)" class="working-steps">
                    <div class="tool-step" :class="{ running: part.status === 'running', done: part.status === 'done', error: part.status === 'error' }">
                      <div class="step-icon">
                        <svg v-if="part.status === 'running'" class="spin-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                        <svg v-else-if="part.status === 'done'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
                        <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
                      </div>
                      <div class="step-body">
                        <div class="step-name">{{ toolLabel(part.name) }}</div>
                        <div class="step-summary">{{ part.summary }}</div>
                        <div v-if="part.result" class="step-result" :class="{ error: part.status === 'error' }">{{ part.result }}</div>
                      </div>
                    </div>
                  </div>
                </div>
                <div v-else-if="part.type === 'text'" class="msg-text" v-html="part.rendered + (msg.streaming && pi === msg.parts.length - 1 ? '<span class=stream-cursor>▊</span>' : '')"></div>
              </template>
            </template>
            <template v-else>
              <!-- Working bubble (tool calls - streaming or saved) -->
              <div v-if="msg.toolCalls && msg.toolCalls.length" class="working-bubble" :class="{ collapsed: !msg.toolsExpanded, done: !msg.streaming }">
                <div class="working-header" @click.stop="toggleToolsExpand(msg)">
                  <div v-if="msg.streaming" class="working-spinner"></div>
                  <svg v-else class="working-done-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
                  <span class="working-label">{{ msg.streaming ? '工作中' : '工具调用' }}</span>
                  <span class="working-count">{{ msg.toolCalls.length }} 步</span>
                  <svg class="working-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
                </div>
                <div v-if="msg.toolsExpanded" class="working-steps">
                  <div v-for="(tc, ti) in msg.toolCalls" :key="ti" class="tool-step" :class="{ running: tc.status === 'running', done: tc.status === 'done', error: tc.status === 'error', flash: tc.flash }">
                    <div class="step-icon">
                      <svg v-if="tc.status === 'running'" class="spin-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>
                      <svg v-else-if="tc.status === 'done'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M20 6L9 17l-5-5"/></svg>
                      <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M18 6L6 18M6 6l12 12"/></svg>
                    </div>
                    <div class="step-body">
                      <div class="step-name">{{ toolLabel(tc.name) }}</div>
                      <div class="step-summary">{{ tc.summary }}</div>
                      <div v-if="tc.result" class="step-result" :class="{ error: tc.status === 'error' }">{{ tc.result }}</div>
                    </div>
                  </div>
                </div>
              </div>
              <!-- Text content (shown after tools or for non-tool messages) -->
              <div v-if="msg.streaming && !msg.text && msg.toolCalls && msg.toolCalls.length" class="msg-text working-placeholder"></div>
              <div v-else class="msg-text" v-html="msg.streaming ? (msg.rendered + '<span class=stream-cursor>▊</span>') : msg.rendered"></div>
            </template>
            <div v-if="msg.projectProposal" class="project-proposal-card">
              <div class="project-proposal-kicker">多智能体协同建议</div>
              <h3>{{ msg.projectProposal.project_name }}</h3>
              <p>{{ msg.projectProposal.summary }}</p>
              <div class="project-role" v-for="role in msg.projectProposal.roles" :key="role.name">
                <strong>{{ role.name }}</strong><span>{{ role.responsibility }}</span>
              </div>
              <div class="project-proposal-actions">
                <span v-if="projectCreationState[msg.id]?.created" class="project-created">项目已创建</span>
                <button v-else class="project-confirm-btn" :disabled="projectCreationState[msg.id]?.loading" @click.stop="confirmProjectProposal(msg)">{{ projectCreationState[msg.id]?.loading ? '创建中...' : '确认创建项目' }}</button>
              </div>
            </div>
            <div class="msg-meta-row">
              <span v-if="msg.model" class="msg-model">{{ msg.modelName }}</span>
              <span v-if="!isSkillStatusMessage(msg)" class="msg-time">{{ msg.streaming ? (msg.text ? '生成中...' : '思考中...') : msg.time }}</span>
              <!-- Message actions (edit/delete/mention/retry/copy) — always visible for non-streaming -->
              <span v-if="!msg.streaming && !String(msg.id).startsWith('tmp-') && !String(msg.id).startsWith('stream-')" class="msg-actions">
                <button class="msg-action-btn danger" @click.stop="deleteMsg(msg)" title="删除">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                </button>
                <button class="msg-action-btn" @click.stop="startEditMsg(msg)" title="编辑">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                </button>
                <button v-if="group.self" class="msg-action-btn retry-btn" @click.stop="retryMsg(msg)" title="重试">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><path d="M1 4v6h6M23 20v-6h-6"/><path d="M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15"/></svg>
                </button>
                <button v-if="!group.self" class="msg-action-btn copy-btn" @click.stop="copyMsg(msg)" title="复制">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                </button>
                <button v-if="!group.self && msg.sender_name" class="msg-action-btn mention-btn" @click.stop="onMentionClick(msg)" title="@提及">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="12" height="12"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94"/></svg>
                </button>
              </span>
            </div>
            <!-- Inline edit textarea -->
            <div v-if="editingMsgId === msg.id" class="msg-edit-box" @click.stop>
              <textarea v-model="editingMsgText" rows="2" class="msg-edit-input" @keydown.enter.ctrl.prevent="saveEditMsg(msg)" @keydown.escape="cancelEditMsg"></textarea>
              <div class="msg-edit-actions">
                <button class="msg-edit-save" @click.stop="saveEditMsg(msg)">保存</button>
                <button class="msg-edit-cancel" @click.stop="cancelEditMsg">取消</button>
              </div>
            </div>
            <!-- Stop button for streaming messages -->
            <button v-if="msg.streaming" class="stop-stream-btn" @click.stop="cancelStream(msg)">⏹ 停止</button>
            <!-- P0: Handoff chain status bubble -->
            <div v-if="msg.handoffInfo && !msg.self" class="handoff-bubble" :class="{ suppressed: msg.handoffInfo.suppressed && msg.handoffInfo.suppressed.length > 0 }">
              <template v-if="msg.handoffInfo.targets && msg.handoffInfo.targets.length > 0">
                <span class="handoff-arrow">→</span>
                <span class="handoff-targets">{{ msg.handoffInfo.targets.map(id => { const a = store.agents.find(x => x.id === id); return a ? '@' + a.name : id.slice(0,8) }).join(' → ') }}</span>
                <span class="handoff-depth" v-if="msg.handoffInfo.chain_depth > 0">第{{ msg.handoffInfo.chain_depth + 1 }}轮</span>
              </template>
              <template v-if="msg.handoffInfo.suppressed && msg.handoffInfo.suppressed.length > 0">
                <div class="handoff-suppressed">
                  <span v-for="(s, si) in msg.handoffInfo.suppressed" :key="si" class="suppressed-item">
                    <template v-if="store.agents.find(x => x.id === s.target)">
                      @{{ store.agents.find(x => x.id === s.target).name }}
                    </template>
                    <template v-else>{{ (s.target || '').slice(0,8) }}</template>
                    已抑制: {{ s.reason }}
                  </span>
                </div>
              </template>
            </div>
          </div>
        </div>
      </template>
      <div v-if="typingAgent" class="typing-indicator active">
        <span style="font-size:12px;color:var(--text-dim);margin-right:4px">{{ typingAgent }}</span>
        <div class="dots"><span></span><span></span><span></span></div>
      </div>
      </div>

    </div>
    <!-- Approval dialog -->
    <div v-if="pendingApproval" class="approval-overlay">
      <div class="approval-dialog">
        <div class="approval-header">
          <span class="approval-icon">⚠️</span>
          <span class="approval-title">命令审批</span>
        </div>
        <div class="approval-agent">{{ pendingApproval.agentName }} 请求执行：</div>
        <div class="approval-command"><code>{{ pendingApproval.command }}</code></div>
        <div v-if="pendingApproval.description" class="approval-desc">{{ pendingApproval.description }}</div>
        <div class="approval-actions">
          <button class="approval-btn deny" @click="respondApproval('deny')">拒绝</button>
          <button class="approval-btn approve" @click="respondApproval('once')">允许执行</button>
          <button class="approval-btn approve-all" @click="respondApproval('session')" title="本次会话内同类命令自动通过">本次全部允许</button>
        </div>
      </div>
    </div>

    <!-- Skill Approval dialog -->
    <div v-if="pendingSkillApproval" class="approval-overlay">
      <div class="approval-dialog skill-approval-dialog">
        <div class="approval-header">
          <span class="approval-icon">🛠️</span>
          <span class="approval-title">{{ pendingSkillApproval.action === 'create' ? '确认学习新技能' : '确认更新技能' }}</span>
        </div>
        <div class="approval-agent">{{ pendingSkillApproval.agentName }} 想要{{ pendingSkillApproval.action === 'create' ? '学习' : '更新' }}技能：</div>
        <div class="skill-approval-content">
          <div class="skill-approval-field">
            <label>技能名称：</label>
            <span class="skill-approval-name">{{ pendingSkillApproval.action === 'create' ? pendingSkillApproval.details.skill_name : pendingSkillApproval.details.target_skill }}</span>
          </div>
          <div v-if="pendingSkillApproval.details.skill_description" class="skill-approval-field">
            <label>描述：</label>
            <span>{{ pendingSkillApproval.details.skill_description }}</span>
          </div>
          <div class="skill-approval-field">
            <label>内容：</label>
            <pre class="skill-approval-content-view">{{ pendingSkillApproval.details.content || pendingSkillApproval.details.skill_content }}</pre>
          </div>
        </div>
        <div class="approval-actions">
          <button class="approval-btn deny" @click="respondSkillApproval('deny')">取消</button>
          <button class="approval-btn approve" @click="respondSkillApproval('approve')">确认入库</button>
        </div>
      </div>
    </div>

    <!-- Input bar (hidden when info panel showing) -->
    <div
      v-if="!(type === 'group' && showSettings)"
      class="input-bar"
      :class="{ 'drag-over': isDraggingFiles, uploading: isUploadingFiles }"
      @dragenter.prevent="onDragEnter"
      @dragover.prevent="onDragOver"
      @dragleave="onDragLeave"
      @drop.prevent="onDropFiles"
    >
      <div v-if="isDraggingFiles" class="drop-hint">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
        <span>松开即可添加到输入框</span>
      </div>
      <div v-if="showShortcutBar" ref="shortcutCard" class="shortcut-card" :style="shortcutCardStyle" @click.stop>
        <div class="shortcut-card-head" @pointerdown="onShortcutPointerDown" title="按住拖动快捷指令浮窗">
          <span>快捷指令</span>
          <span class="shortcut-drag-hint">拖动调整位置</span>
          <button class="shortcut-close" @click="showShortcutBar = false">×</button>
        </div>
        <div class="shortcut-card-grid">
          <button v-for="cmd in shortcutCommands" :key="cmd.id" class="shortcut-card-item" @click="applyShortcut(cmd)" :title="cmd.label">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><path :d="cmd.icon"/></svg>
            <span>{{ cmd.label }}</span>
          </button>
        </div>
      </div>
      <!-- Mention popup -->
      <div v-if="showMentions && mentionCandidates.length" class="mention-popup" @click.stop>
        <div
          v-for="(c, idx) in mentionCandidates"
          :key="c.id"
          class="mention-item"
          :class="{ active: idx === mentionIndex }"
          @mousedown.prevent="selectMention(c)"
        >
          <div class="avatar" :style="{ background: getAgentColor(agentColorIdx(c.id)) }">
            <span v-html="getAgentIcon(agentColorIdx(c.id))"></span>
          </div>
          <span class="name">{{ c.name }}</span>
          <span class="status-dot" :class="c.status === 'online' ? 'online' : 'offline'"></span>
        </div>
      </div>

      <!-- Plus menu popup -->
      <div v-if="showPlusMenu" class="plus-menu-popup">
        <div class="plus-menu-item" @mousedown.prevent="onPlusUploadFile">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="12" y1="18" x2="12" y2="12"/><line x1="9" y1="15" x2="15" y2="15"/></svg>
          <span>上传文件</span>
        </div>
        <div class="plus-menu-item" @mousedown.prevent="onPlusUploadImage">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" width="18" height="18"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
          <span>添加图片</span>
        </div>
      </div>

      <!-- Attachment preview -->
      <div v-if="attachments.length" class="attach-preview">
        <div v-for="(a, idx) in attachments" :key="idx" class="attach-chip">
          <img v-if="a.type === 'image'" :src="a.url">
          <span v-else class="file-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </span>
          <span class="name">{{ a.name }}</span>
          <button class="remove" @click="attachments.splice(idx, 1)">×</button>
        </div>
      </div>

      <button
        ref="shortcutBtnEl"
        class="shortcut-trigger-btn"
        :class="{ active: showShortcutBar, dragging: isShortcutDragging }"
        :style="shortcutTriggerStyle"
        @pointerdown="onShortcutPointerDown"
        @click.stop="toggleShortcutBar"
        title="快捷指令，可拖动调整位置"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>
        <span>快捷指令</span>
      </button>

      <button class="file-btn plus-btn" :class="{ active: showPlusMenu }" @click="togglePlusMenu" title="上传文件">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>
      </button>
      <input ref="fileInput" type="file" multiple style="display:none" @change="onFiles">
      <input ref="imageInput" type="file" multiple accept="image/*" style="display:none" @change="onFiles">

      <button class="at-btn" @click.stop="triggerAt" title="@提及">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0V12a10 10 0 1 0-3.92 7.94"/></svg>
      </button>

      <textarea
        ref="inputEl"
        rows="1"
        placeholder="输入消息..."
        v-model="inputText"
        @keydown.enter.exact.prevent="onEnterKey($event)"
        @keydown.enter.shift.prevent="onShiftEnter($event)"
        @keydown.down.prevent="moveMention(1)"
        @keydown.up.prevent="moveMention(-1)"
        @keydown.tab.prevent="onTab"
        @keydown.escape="closeMentions"
        @compositionstart="onCompositionStart"
        @compositionend="onCompositionEnd"
        @input="onInput"
        @paste="onPaste"
      ></textarea>

      <button class="send-btn" :disabled="!canSend" @click="send">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
      </button>
    </div>

    <button v-if="showScrollBottom" class="scroll-bottom-btn" @click="scrollToBottom" title="滑到最下面">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M12 5v14"/><path d="M19 12l-7 7-7-7"/></svg>
    </button>


    <!-- (Modal-mode RoomMembersModal removed — replaced by RoomInfoPanel inline) -->
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'
import { store, api, ws, auth, escapeHtml, getAgentColor, getAgentIcon, loadConversations, clearUnread, currentRoomId, chatSettings, saveChatSettings, markStreamInterrupted, openArtifact } from '../store.js'
import RoomInfoPanel from './RoomInfoPanel.vue'
import { uploadFile } from '../upload.js'

const props = defineProps({ room: Object, type: String, displayName: String, initialPrompt: String })
const emit = defineEmits(['close', 'prompt-consumed', 'open-chat'])

const messagesArea = ref(null)
const roomInfoPanel = ref(null)
const inputEl = ref(null)
const fileInput = ref(null)
const imageInput = ref(null)
const renameInput = ref(null)
const shortcutCard = ref(null)
const shortcutBtnEl = ref(null)
const shortcutViewportTick = ref(0)
const inputText = ref('')
const messages = ref([])
const messagesLoading = ref(false)
const olderMessagesLoading = ref(false)
const hasOlderMessages = ref(true)
const MESSAGE_PAGE_SIZE = 30
const typingAgent = ref(null)
const showSettings = ref(false)
const pendingApproval = ref(null)
const pendingSkillApproval = ref(null)
const projectCreationState = reactive({})
const attachments = ref([])
const isDraggingFiles = ref(false)
const isUploadingFiles = ref(false)
let dragDepth = 0
const threads = ref([])
const creatingThread = ref(false)
const activeThreadId = ref(null)
const threadDrawerOpen = ref(false)
const threadFilter = ref('')
const showPlusMenu = ref(false)
const showShortcutBar = ref(false)
const shortcutPosition = ref({ x: null, y: null })
const isShortcutDragging = ref(false)
let shortcutDragState = null
let shortcutSuppressClick = false
const showScrollBottom = ref(false)

// Draggable floating shortcut button
const hasActiveStreamInView = computed(() => Object.values(store.activeStreams).some(s => s.roomId === props.room.id && (s.threadId || null) === activeThreadId.value && !s.interrupted))

// Shortcut commands (like TG Hermes slash commands)
const shortcutCommands = [
  { id: 'compress', label: '压缩上下文', icon: 'M4 14h4v4H4zM14 10h4v4h-4zM1 10h4v4H1zM8 6h4v4H8z', command: '/compact' },
  { id: 'stop', label: '立即停止', icon: 'M6 4h4v16H6zM14 4h4v16h-4z', command: '/stop', needsAgent: true },
  { id: 'clear', label: '清空对话', icon: 'M3 6h18M8 6V4h8v2M5 6v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6', command: '/clear' },
  { id: 'retry', label: '重新生成', icon: 'M1 4v6h6M23 20v-6h-6M20.49 9A9 9 0 0 0 5.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 0 1 3.51 15', command: '/retry' },
  { id: 'summary', label: '总结对话', icon: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M16 13H8M16 17H8M10 9H8', command: '/summary' },
]

// Thread rename state
const renamingThreadId = ref(null)
const renameThreadTitle = ref('')

// Mention autocomplete
const showMentions = ref(false)
const mentionQuery = ref('')
const mentionIndex = ref(0)
const mentionStartPos = ref(-1)

let resizeRaf = 0
const isComposingText = ref(false)

// Tool expand state per stream
const toolsExpandedMap = ref({})
const thinkingExpandedMap = ref({})
let clientOrderSeq = 0

function nextClientOrder() {
  clientOrderSeq += 1
  return clientOrderSeq
}

// Markdown render cache to avoid re-parsing on every computed tick
const _mdCache = new Map()
function cachedRenderMd(text, id) {
  if (!text) return ''
  const key = `${id}:${text.length}:${text.slice(0, 64)}`
  if (_mdCache.has(key)) return _mdCache.get(key)
  const html = renderMd(text)
  // Cap cache size
  if (_mdCache.size > 300) {
    const first = _mdCache.keys().next().value
    _mdCache.delete(first)
  }
  _mdCache.set(key, html)
  return html
}

const TOOL_LABELS = {
  run_command: '执行命令',
  read_file: '读取文件',
  write_file: '写入文件',
  http_request: 'HTTP 请求',
  search_files: '搜索文件',
  install_package: '安装依赖',
}
function cleanText(value) {
  if (value === undefined || value === null) return ''
  const text = String(value).trim()
  if (!text || text === 'undefined' || text === 'null') return ''
  return text.replace(/\bundefined\b/g, '').replace(/\bnull\b/g, '').trim()
}
function parseProjectProposal(text) {
  const match = String(text || '').match(/```myna-project-proposal\s*([\s\S]*?)```/i)
  if (!match) return null
  try {
    const proposal = JSON.parse(match[1].trim())
    if (!proposal.project_name || !proposal.summary || !Array.isArray(proposal.roles) || !proposal.roles.length) return null
    if (proposal.roles.some(role => !role?.name || !role?.responsibility)) return null
    return proposal
  } catch { return null }
}
function stripProjectProposal(text) {
  return String(text || '')
    .replace(/<!--myna-assistant:(?:fast|expert):(?:0(?:\.\d+)?|1(?:\.0+)?)-->\s*/ig, '')
    .replace(/```myna-project-proposal\s*[\s\S]*?```/ig, '')
    .trim()
}

async function confirmProjectProposal(msg) {
  if (!msg.projectProposal || projectCreationState[msg.id]?.loading) return
  projectCreationState[msg.id] = { loading: true, created: false }
  try {
    const result = await api('POST', '/admin/collaboration/projects', {
      ...msg.projectProposal,
      source_room_id: props.room.id,
      source_message_id: msg.id,
    })
    if (!result?.ok) throw new Error(result?.error || '创建失败')
    projectCreationState[msg.id] = { loading: false, created: true }
    const __created = result.result?.createdCount || 0
    showToast(__created ? ('已创建 ' + __created + ' 个协作智能体，已开始协同工作') : '协作智能体已就绪')
    await loadConversations({ force: true })
    if (result.result?.room) emit('open-chat', result.result.room, 'group')
  } catch (error) {
    projectCreationState[msg.id] = { loading: false, created: false }
    showToast(error?.message || '项目创建失败')
  }
}
function artifactBaseName(p) {
  return String(p || '').split('/').pop()
}
function onContentClick(e) {
  const dlIcon = e.target.closest?.('.file-card-dl')
  if (dlIcon) {
    const a = dlIcon.closest('a')
    const href = a?.getAttribute('href') || ''
    if (href) {
      e.preventDefault()
      e.stopPropagation()
      const tmp = document.createElement('a')
      tmp.href = href + (href.includes('?') ? '&' : '?') + 'download=1'
      tmp.download = ''
      document.body.appendChild(tmp)
      tmp.click()
      tmp.remove()
    }
    return
  }
  const card = e.target.closest?.('.file-card')
  const img = e.target.closest?.('.msg-text img')
  if (!card && !img) return
  let url = ''
  let name = ''
  if (card) {
    const a = card.closest('a') || card
    url = a.getAttribute('href') || ''
    name = card.querySelector('.file-card-name')?.textContent?.trim() || ''
  } else {
    url = img.getAttribute('src') || ''
    name = img.getAttribute('alt') || ''
  }
  if (!url || url.startsWith('#') || url.startsWith('javascript')) return
  e.preventDefault()
  e.stopPropagation()
  let abs = url
  let path = ''
  try {
    abs = new URL(url, window.location.origin).href
    const pathname = decodeURIComponent(new URL(abs).pathname)
    for (const pre of ['/media/workspaces/', '/admin/media/', '/uploads/']) {
      if (pathname.startsWith(pre)) { path = pathname.slice(pre.length); break }
    }
  } catch {}
  if (!name || name === 'image' || name === '图片') name = artifactBaseName(path) || '文件'
  openArtifact({ name, url: abs, path })
}

function isSkillStatusMessage(msg) {
  if (!msg || msg.senderId !== 'system') return false
  const text = String(msg.text || '')
  return text.includes('已学习新技能')
    || text.includes('已更新技能')
    || text.includes('技能创建已取消')
    || text.includes('技能更新已取消')
}

function toolLabel(name) { return TOOL_LABELS[name] || cleanText(name) || '工具' }

function compactModelBadge(value) {
  let text = cleanText(value)
  if (!text) return ''
  const parts = text.split('/').map(x => x.trim()).filter(Boolean)
  let provider = ''
  let model = text
  if (parts.length >= 2) {
    provider = parts[0]
    model = parts.slice(1).join('/')
  }
  const providerLow = provider.toLowerCase()
  if (providerLow.includes('qwe') || providerLow.includes('qwen') || providerLow === 'qw') provider = 'qwe'
  else if (providerLow.includes('openai')) provider = 'openai'
  else if (providerLow.includes('claude') || providerLow.includes('anthropic')) provider = 'claude'
  else if (providerLow.includes('gemini') || providerLow.includes('google')) provider = 'gemini'
  else if (providerLow.includes('deepseek')) provider = 'deepseek'
  else provider = provider ? provider.split(/[\s-]+/)[0].toLowerCase() : ''
  model = model.toLowerCase()
    .replace(/^qwe\//, '')
    .replace(/^qwen\//, '')
    .replace(/^openai\//, '')
    .replace(/^claude\//, '')
    .replace(/^gemini\//, '')
    .replace(/^deepseek\//, '')
    .replace(/gpt[-_]/g, 'gpt')
    .replace(/qwen[-_]/g, 'qwen')
    .replace(/claude[-_]/g, 'claude')
  return provider && model && provider !== model ? `${provider}/${model}` : (model || provider)
}
function toolExpandKey(msg, partIndex = null) {
  const sid = String(msg.id).startsWith('stream-') ? msg.id.replace('stream-', '') : `saved-${msg.id}`
  return partIndex === null ? sid : `${sid}-part-${partIndex}`
}

function toggleToolsExpand(msg) {
  const key = toolExpandKey(msg)
  toolsExpandedMap.value[key] = !msg.toolsExpanded
}

function togglePartToolExpand(msg, partIndex) {
  const key = toolExpandKey(msg, partIndex)
  toolsExpandedMap.value[key] = !getPartToolExpanded(msg, partIndex)
}

function getPartToolExpanded(msg, partIndex) {
  const key = toolExpandKey(msg, partIndex)
  if (toolsExpandedMap.value[key] !== undefined) return toolsExpandedMap.value[key]
  return false
}

function getToolsExpanded(sid, isStreaming) {
  // If user has manually toggled, respect that
  if (toolsExpandedMap.value[sid] !== undefined) return toolsExpandedMap.value[sid]
  // Default: always collapsed (user can click to expand)
  return false
}

function toggleThinkingExpand(msg) {
  const sid = String(msg.id).startsWith('stream-') ? msg.id.replace('stream-', '') : `saved-${msg.id}`
  thinkingExpandedMap.value[sid] = !msg.thinkingExpanded
}

function getThinkingExpanded(sid) {
  if (thinkingExpandedMap.value[sid] !== undefined) return thinkingExpandedMap.value[sid]
  return false
}

function thinkingStageLabel(stage) {
  const labels = { thinking: '分析', tool_call: '调用', tool_result: '完成', final: '整理' }
  return labels[stage] || '过程'
}

function processEventText(ev) {
  if (!ev) return ''
  return cleanText(ev.content) || cleanText(ev.detail) || cleanText(ev.tool) || ''
}

function getThinkingEvents(msg) {
  const events = Array.isArray(msg?.thinkingEvents) ? msg.thinkingEvents : []
  return events
    .map(ev => ({
      ...ev,
      content: cleanText(ev?.content),
      detail: cleanText(ev?.detail),
      tool: cleanText(ev?.tool),
      stage: cleanText(ev?.stage),
    }))
    .filter(ev => processEventText(ev))
}

function toolStatusLabel(status) {
  if (status === 'running') return '运行中'
  if (status === 'error') return '失败'
  return '完成'
}

function getThinkingSummary(msg) {
  const tools = getProcessTools(msg)
  const events = getThinkingEvents(msg)
  const parts = []
  if (tools.length) {
    const names = tools.map(t => toolLabel(cleanText(t.name || t.tool) || '工具'))
    const unique = [...new Set(names)]
    if (unique.length <= 3) parts.push(unique.join('、'))
    else parts.push(unique.slice(0, 2).join('、') + ' 等 ' + unique.length + ' 项')
  }
  if (events.length && !tools.length) {
    const last = events[events.length - 1]
    const text = processEventText(last)
    if (text) parts.push(text.length > 30 ? text.slice(0, 30) + '…' : text)
  }
  if (!parts.length) return ''
  return parts.join(' → ')
}

function getProcessTools(msg) {
  const directTools = Array.isArray(msg?.toolCalls) ? msg.toolCalls : []
  const partTools = Array.isArray(msg?.parts) ? msg.parts.filter(p => p?.type === 'tool') : []
  const merged = []
  for (const tool of [...directTools, ...partTools]) {
    if (!tool) continue
    const key = [tool.name || tool.tool || '', tool.summary || tool.args_summary || '', tool.result || '', tool.status || ''].join('|')
    if (merged.some(existing => [existing.name || existing.tool || '', existing.summary || existing.args_summary || '', existing.result || '', existing.status || ''].join('|') === key)) continue
    merged.push(tool)
  }
  return merged
}

function onSettingsChange(val) {
  chatSettings.toolCallDisplay = val
  saveChatSettings()
}

// === Task 1: Click AI bubble to @mention ===
function onMentionClick(msg) {
  if (!msg.sender_name) return
  const mention = '@' + msg.sender_name + ' '
  inputText.value = mention + inputText.value
  nextTick(() => {
    const el = inputEl.value
    if (el) {
      el.focus()
      el.selectionStart = el.selectionEnd = mention.length + inputText.value.length - mention.length
    }
  })
}


// === Task 2: Plus menu ===
function togglePlusMenu() {
  showPlusMenu.value = !showPlusMenu.value
  if (showPlusMenu.value) {
    showShortcutBar.value = false
    // Close on outside click
    setTimeout(() => {
      document.addEventListener('click', closePlusMenu, { once: true })
    }, 0)
  }
}
function closePlusMenu() {
  showPlusMenu.value = false
}
function toggleShortcutBar() {
  if (shortcutSuppressClick) {
    shortcutSuppressClick = false
    return
  }
  showShortcutBar.value = !showShortcutBar.value
  if (showShortcutBar.value) {
    showPlusMenu.value = false
    clampShortcutPosition()
    nextTick(() => { shortcutViewportTick.value++; clampShortcutPosition() })
    setTimeout(() => {
      document.addEventListener('click', closeShortcutBar, { once: true })
    }, 0)
  }
}
function closeShortcutBar(e) {
  if (e?.target?.closest?.('.shortcut-card, .shortcut-trigger-btn')) return
  showShortcutBar.value = false
}

function closeMessageContextMenu() {
  // The message context menu was removed, but unmount cleanup still calls this
  // hook in older builds. Keep a safe no-op to avoid breaking chat mount/unmount.
}

const SHORTCUT_MARGIN = 10
const shortcutTriggerSize = computed(() => {
  shortcutViewportTick.value
  const rect = shortcutBtnEl.value?.getBoundingClientRect?.()
  return {
    width: rect?.width || (window.innerWidth < 768 ? 92 : 104),
    height: rect?.height || (window.innerWidth < 768 ? 30 : 32),
  }
})
const shortcutTriggerStyle = computed(() => {
  const p = getShortcutPosition()
  return { left: `${p.x}px`, top: `${p.y}px`, right: 'auto', bottom: 'auto' }
})
const shortcutCardMetrics = computed(() => {
  shortcutViewportTick.value
  const vw = window.innerWidth || document.documentElement.clientWidth || 360
  const vh = window.innerHeight || document.documentElement.clientHeight || 640
  const mobile = vw < 768
  const width = Math.min(mobile ? 360 : 440, vw - SHORTCUT_MARGIN * 2)
  const measured = shortcutCard.value?.getBoundingClientRect?.()
  const fallbackHeight = mobile ? 190 : 150
  const height = Math.min(measured?.height || fallbackHeight, vh - SHORTCUT_MARGIN * 2)
  return { vw, vh, width, height }
})
const shortcutCardStyle = computed(() => {
  const p = getShortcutPosition()
  const trigger = shortcutTriggerSize.value
  const { vw, vh, width, height } = shortcutCardMetrics.value
  const gap = 10
  let left = p.x + trigger.width - width
  left = Math.max(SHORTCUT_MARGIN, Math.min(left, vw - width - SHORTCUT_MARGIN))

  const spaceAbove = p.y - SHORTCUT_MARGIN
  const spaceBelow = vh - (p.y + trigger.height) - SHORTCUT_MARGIN
  let top
  if (spaceAbove >= height + gap || spaceAbove >= spaceBelow) top = p.y - height - gap
  else top = p.y + trigger.height + gap
  top = Math.max(SHORTCUT_MARGIN, Math.min(top, vh - height - SHORTCUT_MARGIN))

  return {
    left: `${left}px`,
    top: `${top}px`,
    right: 'auto',
    bottom: 'auto',
    width: `${width}px`,
    maxHeight: `${vh - SHORTCUT_MARGIN * 2}px`,
  }
})

function getShortcutPosition() {
  if (shortcutPosition.value.x == null || shortcutPosition.value.y == null) {
    const vw = window.innerWidth || document.documentElement.clientWidth || 360
    const vh = window.innerHeight || document.documentElement.clientHeight || 640
    const trigger = shortcutTriggerSize.value
    shortcutPosition.value = {
      x: Math.max(SHORTCUT_MARGIN, vw - trigger.width - 60),
      y: Math.max(SHORTCUT_MARGIN, vh - trigger.height - 100),
    }
  }
  return shortcutPosition.value
}

function clampShortcutPosition() {
  const vw = window.innerWidth || document.documentElement.clientWidth || 360
  const vh = window.innerHeight || document.documentElement.clientHeight || 640
  const trigger = shortcutTriggerSize.value
  const p = getShortcutPosition()
  shortcutPosition.value = {
    x: Math.max(SHORTCUT_MARGIN, Math.min(p.x, vw - trigger.width - SHORTCUT_MARGIN)),
    y: Math.max(SHORTCUT_MARGIN, Math.min(p.y, vh - trigger.height - SHORTCUT_MARGIN)),
  }
  try { localStorage.setItem('shortcut_floating_pos', JSON.stringify(shortcutPosition.value)) } catch {}
}

function onShortcutPointerDown(e) {
  if (e.button !== undefined && e.button !== 0) return
  if (e.target?.closest?.('.shortcut-close, .shortcut-card-item')) return
  e.stopPropagation()
  if (e.cancelable) e.preventDefault()
  const p = getShortcutPosition()
  shortcutDragState = { startX: e.clientX, startY: e.clientY, originX: p.x, originY: p.y, moved: false }
  isShortcutDragging.value = true
  e.currentTarget?.setPointerCapture?.(e.pointerId)
  document.addEventListener('pointermove', onShortcutPointerMove, { passive: false })
  document.addEventListener('pointerup', onShortcutPointerUp, { once: true })
  document.addEventListener('pointercancel', onShortcutPointerUp, { once: true })
}

function onShortcutPointerMove(e) {
  if (!shortcutDragState) return
  if (e.cancelable) e.preventDefault()
  const dx = e.clientX - shortcutDragState.startX
  const dy = e.clientY - shortcutDragState.startY
  if (Math.abs(dx) + Math.abs(dy) > 3) shortcutDragState.moved = true
  if (!shortcutDragState.moved) return
  shortcutPosition.value = { x: shortcutDragState.originX + dx, y: shortcutDragState.originY + dy }
  clampShortcutPosition()
}

function onShortcutPointerUp() {
  document.removeEventListener('pointermove', onShortcutPointerMove)
  document.removeEventListener('pointercancel', onShortcutPointerUp)
  if (shortcutDragState?.moved) shortcutSuppressClick = true
  shortcutDragState = null
  isShortcutDragging.value = false
  clampShortcutPosition()
}
function onPlusUploadFile() {
  showPlusMenu.value = false
  fileInput.value?.click()
}
function onPlusUploadImage() {
  showPlusMenu.value = false
  imageInput.value?.click()
}
function applyShortcut(cmd) {
  showShortcutBar.value = false

  // Direct-execute commands that don't need agent interaction
  if (cmd.command === '/clear') {
    if (confirm('是否清除对话？')) {
      handleCommand('/clear')
    }
    return
  }
  if (cmd.command === '/stop') {
    // User stop means stop showing the live bubble immediately. Backend may save
    // a compact audit marker, but the long partial stream should disappear now.
    let count = 0
    for (const [streamId, stream] of Object.entries(store.activeStreams)) {
      if (stream.roomId === props.room.id && (stream.threadId || null) === activeThreadId.value) {
        if (ws._ws && ws._ws.readyState === WebSocket.OPEN) {
          ws._ws.send(JSON.stringify({ type: 'cancel_stream', stream_id: streamId }))
        }
        markStreamInterrupted(streamId)
        count++
      }
    }
    showToast(count ? '已停止生成' : '当前没有正在生成的回复')
    return
  }

  // Commands that need to be sent to the agent (compact, retry, summary)
  if (cmd.command === '/compact' || cmd.command === '/retry' || cmd.command === '/summary') {
    const toastMsg = cmd.command === '/compact' ? '正在压缩上下文...' : cmd.command === '/retry' ? '正在重新生成...' : '正在总结对话...'
    showToast(toastMsg)

    // /retry: don't show user message (backend handles deletion + re-trigger)
    if (cmd.command === '/retry') {
      const endpoint = activeThreadId.value ? `/admin/threads/${activeThreadId.value}/send` : `/admin/rooms/${props.room.id}/send`
      // Determine target agent
      const lastAgentMsg = [...messages.value].reverse().find(m => m.sender_id && m.sender_id !== 'user' && m.sender_id !== 'system')
      const mentions = lastAgentMsg ? [lastAgentMsg.sender_id] : []
      api('POST', endpoint, { text: '/retry', mentions })
      return
    }

    // Determine target agent (last agent that replied)
    const lastAgentMsg = [...messages.value].reverse().find(m => m.sender_id && m.sender_id !== 'user' && m.sender_id !== 'system')
    const mentions = []
    if (lastAgentMsg) mentions.push(lastAgentMsg.sender_id)
    else if (props.room.members?.length) {
      const first = props.room.members.find(m => m.id !== 'user' && m.id !== 'system')
      if (first) mentions.push(first.id)
    }

    const endpoint = activeThreadId.value ? `/admin/threads/${activeThreadId.value}/send` : `/admin/rooms/${props.room.id}/send`
    api('POST', endpoint, { text: cmd.command, mentions })
    return
  }

  // Fallback: insert command and trigger @ mention picker
  inputText.value = cmd.command + ' @'
  nextTick(() => {
    inputEl.value?.focus()
    triggerAt()
  })
}

// === Task 4: Cancel stream ===
function cancelStream(msg) {
  const streamId = String(msg.id).replace('stream-', '')
  // Emit WS event
  if (ws._ws && ws._ws.readyState === WebSocket.OPEN) {
    ws._ws.send(JSON.stringify({ type: 'cancel_stream', stream_id: streamId }))
  }
  markStreamInterrupted(streamId)
}

const title = computed(() => {
  if (props.type === 'dm') return props.displayName || props.room.agent?.name || '私聊'
  return props.room.name || '群聊'
})
const subtitle = computed(() => {
  if (props.type === 'group') return (props.room.members?.length || 0) + ' 个成员'
  return ''
})

const canSend = computed(() => inputText.value.trim().length > 0 || attachments.value.length > 0)

const agentColorIdx = (id) => store.agents.findIndex(a => a.id === id)

// Mention candidates: room members (group) or all agents (dm)
const mentionCandidates = computed(() => {
  let pool = []
  const isGroup = props.type === 'group' && props.room.members
  if (isGroup) {
    pool = props.room.members.filter(m => m.id !== 'user')
  } else {
    pool = store.agents
  }
  // @全部 only makes sense in group chats with multiple members
  const showAll = isGroup && pool.filter(m => m.id !== 'system').length > 1
  const allOption = { id: '__all__', name: '全部', description: '通知所有智能体' }
  const q = mentionQuery.value.toLowerCase()
  if (!q) return [...(showAll ? [allOption] : []), ...pool]
  if (showAll && ('全部'.includes(q) || 'all'.includes(q))) {
    return [allOption, ...pool.filter(m => (m.name || '').toLowerCase().includes(q))]
  }
  return pool.filter(m => (m.name || '').toLowerCase().includes(q))
})

watch(mentionCandidates, (list) => {
  if (mentionIndex.value >= list.length) mentionIndex.value = Math.max(0, list.length - 1)
})

// Time formatting — convert UTC/ISO to local timezone
function formatMsgTime(ts) {
  if (!ts) return ''
  try {
    // Backend stores UTC without Z suffix, format: "2026-05-28 07:04:42"
    const normalized = ts.replace(' ', 'T') + (ts.includes('Z') || ts.includes('+') ? '' : 'Z')
    const d = new Date(normalized)
    if (isNaN(d.getTime())) return ts.slice(11, 16)
    return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })
  } catch { return ts.slice(11, 16) }
}
function formatMsgDate(ts) {
  if (!ts) return ''
  try {
    const normalized = ts.replace(' ', 'T') + (ts.includes('Z') || ts.includes('+') ? '' : 'Z')
    const d = new Date(normalized)
    if (isNaN(d.getTime())) return ts.slice(0, 10)
    const y = d.getFullYear()
    const m = String(d.getMonth() + 1).padStart(2, '0')
    const day = String(d.getDate()).padStart(2, '0')
    return `${y}-${m}-${day}`
  } catch { return ts.slice(0, 10) }
}

function parseMessageTs(ts) {
  if (!ts) return 0
  if (typeof ts === 'number') return ts
  try {
    const value = String(ts)
    const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value)
    const normalized = value.replace(' ', 'T') + (hasZone ? '' : 'Z')
    const d = new Date(normalized)
    return isNaN(d.getTime()) ? 0 : d.getTime()
  } catch { return 0 }
}

function numericMessageId(id) {
  const n = Number(id)
  return Number.isFinite(n) && String(id).match(/^\d+$/) ? n : 0
}

function compareChatItems(a, b) {
  const ta = a.sortTs || 0
  const tb = b.sortTs || 0
  if (ta !== tb) return ta - tb

  const ia = numericMessageId(a.id)
  const ib = numericMessageId(b.id)
  if (ia && ib && ia !== ib) return ia - ib

  const oa = a.clientOrder || 0
  const ob = b.clientOrder || 0
  if (oa !== ob) return oa - ob
  return String(a.id).localeCompare(String(b.id))
}

function sortChatMessages(list) {
  return [...list].sort((a, b) => compareChatItems(
    { ...a, sortTs: a.clientSortTs || parseMessageTs(a.created_at), clientOrder: a.clientOrder || 0 },
    { ...b, sortTs: b.clientSortTs || parseMessageTs(b.created_at), clientOrder: b.clientOrder || 0 }
  ))
}


function normalizeDisplayMathBlocks(text) {
  if (!text) return text
  return text.replace(/(^|\n)\s*\[\s*\n([\s\S]*?)\n\s*\]\s*(?=\n|$)/g, (match, prefix, body) => {
    const lines = body.split('\n').map(line => line.trim()).filter(Boolean)
    if (!lines.length || lines.length > 4) return match
    const content = lines.join(' ')
    const looksLikeFormula = /[=÷×+\-*/%≈]|\d/.test(content) && !/^https?:\/\//i.test(content)
    if (!looksLikeFormula) return match
    return `${prefix}<div class="formula-block">${escapeHtml(content)}</div>\n`
  })
}

function extractSources(text) {
  const found = []
  const seen = new Set()
  const matches = String(text || '').match(/https?:\/\/[^\s<>()\[\]"']+/gi) || []
  for (const match of matches) {
    const candidate = match.replace(/[，。！？；：,.!?;:]+$/g, '')
    try {
      const url = new URL(candidate)
      if (!['http:', 'https:'].includes(url.protocol) || seen.has(url.href)) continue
      seen.add(url.href)
      found.push({ index: found.length + 1, url: url.href, host: url.hostname.replace(/^www\./, '') })
    } catch {}
    if (found.length >= 12) break
  }
  return found
}

function mergeSources(text, verifiedSources = []) {
  return extractSources([...verifiedSources, text].filter(Boolean).join('\n'))
}

function renderMd(text) {
  if (!text) return ''
  try {
    marked.setOptions({ breaks: true, gfm: true })

    const encodeMediaPath = (path) => {
      // Preserve a leading slash for absolute paths, but do not drop the first
      // segment for relative workspace paths like "room-id/file.xlsx".
      const leadingSlash = path.startsWith('/')
      const encoded = path
        .split('/')
        .filter((part, idx) => part || idx === 0)
        .map((part, idx) => (idx === 0 && leadingSlash) ? '' : encodeURIComponent(part))
        .join('/')
      return encoded
    }
    const mediaUrlForPath = (path, download = false) => {
      const encodedPath = encodeMediaPath(path)
      const workspacePrefix = '/app/data/workspaces/'
      if (path.startsWith(workspacePrefix)) {
        const workspaceRelPath = path.slice(workspacePrefix.length)
        const url = `/media/workspaces/${encodeMediaPath(workspaceRelPath).replace(/^\//, '')}`
        return download ? `${url}?download=1` : url
      }
      const url = `/admin/media${encodedPath}`
      return download ? `${url}?download=1` : url
    }

    // Convert MEDIA:/path/to/file to displayable content
    // Supports: MEDIA:/path, MEDIA:`/path`, **MEDIA:** `/path`
    let processed = normalizeDisplayMathBlocks(String(text).replace(/<!--myna-assistant:(?:fast|expert):[\d.]+-->\s*/gi, ''))

    processed = processed.replace(/\[([^\]]+)\]\((\/app\/data\/[^)\s]+)\)/g, (m, lt, p) => 'MEDIA:' + p)
    processed = processed.replace(/(?<![(\[`">=:，、])(\/app\/data\/(?:workspaces|uploads)\/[^\s`()）\]，。；、]+?\.(?:png|jpe?g|gif|webp|svg|mp4|webm|pdf|html?|zip|tar|gz|7z|rar|docx?|xlsx?|pptx?|txt|md|json|csv|sql))/gi, (m, p) => 'MEDIA:' + p)
    processed = processed.replace(/(?<![(\[`">=:，、])(\/app\/backend\/[^\s`()）\]，。；、]+?\.(?:zip|tar|gz|7z|rar|docx?|xlsx?|pptx?|pdf|csv|md|txt|json|png|jpe?g))/gi, (m, p) => 'MEDIA:' + p)
    processed = processed.replace(/(?:\*{0,2}MEDIA:?\*{0,2})\s*`?(\/[^\n`]*?\.(?:png|jpe?g|gif|webp|svg|mp4|webm|pdf|html?|zip|tar|gz|7z|rar|docx?|xlsx?|pptx?|txt|md|json|csv|sql))`?/gi, (match, filePath) => {
      const cleanPath = filePath.trim()
      const ext = cleanPath.split('.').pop().toLowerCase()
      const mediaUrl = mediaUrlForPath(cleanPath)
      const fileName = cleanPath.split('/').pop()
      const safeFileName = escapeHtml(fileName)
      if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'].includes(ext)) {
        return `![image](${mediaUrl})`
      } else if (['mp4', 'webm'].includes(ext)) {
        return `<video src="${mediaUrl}" controls style="max-width:100%;border-radius:8px"></video>`
      } else if (ext === 'pdf') {
        return `<a href="${mediaUrl}" class="file-card"><span class="file-card-icon">📄</span><span class="file-card-info"><span class="file-card-name">${safeFileName}</span><span class="file-card-meta">PDF 文档 · 点击预览</span></span><span class="file-card-dl">⬇</span></a>`
      } else if (ext === 'html' || ext === 'htm') {
        return `<a href="${mediaUrl}" class="file-card"><span class="file-card-icon">🌐</span><span class="file-card-info"><span class="file-card-name">${safeFileName}</span><span class="file-card-meta">HTML 文件 · 点击预览</span></span><span class="file-card-dl">⬇</span></a>`
      } else {
        const downloadUrl = mediaUrlForPath(cleanPath, true)
        const icons = { zip: '🗜️', tar: '🗜️', gz: '🗜️', '7z': '🗜️', rar: '🗜️', doc: '📝', docx: '📝', xls: '📊', xlsx: '📊', ppt: '📽️', pptx: '📽️', txt: '📃', md: '📃', json: '📋', csv: '📊', sql: '🗃️', html: '🌐', htm: '🌐' }
        const icon = icons[ext] || '📎'
        const previewable = ['docx', 'xlsx', 'xlsm', 'pptx', 'txt', 'md', 'markdown', 'pdf'].includes(ext)
        const label = previewable ? `点击预览` : `${ext.toUpperCase()} 文件 · 点击下载`
        return `<a href="${previewable ? mediaUrl : downloadUrl}"${previewable ? '' : ` download="${safeFileName}"`} class="file-card"><span class="file-card-icon">${icon}</span><span class="file-card-info"><span class="file-card-name">${safeFileName}</span><span class="file-card-meta">${label}</span></span><span class="file-card-dl">⬇</span></a>`
      }
    })

    // Temporarily protect code blocks
    const codeBlocks = []
    processed = processed.replace(/```[\s\S]*?```/g, (match) => {
      codeBlocks.push(match)
      return `__CODE_BLOCK_${codeBlocks.length - 1}__`
    })
    // Highlight @mentions (outside code blocks)
    processed = processed.replace(/@(\S+?)(?=[.,;:!?\s，。；：！？]|$)/g, '<span class="at-mention">@$1</span>')
    // Escape HTML tags outside code blocks (prevent layout breakage)
    processed = processed.replace(/<(script|style|link|meta|iframe|object|embed|form)[^>]*>[\s\S]*?<\/\1>/gi, (match) => {
      return '```html\n' + match + '\n```'
    })
    processed = processed.replace(/<(script|style|link|meta|iframe|object|embed|form)[^>]*\/?>/gi, (match) => {
      return '`' + match + '`'
    })
    // Restore code blocks
    processed = processed.replace(/__CODE_BLOCK_(\d+)__/g, (_, i) => codeBlocks[i])

    // Extract KaTeX math before marked (protect from markdown parsing)
    const __mathBlocks = []
    processed = processed.replace(/\$\$([\s\S]+?)\$\$/g, (m, math) => {
      __mathBlocks.push({ math: math.trim(), display: true })
      return ' __MATH_' + (__mathBlocks.length - 1) + '_ '
    })
    processed = processed.replace(/\$(?!\s)([^\n$]+?)(?<![\s\\])\$/g, (m, math) => {
      if (math.trim().length === 0) return m
      __mathBlocks.push({ math: math.trim(), display: false })
      return ' __MATH_' + (__mathBlocks.length - 1) + '_ '
    })

    let html = marked.parse(processed)
    html = html.replace(/<table>/g, '<div class="table-wrapper"><table>').replace(/<\/table>/g, '</table></div>')
    html = html.replace(/<img /g, '<img loading="lazy" decoding="async" style="max-width:100%;max-height:300px;border-radius:8px;cursor:zoom-in;display:block;margin:4px 0" ')
    // Sanitize with DOMPurify to prevent XSS while keeping rich content
    html = DOMPurify.sanitize(html, {
      ALLOWED_TAGS: ['a','b','i','em','strong','code','pre','p','br','ul','ol','li','h1','h2','h3','h4','h5','h6','table','thead','tbody','tr','th','td','div','span','img','video','source','blockquote','details','summary','del','ins','sup','sub','hr','ruby','rt','rp'],
      ALLOWED_ATTR: ['href','target','rel','style','class','id','src','alt','title','controls','download','onclick','colspan','rowspan','width','height','align','valign','loading','decoding'],
      ALLOW_DATA_ATTR: false,
      FORBID_TAGS: ['script','style','iframe','object','embed','form','input','textarea','select','button','link','meta','noscript'],
      FORBID_ATTR: ['onerror','onload','onmouseover','onfocus','onblur','onsubmit','onchange','formaction'],
    })
    const doc = new DOMParser().parseFromString(html, 'text/html')
    doc.querySelectorAll('a[href]').forEach(a => {
      a.setAttribute('target', '_blank')
      a.setAttribute('rel', 'noopener noreferrer')
    })
    let result = doc.body.innerHTML
    if (typeof window.katex !== 'undefined' && __mathBlocks && __mathBlocks.length) {
      for (let i = 0; i < __mathBlocks.length; i++) {
        const block = __mathBlocks[i]
        const placeholder = '__MATH_' + i + '_'
        try {
          const rendered = window.katex.renderToString(block.math, { displayMode: block.display, throwOnError: false, trust: true })
          result = result.split(placeholder).join(rendered)
        } catch (e) {
          const fallback = block.display ? '<div class="math-fallback">$$' + block.math + '$$</div>' : '<span class="math-fallback">$' + block.math + '$</span>'
          result = result.split(placeholder).join(fallback)
        }
      }
    }
    return result
  } catch { return escapeHtml(text) }
}

function fmtMs(v) {
  if (v == null) return '—'
  if (v >= 60000) return Math.floor(v / 60000) + 'm' + Math.round((v % 60000) / 1000) + 's'
  if (v >= 1000) return (v / 1000).toFixed(1) + 's'
  return v + 'ms'
}
function fmtK(v) {
  if (v >= 1000000) return (v / 1000000).toFixed(1) + 'M'
  if (v >= 1000) return (v / 1000).toFixed(1) + 'K'
  return v
}
const totalLlmMs = computed(() => {
  let t = 0
  for (const m of messages.value) {
    try {
      const md = typeof m.metadata === 'string' ? JSON.parse(m.metadata || '{}') : (m.metadata || {})
      t += Number(md?.stats?.total_ms) || 0
    } catch {}
  }
  return t
})
const sessionStats = computed(() => {
  let ttftSum = 0, ttftN = 0, inTok = 0, outTok = 0, cacheInput = 0, cacheHit = 0, cacheN = 0, hasUsage = false, hasTime = false
  for (const message of messages.value) {
    let stats
    try { const meta = typeof message.metadata === 'string' ? JSON.parse(message.metadata) : message.metadata; stats = meta?.stats } catch {}
    if (!stats) continue
    if (Number.isFinite(stats.total_ms)) hasTime = true
    if (Number.isFinite(stats.first_token_ms)) { ttftSum += stats.first_token_ms; ttftN++ }
    const measured = stats.usage_recorded === true || Number(stats.input_tokens) > 0 || Number(stats.output_tokens) > 0
    if (measured) { hasUsage = true; inTok += Number(stats.input_tokens) || 0; outTok += Number(stats.output_tokens) || 0 }
    if (measured && Number.isFinite(stats.cache_hit_tokens) && Number(stats.input_tokens) > 0) {
      cacheHit += stats.cache_hit_tokens; cacheInput += Number(stats.input_tokens); cacheN++
    }
  }
  return { turns: messages.value.filter(m => m.sender_id === 'user').length, avgTtft: ttftN ? Math.round(ttftSum / ttftN) : null,
    hasTime, hasUsage, inTok, outTok, cachePct: cacheN && cacheInput ? Math.round(cacheHit / cacheInput * 100) : null }
})

const messageGroups = computed(() => {
  const allMsgs = []
  const replacedInterruptedStreams = new Set()
  messages.value.forEach(m => {
    const event = m.sender_id === 'system'
    const self = m.sender_id === 'user'
    // Parse metadata for tool_calls, chronological parts, and handoff info
    let toolCalls = null
    let parts = null
    let thinkingEvents = null
    let handoffInfo = null
    let modelInfo = null
    let modelNameInfo = null
    let verifiedSources = []
    if (m.metadata) {
      try {
        const meta = typeof m.metadata === 'string' ? JSON.parse(m.metadata) : m.metadata
        if (meta.tool_calls && meta.tool_calls.length > 0) {
          toolCalls = meta.tool_calls
        }
        if (meta.parts && meta.parts.length > 0) {
          parts = meta.parts
            .map(p => p.type === 'text' ? { ...p, text: stripProjectProposal(p.text), rendered: cachedRenderMd(stripProjectProposal(p.text), `${m.id}-part-${p.text?.length || 0}`) } : p)
            .filter(p => p.type !== 'text' || p.text)
        }
        if (meta.thinking_events && meta.thinking_events.length > 0) {
          thinkingEvents = meta.thinking_events
            .map(ev => ({ ...ev, content: cleanText(ev?.content), detail: cleanText(ev?.detail), tool: cleanText(ev?.tool) }))
            .filter(ev => processEventText(ev))
        }
        if (meta.interrupted && meta.stream_id && store.activeStreams[meta.stream_id]?.interrupted) {
          replacedInterruptedStreams.add(meta.stream_id)
        }
        // P0: Extract handoff info from metadata
        if (meta.handoff) {
          handoffInfo = meta.handoff
        }
        if (meta.model || meta.model_name || meta.actual_model) {
          modelInfo = meta.model || meta.actual_model
          modelNameInfo = compactModelBadge(meta.model_name || meta.actual_model || meta.model)
        }
        if (Array.isArray(meta.verified_sources)) verifiedSources = meta.verified_sources
      } catch {}
    }
    const metaSortTs = (() => {
      try {
        const meta = typeof m.metadata === 'string' ? JSON.parse(m.metadata) : (m.metadata || {})
        return meta.sort_ts || meta.stream_started_at || 0
      } catch { return 0 }
    })()
    allMsgs.push({
      id: m.id,
      sender_id: m.sender_id,
      sender_name: m.sender_name,
      text: m.text,
      sources: m.sender_id !== 'user' && m.sender_id !== 'system' ? mergeSources(m.text, verifiedSources) : [],
      rendered: cachedRenderMd(stripProjectProposal(m.text), m.id),
      time: formatMsgTime(m.created_at),
      date: formatMsgDate(m.created_at),
      sortTs: m.clientSortTs || metaSortTs || parseMessageTs(m.created_at),
      clientOrder: m.clientOrder || 0,
      self,
      event,
      showName: !self && !event && (props.type === 'group' || !self),
      toolCalls,
      parts,
      thinkingEvents,
      thinkingExpanded: thinkingEvents || toolCalls || parts ? getThinkingExpanded(`saved-${m.id}`) : false,
      toolsExpanded: toolCalls ? getToolsExpanded(`saved-${m.id}`, false) : false,
      handoffInfo,
      model: modelInfo,
      modelName: modelNameInfo,
      projectProposal: !self && !event ? parseProjectProposal(m.text) : null,
    })
  })
  const latestUserSortTs = allMsgs
    .filter(m => m.sender_id === 'user' && m.sortTs)
    .reduce((max, m) => Math.max(max, m.sortTs || 0), 0)
  for (const sid in store.activeStreams) {
    const s = store.activeStreams[sid]
    if (replacedInterruptedStreams.has(sid)) continue
    if (s.roomId !== props.room.id) continue
    if ((s.threadId || null) !== activeThreadId.value) continue
    const startedAt = s.startedAt || Date.now()
    // Active AI streams are causally triggered by the latest user turn in this
    // view. Do not sort them purely by backend/browser timestamps: client clock
    // skew or fast WS delivery can place the stream above the optimistic user
    // message until the server copy arrives. Anchor live streams after the
    // latest user message; persisted messages keep normal server ordering.
    const streamSortTs = s.interrupted
      ? startedAt
      : Math.max(startedAt, latestUserSortTs ? latestUserSortTs + 1 : startedAt)
    allMsgs.push({
      id: `stream-${sid}`,
      sender_id: s.agentId,
      sender_name: s.agentName,
      text: s.text,
      sources: extractSources(s.text),
      rendered: renderMd(s.text),
      time: s.interrupted ? '已中断' : '',
      date: '',
      sortTs: streamSortTs,
      clientOrder: s.clientOrder || 0,
      self: false,
      showName: props.type === 'group',
      streaming: !s.interrupted,
      interrupted: s.interrupted,
      working: s.working,
      thinkingEvents: s.thinkingEvents || [],
      thinkingExpanded: getThinkingExpanded(sid),
      parts: (s.parts || []).map(p => p.type === 'text' ? { ...p, rendered: renderMd(p.text) } : p),
      toolCalls: s.toolCalls || [],
      toolsExpanded: getToolsExpanded(sid, true), // streaming = true
    })
  }
  allMsgs.sort(compareChatItems)
  const groups = []
  let prevSender = null
  let prevDate = null
  for (const m of allMsgs) {
    if (m.date && prevDate && m.date !== prevDate) {
      groups.push({ separator: m.date, self: false, messages: [] })
    }
    if (m.sender_id !== prevSender) {
      groups.push({ self: m.self, event: m.event, messages: [m] })
    } else {
      groups[groups.length - 1].messages.push(m)
    }
    prevSender = m.sender_id
    prevDate = m.date
  }
  return groups
})

async function fetchMessages({ keepPosition = false, forceScroll = false, older = false } = {}) {
  if (messagesLoading.value || (older && olderMessagesLoading.value)) return
  const area = messagesArea.value
  const wasNearBottom = !area || (area.scrollHeight - area.scrollTop - area.clientHeight < 120)
  const prevHeight = area?.scrollHeight || 0
  const beforeId = older ? messages.value.find(m => Number.isInteger(Number(m.id)))?.id : null
  if (older && !beforeId) return
  if (older) olderMessagesLoading.value = true
  else messagesLoading.value = true
  let data
  try {
    const cursor = beforeId ? `&before_id=${encodeURIComponent(beforeId)}` : ''
    if (activeThreadId.value) {
      data = await api('GET', `/admin/threads/${activeThreadId.value}/messages?limit=${MESSAGE_PAGE_SIZE}${cursor}`)
    } else {
      data = await api('GET', `/admin/rooms/${props.room.id}/messages?limit=${MESSAGE_PAGE_SIZE}${cursor}`)
    }
  } finally {
    if (older) olderMessagesLoading.value = false
    else messagesLoading.value = false
  }
  const newMsgs = data.result || []
  if (older) {
    hasOlderMessages.value = newMsgs.length === MESSAGE_PAGE_SIZE
    const known = new Set(messages.value.map(m => String(m.id)))
    messages.value = sortChatMessages([...newMsgs.filter(m => !known.has(String(m.id))), ...messages.value])
    await nextTick()
    if (area) area.scrollTop += area.scrollHeight - prevHeight
    return
  }
  hasOlderMessages.value = newMsgs.length === MESSAGE_PAGE_SIZE
  // Preserve optimistic messages that haven't appeared in server response yet.
  // When the server-saved user message arrives, copy the optimistic sort anchor
  // onto it so a fast AI stream/reply never jumps above the just-sent user turn.
  const optimistic = messages.value.filter(m => String(m.id).startsWith('tmp-'))
  const optimisticByText = new Map()
  optimistic.forEach(om => {
    if (om.sender_id === 'user') optimisticByText.set(om.text, om)
  })
  const anchoredMsgs = newMsgs.map(sm => {
    if (sm.sender_id !== 'user') return sm
    const om = optimisticByText.get(sm.text)
    if (!om) return sm
    return {
      ...sm,
      clientSortTs: om.clientSortTs || parseMessageTs(sm.created_at),
      clientOrder: om.clientOrder || 0,
    }
  })
  // Keep optimistic messages only until their server copy appears.
  const unsaved = optimistic.filter(om => !newMsgs.some(sm => sm.sender_id === 'user' && sm.text === om.text))
  messages.value = sortChatMessages([...anchoredMsgs, ...unsaved])
  await nextTick()
  if (keepPosition && area) {
    area.scrollTop += area.scrollHeight - prevHeight
  } else if (forceScroll || wasNearBottom) {
    scrollToBottom()
  }
}

async function fetchThreads() {
  const data = await api('GET', `/admin/rooms/${props.room.id}/threads`)
  threads.value = data.result || []
}


const filteredThreads = computed(() => threads.value.filter(t => threadMatches(t.id, t.title, t.last_message)))

function threadMatches(id, title, preview) {
  const q = String(threadFilter.value || '').trim().toLowerCase()
  if (!q) return true
  return [id, title, preview].some(value => String(value || '').toLowerCase().includes(q))
}

function selectThread(threadId) {
  if (messagesLoading.value || olderMessagesLoading.value) return
  activeThreadId.value = threadId
  messages.value = []
  hasOlderMessages.value = true
  fetchMessages({ forceScroll: true })
}

async function createThread() {
  if (creatingThread.value || messagesLoading.value || olderMessagesLoading.value) return
  const title = window.prompt('对话名称', '新对话')?.trim()
  if (!title) return
  creatingThread.value = true
  try {
    const data = await api('POST', `/admin/rooms/${props.room.id}/threads`, { title })
    if (!data?.ok) throw Error(data?.error || '创建对话失败')
    await fetchThreads()
    selectThread(data.result.id)
  } catch (e) { showToast(e.message) }
  finally { creatingThread.value = false }
}

async function deleteThread(threadId) {
  if (!confirm('确定删除此话题及其所有消息？')) return
  await api('DELETE', `/admin/threads/${threadId}`)
  if (activeThreadId.value === threadId) {
    activeThreadId.value = null
  }
  await fetchThreads()
  fetchMessages({ forceScroll: true })
}

// === Task 3: Thread rename ===
function startRenameThread(t) {
  renamingThreadId.value = t.id
  renameThreadTitle.value = t.title
  nextTick(() => {
    const el = renameInput.value
    if (el) {
      // renameInput may be an array due to v-for
      const input = Array.isArray(el) ? el[0] : el
      if (input) input.focus()
    }
  })
}
async function finishRenameThread(t) {
  const newTitle = renameThreadTitle.value.trim()
  if (newTitle && newTitle !== t.title) {
    await api('PATCH', `/admin/threads/${t.id}`, { title: newTitle })
    t.title = newTitle
    await fetchThreads()
  }
  renamingThreadId.value = null
}
function cancelRenameThread() {
  renamingThreadId.value = null
}

// === Message edit/delete ===
const editingMsgId = ref(null)
const editingMsgText = ref('')

function startEditMsg(msg) {
  editingMsgId.value = msg.id
  editingMsgText.value = msg.text
}

function cancelEditMsg() {
  editingMsgId.value = null
  editingMsgText.value = ''
}

async function saveEditMsg(msg) {
  const newText = editingMsgText.value.trim()
  if (!newText) return
  await api('PATCH', `/admin/messages/${msg.id}`, { text: newText })
  // Update local state
  const found = messages.value.find(m => m.id === msg.id)
  if (found) found.text = newText
  editingMsgId.value = null
  editingMsgText.value = ''
  fetchMessages()
}

async function deleteMsg(msg) {
  if (!confirm('确定删除这条消息？')) return
  await api('DELETE', `/admin/messages/${msg.id}`)
  messages.value = messages.value.filter(m => m.id !== msg.id)
}

async function retryMsg(msg) {
  // For user messages: delete and re-send the same text
  // For AI messages: delete the AI response and re-send the last user message before it
  if (msg.sender_id === 'user') {
    const text = msg.text
    await api('DELETE', `/admin/messages/${msg.id}`)
    messages.value = messages.value.filter(m => m.id !== msg.id)
    // Re-send
    inputText.value = text
    await nextTick()
    send()
  } else {
    // Find the last user message before this AI message
    const idx = messages.value.findIndex(m => m.id === msg.id)
    let userMsg = null
    for (let i = idx - 1; i >= 0; i--) {
      if (messages.value[i].sender_id === 'user') {
        userMsg = messages.value[i]
        break
      }
    }
    // Delete the AI message
    await api('DELETE', `/admin/messages/${msg.id}`)
    messages.value = messages.value.filter(m => m.id !== msg.id)
    // Re-send the user message (or just re-trigger with @agent)
    if (userMsg) {
      inputText.value = userMsg.text
      await nextTick()
      send()
    }
  }
}

async function copyMsg(msg) {
  try {
    await navigator.clipboard.writeText(msg.text)
    showToast('已复制到剪贴板')
  } catch (err) {
    // Fallback for older browsers
    const textarea = document.createElement('textarea')
    textarea.value = msg.text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
    showToast('已复制到剪贴板')
  }
}

// Auto-update thread title on first message
async function autoUpdateThreadTitle(text) {
  if (!activeThreadId.value) return
  const thread = threads.value.find(t => t.id === activeThreadId.value)
  if (!thread || thread.title !== '新对话') return
  // Only update if this is the first message (thread has no prior messages)
  const truncated = text.slice(0, 20)
  await api('PATCH', `/admin/threads/${activeThreadId.value}`, { title: truncated })
  thread.title = truncated
}

function formatThreadTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = now - d
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return Math.floor(diff / 60000) + '分钟前'
  if (diff < 86400000) return Math.floor(diff / 3600000) + '小时前'
  if (diff < 604800000) return Math.floor(diff / 86400000) + '天前'
  return ts.slice(0, 10)
}

// Smart scroll: only auto-scroll if user is near bottom
let userScrolledUp = false
function onScroll() {
  const el = messagesArea.value
  if (!el) return
  const threshold = 80
  userScrolledUp = (el.scrollHeight - el.scrollTop - el.clientHeight) > threshold
  showScrollBottom.value = userScrolledUp
  if (el.scrollTop < 80 && hasOlderMessages.value && !olderMessagesLoading.value) {
    fetchMessages({ keepPosition: true, older: true })
  }
}
function scrollToBottom() {
  const el = messagesArea.value
  if (el) el.scrollTop = el.scrollHeight
  userScrolledUp = false
  showScrollBottom.value = false
}
function scrollToBottomIfNeeded() {
  if (!userScrolledUp) scrollToBottom()
}

// === Mention logic ===
function onCompositionStart() {
  isComposingText.value = true
  closeMentions()
}

function onCompositionEnd(e) {
  isComposingText.value = false
  onInput(e)
}

function onInput(e) {
  scheduleAutoResize(e?.target || inputEl.value)
  if (isComposingText.value) return
  const el = inputEl.value
  if (!el) return
  const pos = el.selectionStart
  const text = inputText.value
  // Find latest @ before cursor with no space between
  let i = pos - 1
  let atPos = -1
  while (i >= 0) {
    const ch = text[i]
    if (ch === '@') { atPos = i; break }
    if (ch === ' ' || ch === '\n') break
    i--
  }
  if (atPos === -1) {
    showMentions.value = false
    mentionStartPos.value = -1
    return
  }
  const query = text.slice(atPos + 1, pos)
  mentionStartPos.value = atPos
  mentionQuery.value = query
  showMentions.value = true
  mentionIndex.value = 0
}

function moveMention(delta) {
  if (!showMentions.value) return
  const len = mentionCandidates.value.length
  if (!len) return
  mentionIndex.value = (mentionIndex.value + delta + len) % len
}

function selectMention(candidate) {
  if (mentionStartPos.value < 0) return
  const before = inputText.value.slice(0, mentionStartPos.value)
  const after = inputText.value.slice(inputEl.value.selectionStart)
  const insert = '@' + candidate.name + ' '
  inputText.value = before + insert + after
  closeMentions()
  nextTick(() => {
    const newPos = before.length + insert.length
    inputEl.value.focus()
    inputEl.value.selectionStart = inputEl.value.selectionEnd = newPos
  })
}

function closeMentions() {
  showMentions.value = false
  mentionStartPos.value = -1
}

function onMentionOutsideClick(e) {
  if (!showMentions.value) return
  const target = e.target
  if (target?.closest?.('.mention-popup, .at-btn')) return
  closeMentions()
}

const isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(navigator.userAgent)

function onEnterKey(e) {
  if (isComposingText.value || e?.isComposing) return
  if (showMentions.value && mentionCandidates.value[mentionIndex.value]) {
    selectMention(mentionCandidates.value[mentionIndex.value])
    return
  }
  if (isMobile) {
    // Mobile: Enter = newline
    insertNewline()
  } else {
    // Desktop: Enter = send
    send()
  }
}

function onShiftEnter() {
  // Desktop: Shift+Enter = newline (mobile won't trigger this)
  insertNewline()
}

function insertNewline() {
  const el = inputEl.value
  if (!el) return
  const start = el.selectionStart
  const end = el.selectionEnd
  inputText.value = inputText.value.slice(0, start) + '\n' + inputText.value.slice(end)
  nextTick(() => {
    el.selectionStart = el.selectionEnd = start + 1
    autoResize({ target: el })
  })
}

function onTab() {
  if (showMentions.value && mentionCandidates.value[mentionIndex.value]) {
    selectMention(mentionCandidates.value[mentionIndex.value])
  }
}

function triggerAt() {
  const el = inputEl.value
  if (!el) return
  if (showMentions.value) {
    closeMentions()
    return
  }
  el.focus()
  const pos = el.selectionStart || inputText.value.length
  inputText.value = inputText.value.slice(0, pos) + '@' + inputText.value.slice(pos)
  nextTick(() => {
    el.selectionStart = el.selectionEnd = pos + 1
    onInput({ target: el })
  })
}

// === File upload ===
const MIME_EXTENSIONS = {
  'image/png': 'png', 'image/jpeg': 'jpg', 'image/jpg': 'jpg',
  'image/gif': 'gif', 'image/webp': 'webp', 'image/svg+xml': 'svg',
  'application/pdf': 'pdf', 'application/msword': 'doc',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
  'application/vnd.ms-excel': 'xls',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'xlsx',
  'application/vnd.ms-powerpoint': 'ppt',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'pptx',
  'text/plain': 'txt', 'text/markdown': 'md', 'text/csv': 'csv',
  'application/json': 'json', 'application/xml': 'xml', 'text/html': 'html',
  'application/javascript': 'js', 'text/javascript': 'js',
  'application/typescript': 'ts', 'text/typescript': 'ts',
  'application/x-python': 'py', 'text/x-python': 'py',
  'application/x-shellscript': 'sh',
  'text/x-c': 'c', 'text/x-c++src': 'cpp', 'text/x-java-source': 'java',
  'application/zip': 'zip', 'application/x-rar-compressed': 'rar',
  'application/vnd.rar': 'rar', 'application/x-7z-compressed': '7z',
  'application/gzip': 'gz', 'application/x-tar': 'tar',
  'audio/mpeg': 'mp3', 'audio/wav': 'wav',
  'video/mp4': 'mp4', 'video/webm': 'webm',
  'application/octet-stream': 'bin',
}
const FILE_CATEGORY_EXTS = {
  image: new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'ico', 'avif']),
  archive: new Set(['zip', 'rar', '7z', 'tar', 'gz', 'tgz', 'bz2', 'tbz', 'xz', 'txz']),
  document: new Set(['doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'pdf', 'txt', 'md', 'csv', 'rtf']),
  code: new Set(['js', 'ts', 'jsx', 'tsx', 'py', 'java', 'c', 'cpp', 'h', 'cs', 'rb', 'go', 'rs', 'php', 'swift', 'kt', 'sh', 'sql', 'r', 'lua', 'dart', 'vue', 'svelte', 'json', 'yaml', 'yml', 'toml', 'xml', 'html', 'css', 'scss']),
  media: new Set(['mp3', 'wav', 'ogg', 'flac', 'mp4', 'webm', 'avi', 'mov']),
}

function extensionFromMime(type) {
  if (!type) return 'bin'
  return MIME_EXTENSIONS[type] || type.split('/')[1]?.split('+')[0] || 'bin'
}

function uploadTypeFromFile(file, serverType) {
  if (serverType === 'image' || serverType === 'archive') return serverType
  if (file?.type?.startsWith('image/')) return 'image'
  const ext = (file?.name || '').split('.').pop()?.toLowerCase() || ''
  if (FILE_CATEGORY_EXTS.image.has(ext)) return 'image'
  if (FILE_CATEGORY_EXTS.archive.has(ext)) return 'archive'
  return 'file'
}

function normalizeUploadFile(file, source, index = 0) {
  if (!file) return null
  if (file.name && file.name !== 'image.png') return file
  const isImage = file.type?.startsWith('image/')
  const prefix = (isImage ? 'pasted-image' : source).replace(/[^a-z0-9_-]+/gi, '-').replace(/^-+|-+$/g, '') || 'file'
  const ext = extensionFromMime(file.type)
  return new File([file], `${prefix}-${Date.now()}-${index + 1}.${ext}`, { type: file.type || 'application/octet-stream', lastModified: file.lastModified || Date.now() })
}

function getEventFiles(e) {
  return Array.from(e?.dataTransfer?.files || []).filter(f => f && f.size >= 0)
}

function hasDraggedFiles(e) {
  return Array.from(e?.dataTransfer?.types || []).includes('Files')
}

function collectClipboardFiles(clipboardData) {
  const files = []
  const seen = new Set()
  const add = (file) => {
    if (!file || file.size < 0) return
    const key = `${file.name || ''}:${file.type || ''}:${file.size || 0}:${file.lastModified || 0}`
    if (seen.has(key)) return
    seen.add(key)
    files.push(file)
  }
  Array.from(clipboardData?.files || []).forEach(add)
  // Only check items if files list was empty (getAsFile() creates new objects
  // with different lastModified, causing duplicate uploads of the same image)
  if (!files.length) {
    Array.from(clipboardData?.items || []).forEach(item => {
      if (item.kind !== 'file') return
      try { add(item.getAsFile()) } catch {}
    })
  }
  return files
}

function getClipboardText(clipboardData) {
  try { return clipboardData?.getData?.('text/plain') || '' }
  catch { return '' }
}

function insertTextAtCursor(text) {
  if (!text) return
  const el = inputEl.value
  if (!el) return
  const start = Number.isFinite(el.selectionStart) ? el.selectionStart : inputText.value.length
  const end = Number.isFinite(el.selectionEnd) ? el.selectionEnd : start
  inputText.value = inputText.value.slice(0, start) + text + inputText.value.slice(end)
  nextTick(() => {
    el.focus()
    const pos = start + text.length
    try { el.setSelectionRange(pos, pos) } catch {}
    onInput({ target: el })
  })
}

function uploadAuthHeaders() {
  const token = auth.token || localStorage.getItem('hub_auth_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function parseUploadResponse(response) {
  const text = await response.text().catch(() => '')
  if (!text) return { ok: false, error: response.ok ? '服务器返回空响应' : `HTTP ${response.status}` }
  try { return JSON.parse(text) }
  catch { return { ok: false, error: response.ok ? '响应解析失败' : `HTTP ${response.status}: ${text.slice(0, 120)}` } }
}

async function uploadFiles(files, source = '上传') {
  const normalizedFiles = Array.from(files || [])
    .map((f, idx) => normalizeUploadFile(f, source, idx))
    .filter(f => f && f.size >= 0)
  if (!normalizedFiles.length) return
  isUploadingFiles.value = true
  let okCount = 0
  try {
    for (const f of normalizedFiles) {
      try {
        const data = await uploadFile(f)
        attachments.value.push({ url: data.url, type: uploadTypeFromFile(f, data.type), name: data.name || f.name, size: data.size })
        okCount++
      } catch (err) {
        showToast(`${source}失败: ${err?.message || '网络错误'}`)
      }
    }
  } finally {
    isUploadingFiles.value = false
  }
  if (okCount) {
    inputEl.value?.focus()
    showToast(okCount === 1 ? '已添加到输入框' : `已添加 ${okCount} 个文件`)
  }
}

function onDragEnter(e) {
  if (!hasDraggedFiles(e)) return
  dragDepth++
  isDraggingFiles.value = true
}

function onDragOver(e) {
  if (!hasDraggedFiles(e)) return
  e.dataTransfer.dropEffect = 'copy'
  isDraggingFiles.value = true
}

function onDragLeave(e) {
  if (!hasDraggedFiles(e)) return
  dragDepth = Math.max(0, dragDepth - 1)
  if (dragDepth === 0) isDraggingFiles.value = false
}

async function onDropFiles(e) {
  dragDepth = 0
  isDraggingFiles.value = false
  const files = getEventFiles(e)
  if (!files.length) return
  await uploadFiles(files, '拖拽上传')
}

async function onPaste(e) {
  const files = collectClipboardFiles(e.clipboardData)
  if (!files.length) return
  const text = getClipboardText(e.clipboardData)
  // Prevent default binary/image paste, but keep accompanying clipboard text.
  e.preventDefault()
  insertTextAtCursor(text)
  await uploadFiles(files, '粘贴上传')
}

function isEditableTarget(target) {
  if (!target) return false
  const tag = target.tagName?.toLowerCase?.()
  return tag === 'input' || tag === 'textarea' || target.isContentEditable
}

async function onWindowPaste(e) {
  if (e.defaultPrevented) return
  if (isEditableTarget(e.target)) return
  const files = collectClipboardFiles(e.clipboardData)
  const text = getClipboardText(e.clipboardData)
  if (files.length) {
    e.preventDefault()
    if (text) insertTextAtCursor(text)
    await uploadFiles(files, '粘贴上传')
    return
  }
  if (navigator.clipboard?.read) {
    try {
      const clipItems = await navigator.clipboard.read()
      const apiFiles = []
      for (const item of clipItems) {
        for (const type of item.types) {
          if (type.startsWith('image/') || type.startsWith('video/') || type === 'application/pdf') {
            try { const blob = await item.getType(type); apiFiles.push(new File([blob], 'pasted-' + Date.now() + '.' + (type.split('/')[1] || 'bin'), { type })) } catch {}
          }
        }
      }
      if (apiFiles.length) {
        e.preventDefault()
        if (text) insertTextAtCursor(text)
        await uploadFiles(apiFiles, '粘贴上传')
        return
      }
    } catch {}
  }
  if (!files.length && !text) return
  e.preventDefault()
  if (text) insertTextAtCursor(text)
  if (files.length) await uploadFiles(files, '粘贴上传')
}

async function onFiles(e) {
  const files = Array.from(e.target.files || [])
  await uploadFiles(files, '上传')
  e.target.value = ''
}

function escapeMarkdownLabel(value) {
  return String(value || 'file').replace(/([\\\[\]])/g, '\\$1')
}

async function send() {
  const text = inputText.value.trim()
  const atts = attachments.value.slice()
  if (!text && !atts.length) return

  if (text.startsWith('/')) {
    handleCommand(text)
    inputText.value = ''
    return
  }

  // Build message body — append attachments as markdown
  let body = text
  for (const a of atts) {
    const name = escapeMarkdownLabel(a.name)
    if (a.type === 'image') body += `\n![${name}](${a.url})`
    else body += `\n[${name}](${a.url})`
  }

  // Extract mentions — only resolve names that are actual room members
  const mentions = []
  const memberMap = {}
  if (props.type === 'group' && props.room.members) {
    // In group chats, only allow @mentions for members of this room
    props.room.members.forEach(m => { memberMap[m.name] = m.id })
  } else {
    // In DMs, resolve against all agents (DM partner is always present)
    store.agents.forEach(a => { memberMap[a.name] = a.id })
  }
  const mentionRegex = /@([^\s@,，.。;；:：!！?？]+)/g
  let match
  while ((match = mentionRegex.exec(text)) !== null) {
    const name = match[1].replace(/[*_`~|]/g, '').trim()
    // Handle @全部 — add all members
    if (name === '全部' || name === 'all') {
      if (props.room.members) {
        props.room.members.forEach(m => {
          if (m.id !== 'user' && m.id !== 'system' && !mentions.includes(m.id)) mentions.push(m.id)
        })
      }
    } else {
      const id = memberMap[name]
      if (id && !mentions.includes(id)) mentions.push(id)
    }
  }

  // Default mention: if no explicit @, send to last agent that replied
  if (mentions.length === 0 && props.type !== 'dm') {
    const lastAgentMsg = [...messages.value].reverse().find(m => m.sender_id && m.sender_id !== 'user' && m.sender_id !== 'system')
    if (lastAgentMsg) {
      mentions.push(lastAgentMsg.sender_id)
    } else if (props.room.members?.length) {
      // Fallback: first non-user member
      const first = props.room.members.find(m => m.id !== 'user' && m.id !== 'system')
      if (first) mentions.push(first.id)
    }
  }

  inputText.value = ''
  attachments.value = []
  if (inputEl.value) inputEl.value.style.height = 'auto'

  // Auto-interrupt: keep the old stream in-place and mark it interrupted so the
  // next user turn appears below it in the correct order.
  if (ws._ws && ws._ws.readyState === WebSocket.OPEN) {
    for (const [streamId, stream] of Object.entries(store.activeStreams)) {
      if (stream.roomId === props.room.id && (stream.threadId || null) === activeThreadId.value && (mentions.includes(stream.agentId) || mentions.length === 0)) {
        ws._ws.send(JSON.stringify({ type: 'cancel_stream', stream_id: streamId }))
        markStreamInterrupted(streamId)
      }
    }
  }

  // Optimistic add
  const optimisticNow = Date.now()
  messages.value.push({
    id: 'tmp-' + optimisticNow,
    sender_id: 'user',
    sender_name: '我',
    text: body,
    created_at: new Date(optimisticNow).toISOString(),
    clientSortTs: optimisticNow,
    clientOrder: nextClientOrder(),
  })
  await nextTick()
  scrollToBottom()

  const preparingAgent = store.agents.find(agent => mentions.includes(agent.id)) || props.room.agent
  typingAgent.value = preparingAgent?.name || title.value

  const res = await api('POST', activeThreadId.value ? `/admin/threads/${activeThreadId.value}/send` : `/admin/rooms/${props.room.id}/send`, { text: body, mentions })
  if (res?.ok !== false) {
    const saved = res?.result
    if (saved?.id) {
      const optimistic = messages.value.find(m => String(m.id).startsWith('tmp-') && m.text === body)
      if (optimistic) Object.assign(optimistic, saved, { clientSortTs: optimistic.clientSortTs, clientOrder: optimistic.clientOrder })
    }
  }
  // Auto-update thread title if this is the first message in a '新对话' thread
  autoUpdateThreadTitle(text)
}

async function handleCommand(text) {
  const cmd = text.split(' ')[0]
  if (cmd === '/clear') {
    const data = await api('DELETE', `/admin/rooms/${props.room.id}/messages`)
    if (data.ok) { messages.value = []; showToast('对话已清空') }
  } else if (cmd === '/members') {
    showSettings.value = true
  } else if (cmd === '/compact' || cmd === '/summary') {
    // These need to be sent to the agent as regular messages
    const toastMsg = cmd === '/compact' ? '正在压缩上下文...' : '正在总结对话...'
    showToast(toastMsg)
    const lastAgentMsg = [...messages.value].reverse().find(m => m.sender_id && m.sender_id !== 'user' && m.sender_id !== 'system')
    const mentions = []
    if (lastAgentMsg) mentions.push(lastAgentMsg.sender_id)
    else if (props.room.members?.length) {
      const first = props.room.members.find(m => m.id !== 'user' && m.id !== 'system')
      if (first) mentions.push(first.id)
    }
    messages.value.push({
      id: 'tmp-' + Date.now(),
      sender_id: 'user',
      sender_name: '我',
        text: cmd,
        created_at: new Date().toISOString(),
        clientSortTs: Date.now(),
        clientOrder: nextClientOrder(),
      })
    nextTick(scrollToBottom)
    const endpoint = activeThreadId.value ? `/admin/threads/${activeThreadId.value}/send` : `/admin/rooms/${props.room.id}/send`
    api('POST', endpoint, { text: cmd, mentions })
  } else if (cmd === '/retry') {
    showToast('正在重新生成...')
    const lastAgentMsg = [...messages.value].reverse().find(m => m.sender_id && m.sender_id !== 'user' && m.sender_id !== 'system')
    const mentions = lastAgentMsg ? [lastAgentMsg.sender_id] : []
    const endpoint = activeThreadId.value ? `/admin/threads/${activeThreadId.value}/send` : `/admin/rooms/${props.room.id}/send`
    api('POST', endpoint, { text: '/retry', mentions })
  }
}

function scheduleAutoResize(el) {
  if (!el) return
  if (resizeRaf) cancelAnimationFrame(resizeRaf)
  resizeRaf = requestAnimationFrame(() => {
    resizeRaf = 0
    autoResize({ target: el })
  })
}

function autoResize(e) {
  const el = e?.target
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 120) + 'px'
}

function showToast(msg) {
  const t = document.createElement('div')
  t.className = 'toast'
  t.textContent = msg
  document.body.appendChild(t)
  setTimeout(() => t.remove(), 2000)
}

function safeShareFilename(name) {
  return String(name || 'chat')
    .replace(/[\\/:*?"<>|]+/g, '-')
    .replace(/\s+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'chat'
}

function renderShareText(text) {
  return escapeHtml(text || '')
    .replace(/https?:\/\/[^\s<]+/g, url => `<a href="${url}" target="_blank" rel="noopener noreferrer">查看链接</a>`)
    .replace(/\n/g, '<br>')
}

function buildShareHtml(roomTitle, rows) {
  const generatedAt = new Date().toLocaleString()
  const messagesHtml = rows.map(m => {
    const cls = m.self ? 'msg-group self' : (m.event ? 'msg-group event' : 'msg-group')
    const bubbleCls = m.event ? 'msg event' : 'msg'
    const sender = escapeHtml(m.senderName || '未知')
    const time = escapeHtml(m.time || '')
    return `<article class="${cls}"><div class="${bubbleCls}">${!m.event ? `<div class="sender-name">${sender}</div>` : ''}<div class="msg-text">${renderShareText(m.text)}</div>${!m.event ? `<div class="msg-meta-row"><span>${sender}</span><span>${time}</span></div>` : ''}</div></article>`
  }).join('')
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>${escapeHtml(roomTitle)} - 聊天记录</title>
  <style>
    :root { color-scheme: light dark; --bg:#f7f3ea; --surface:#fffaf1; --surface2:#f2eadc; --text:#1f2933; --text-dim:#6b7280; --text-faint:#9ca3af; --border:rgba(45,106,79,.18); --accent:#2d6a4f; --accent-glow:rgba(45,106,79,.18); --radius-lg:18px; --shadow-sm:0 1px 2px rgba(0,0,0,.05); }
    @media (prefers-color-scheme: dark) { :root { --bg:#11140f; --surface:#1a211b; --surface2:#222b24; --text:#f3f5ef; --text-dim:#b7c0b4; --text-faint:#879083; --border:rgba(232,240,235,.16); --accent:#7fb096; --accent-glow:rgba(127,176,150,.22); } }
    * { box-sizing:border-box; } html, body { margin:0; min-height:100%; } body { font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); }
    .shell { min-height:100vh; display:flex; flex-direction:column; } header { position:sticky; top:0; z-index:2; padding:14px 20px; background:var(--surface); border-bottom:1px solid var(--border); box-shadow:var(--shadow-sm); }
    h1 { margin:0; font-size:17px; line-height:1.3; overflow-wrap:anywhere; } .meta { margin-top:6px; color:var(--text-dim); font-size:12px; }
    main { flex:1; width:100%; max-width:980px; margin:0 auto; padding:16px 20px 24px; display:flex; flex-direction:column; gap:6px; }
    .msg-group { display:flex; flex-direction:column; gap:2px; } .msg { max-width:78%; padding:10px 14px; border-radius:var(--radius-lg); font-size:14.5px; line-height:1.6; word-break:break-word; overflow-wrap:anywhere; }
    .msg-group:not(.self) .msg { align-self:flex-start; background:var(--surface); border:1px solid var(--border); color:var(--text); box-shadow:var(--shadow-sm); }
    .msg-group.self .msg { align-self:flex-end; background:var(--accent); border:1px solid transparent; color:white; box-shadow:0 1px 2px var(--accent-glow); }
    .msg.event { align-self:center; max-width:78%; background:rgba(217,119,6,.08); color:var(--text-dim); border:1px solid rgba(217,119,6,.18); box-shadow:none; border-radius:999px; padding:6px 12px; font-size:12.5px; text-align:center; }
    .sender-name { font-size:12px; color:var(--accent); font-weight:600; margin-bottom:4px; } .self .sender-name { color:rgba(255,255,255,.85); }
    .msg-text { white-space:normal; overflow-wrap:anywhere; } .msg-text a { color:var(--accent); text-decoration:underline; text-underline-offset:2px; word-break:break-all; } .self .msg-text a { color:#bbf7d0; }
    .msg-meta-row { display:flex; justify-content:flex-end; gap:8px; margin-top:4px; font-size:11px; color:var(--text-faint); } .self .msg-meta-row { color:rgba(255,255,255,.7); }
    .empty { color:var(--text-dim); text-align:center; padding:36px 4px; }
    @media (max-width:640px) { header { padding:12px 14px; } main { padding:12px 10px 18px; } .msg { max-width:88%; padding:9px 12px; font-size:14px; } .msg.event { max-width:88%; } h1 { font-size:15px; } }


.thread-search-bar {
  margin: 0 0 10px;
}

.thread-search-bar input {
  min-height: 38px;
}

</style>
</head>
<body>
  <div class="shell">
    <header><h1>${escapeHtml(roomTitle)}</h1><div class="meta">${rows.length} 条消息 · 导出时间：${escapeHtml(generatedAt)} · 离线 HTML 聊天记录</div></header>
    <main>${messagesHtml || '<div class="empty">暂无聊天记录</div>'}</main>
  </div>
</body>
</html>`
}

async function shareChatContent() {
  const messageIds = messages.value
    .filter(m => m?.text && Number.isInteger(Number(m.id)) && !String(m.id).startsWith('tmp-') && !String(m.id).startsWith('stream-'))
    .map(m => Number(m.id))
  if (!messageIds.length) {
    showToast('当前没有可分享的聊天内容')
    return
  }
  const result = await api('POST', `/admin/rooms/${props.room.id}/share`, { message_ids: messageIds })
  if (!result?.ok || !result.result?.url) {
    showToast(result?.error || '生成分享链接失败')
    return
  }
  const shareUrl = new URL(result.result.url, window.location.origin).toString()
  if (navigator.share) {
    try {
      await navigator.share({ title: `${title.value || '聊天记录'} · Myna`, text: '查看这段 Myna 对话，并在自己的马哥中继续', url: shareUrl })
      showToast('已打开系统分享')
      return
    } catch (err) {
      if (err?.name === 'AbortError') return
    }
  }
  await navigator.clipboard.writeText(shareUrl)
  showToast('分享链接已复制')
}

async function onMembersChanged() {
  // refresh conversation list so room.members reflects latest
  await loadConversations()
  // Also refresh room members directly for mention candidates
  try {
    const data = await api('GET', '/admin/rooms')
    const updated = (data.result || []).find(r => r.id === props.room.id)
    if (updated && updated.members) {
      props.room.members = updated.members
    }
  } catch {}
}

async function respondApproval(decision) {
  if (!pendingApproval.value) return
  const id = pendingApproval.value.id
  pendingApproval.value = null
  await api('POST', `/admin/approvals/${id}`, { decision })
}

async function respondSkillApproval(decision) {
  if (!pendingSkillApproval.value) return
  const id = pendingSkillApproval.value.id
  pendingSkillApproval.value = null
  await api('POST', `/admin/approvals/${id}`, { decision })
}

function handleWS(msg) {
  if (msg.type === 'stream_start' && msg.room_id === props.room.id) {
    // activeStreams is now managed globally in store.js
    typingAgent.value = null
    nextTick(scrollToBottomIfNeeded)
  } else if (msg.type === 'tool_call' && store.activeStreams[msg.stream_id]) {
    // Tool calls are now handled globally in store.js — just scroll
    nextTick(scrollToBottomIfNeeded)
  } else if (msg.type === 'tool_result' && store.activeStreams[msg.stream_id]) {
    // Tool results are now handled globally in store.js — just scroll
    nextTick(scrollToBottomIfNeeded)
  } else if (msg.type === 'stream_token' && store.activeStreams[msg.stream_id]) {
    // Stream tokens are now handled globally in store.js — just scroll
    nextTick(scrollToBottomIfNeeded)
  } else if (msg.type === 'stream_end' && msg.room_id === props.room.id) {
    typingAgent.value = null
  } else if (msg.type === 'new_message' && msg.room_id === props.room.id) {
    // Only fetch if thread matches current view
    const msgThread = msg.thread_id || null
    if (msgThread === activeThreadId.value && msg.message) {
      const incoming = msg.message
      const idx = messages.value.findIndex(m => String(m.id) === String(incoming.id))
      if (idx >= 0) messages.value[idx] = incoming
      else messages.value = sortChatMessages([...messages.value, incoming])
      nextTick(scrollToBottomIfNeeded)
    }
    // Refresh threads list in case a workflow created a new thread
    fetchThreads()
  } else if (msg.type === 'typing' && msg.room_id === props.room.id) {
    typingAgent.value = msg.from?.name || null
    setTimeout(() => { typingAgent.value = null }, 30000)
  } else if (msg.type === 'handoff_status' && msg.room_id === props.room.id) {
    // P0: Show handoff in-progress indicator
    const names = (msg.to_agent_names || []).join(' → ')
    if (names) {
      typingAgent.value = `→ ${names}`
      nextTick(scrollToBottomIfNeeded)
      setTimeout(() => { typingAgent.value = null }, 4000)
    }
  } else if (msg.type === 'approval_request' && msg.room_id === props.room.id) {
    // Show approval dialog
    pendingApproval.value = {
      id: msg.approval_id,
      command: msg.command,
      description: msg.description,
      agentName: msg.agent_name,
    }
  } else if (msg.type === 'skill_approval_request' && msg.room_id === props.room.id) {
    pendingSkillApproval.value = {
      id: msg.approval_id,
      action: msg.action,
      agentName: msg.agent_name,
      details: msg.details || {},
    }
  } else if (msg.type === 'message_deleted' && msg.room_id === props.room.id) {
    // Remove deleted message from local list
    const msgThread = msg.thread_id || null
    if (msgThread === activeThreadId.value) {
      messages.value = messages.value.filter(m => m.id !== msg.message_id)
    }
  }
}

function onShortcutViewportResize() {
  shortcutViewportTick.value++
  clampShortcutPosition()
}

onMounted(() => {
  try {
    const savedShortcutPosition = JSON.parse(localStorage.getItem('shortcut_floating_pos') || 'null')
    if (savedShortcutPosition && Number.isFinite(savedShortcutPosition.x) && Number.isFinite(savedShortcutPosition.y)) {
      shortcutPosition.value = savedShortcutPosition
    }
  } catch {}
  clampShortcutPosition()
  window.addEventListener('resize', onShortcutViewportResize)
  window.addEventListener('paste', onWindowPaste)
  clearUnread(props.room.id)
  currentRoomId.value = props.room.id
  fetchMessages({ forceScroll: true })
  fetchThreads()
  ws.onMessage(handleWS)
  messagesArea.value?.addEventListener('click', onContentClick)
  if (props.initialPrompt) {
    inputText.value = props.initialPrompt
    nextTick(async () => {
      await send()
      emit('prompt-consumed')
    })
  }
  document.addEventListener('click', onMentionOutsideClick)
  // If there are already active streams for this room (e.g. from WS reconnect before mount),
  // scroll to bottom to show the generating bubble
  nextTick(() => {
    const hasActiveStream = Object.values(store.activeStreams).some(s => s.roomId === props.room.id)
    if (hasActiveStream) scrollToBottom()
  })
})

onUnmounted(() => {
  window.removeEventListener('resize', onShortcutViewportResize)
  window.removeEventListener('paste', onWindowPaste)
  document.removeEventListener('pointermove', onShortcutPointerMove)
  if (resizeRaf) cancelAnimationFrame(resizeRaf)
  closeMessageContextMenu()
  currentRoomId.value = null
  ws.offMessage(handleWS)
  messagesArea.value?.removeEventListener('click', onContentClick)
  document.removeEventListener('click', onMentionOutsideClick)
})

// Note: room switching is handled by :key on <ChatView> which destroys/recreates the component
</script>

<style scoped>
.msg.has-citations { padding-top:30px; }
.message-citations { position:absolute; top:8px; right:10px; z-index:2; display:flex; align-items:center; justify-content:flex-end; gap:4px; max-width:calc(100% - 20px); overflow-x:auto; scrollbar-width:none; }
.message-citations::-webkit-scrollbar { display:none; }
.citation-badge { display:inline-flex; align-items:center; justify-content:center; min-width:25px; height:19px; padding:0 5px; border:1px solid color-mix(in srgb,var(--accent) 30%,var(--border)); border-radius:6px; background:color-mix(in srgb,var(--accent) 9%,var(--surface)); color:var(--accent); font-size:10px; font-weight:800; line-height:1; text-decoration:none; box-shadow:0 1px 3px rgba(0,0,0,.05); }
.citation-badge:hover { border-color:var(--accent); background:var(--accent-soft); }
.msg.self .citation-badge { border-color:rgba(255,255,255,.35); background:rgba(255,255,255,.14); color:#fff; }
.project-proposal-card { margin-top:12px; padding:16px; border:1px solid color-mix(in srgb,var(--accent) 35%,var(--border)); border-radius:14px; background:color-mix(in srgb,var(--accent) 7%,var(--surface)); }
.project-proposal-kicker { color:var(--accent); font-size:12px; font-weight:700; letter-spacing:.06em; }
.project-proposal-card h3 { margin:5px 0 6px; font-size:17px; }
.project-proposal-card p { margin:0 0 12px; color:var(--text-2); line-height:1.55; }
.project-role { display:grid; grid-template-columns:minmax(64px,auto) 1fr; gap:10px; padding:8px 0; border-top:1px solid var(--border); font-size:13px; }
.project-role span { color:var(--text-2); }
.project-proposal-actions { display:flex; justify-content:flex-end; align-items:center; margin-top:12px; }
.project-confirm-btn { border:0; border-radius:9px; padding:9px 14px; background:var(--accent); color:#fff; font-weight:700; cursor:pointer; }
.project-confirm-btn:disabled { opacity:.55; cursor:wait; }
.project-created { color:var(--accent); font-size:13px; font-weight:700; }
.shortcut-trigger-btn {
  position: fixed;
  z-index: 10011;
  height: 32px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  color: var(--accent);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 700;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
  transition: all 0.15s ease;
  user-select: none;
  -webkit-user-select: none;
  touch-action: none;
}
.shortcut-trigger-btn.dragging,
.shortcut-trigger-btn:active {
  cursor: grabbing;
}
.shortcut-trigger-btn:hover,
.shortcut-trigger-btn.active {
  background: color-mix(in srgb, var(--accent-soft) 40%, var(--surface));
  color: var(--accent);
  border-color: color-mix(in srgb, var(--accent) 55%, var(--border));
}
.shortcut-trigger-btn svg {
  width: 15px;
  height: 15px;
}
.shortcut-card {
  position: fixed;
  width: min(440px, calc(100vw - 28px));
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  box-shadow: var(--shadow-lg);
  z-index: 10012;
  animation: slideUp 0.16s ease;
  overflow: auto;
}
.shortcut-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  cursor: grab;
  touch-action: none;
  user-select: none;
  padding: 0 2px 8px;
  color: var(--text-2);
  font-size: 12px;
  font-weight: 700;
}
.shortcut-drag-hint {
  margin-left: auto;
  font-size: 11px;
  font-weight: 500;
  color: var(--text-dim);
}
.shortcut-close {
  width: 22px;
  height: 22px;
  border: none;
  border-radius: 999px;
  background: transparent;
  color: var(--text-dim, #888);
  font-size: 18px;
  cursor: pointer;
  line-height: 1;
  padding: 0 2px;
}
.shortcut-close:hover {
  background: var(--surface2);
  color: var(--text);
}
.shortcut-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(112px, 1fr));
  gap: 8px;
}
.shortcut-card-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 40px;
  padding: 8px 10px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--bg);
  color: var(--text-2);
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;
}
.shortcut-card-item:hover {
  border-color: var(--accent);
  color: var(--accent);
  background: color-mix(in srgb, var(--accent-soft) 55%, var(--bg));
  transform: translateY(-1px);
}
.shortcut-card-item svg {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
}
.shortcut-card-item span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
@media (max-width: 767px) {
  .shortcut-trigger-btn {
    height: 30px;
    padding: 0 10px;
    font-size: 12px;
  }
  .shortcut-card {
    width: min(360px, calc(100vw - 20px));
  }
  .shortcut-card-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
.scroll-bottom-btn {
  position: fixed;
  right: 18px;
  bottom: 86px;
  width: 42px;
  height: 42px;
  border-radius: 999px;
  border: 1px solid color-mix(in srgb, var(--accent) 45%, var(--border));
  background: var(--surface);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 10020;
  cursor: pointer;
  box-shadow: 0 8px 24px rgba(0,0,0,.35);
}
.scroll-bottom-btn:hover {
  background: color-mix(in srgb, var(--accent-soft) 45%, var(--surface));
  color: var(--accent);
}
.scroll-bottom-btn svg {
  width: 20px;
  height: 20px;
}

.thinking-bubble {
  margin: 6px 0 8px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 12px;
  background: rgba(148, 163, 184, 0.07);
  color: var(--text-dim);
  overflow: hidden;
}
.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  cursor: pointer;
  user-select: none;
  font-size: 12px;
}
.thinking-dot {
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--text-dim);
  opacity: .55;
}
.thinking-dot.active {
  background: var(--accent);
  opacity: 1;
  animation: thinkingPulse 1.2s ease-in-out infinite;
}
.thinking-label {
  font-weight: 600;
  color: var(--text);
}
.thinking-count {
  margin-left: auto;
  font-size: 11px;
  opacity: .75;
}
.thinking-chevron {
  width: 14px;
  height: 14px;
  transition: transform .18s ease;
}
.thinking-bubble:not(.collapsed) .thinking-chevron {
  transform: rotate(180deg);
}
.thinking-steps {
  border-top: 1px solid rgba(148, 163, 184, 0.18);
  padding: 4px 10px 9px;
}
.thinking-step {
  display: flex;
  gap: 8px;
  padding: 5px 0;
  font-size: 12px;
  line-height: 1.45;
}
.thinking-step-stage {
  flex: 0 0 auto;
  color: var(--accent);
  font-weight: 600;
}
.thinking-step.error .thinking-step-stage {
  color: #ef4444;
}
.thinking-step-content {
  min-width: 0;
  word-break: break-word;
}
.process-tool-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
.process-tool-card {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.05);
  padding: 8px 10px;
}
.process-tool-head {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 600;
}
.process-tool-status {
  color: var(--accent);
}
.process-tool-card.error .process-tool-status {
  color: #ef4444;
}
.process-tool-name {
  color: var(--text);
}
.process-tool-summary,
.process-tool-result {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--text-dim);
}
.process-tool-result {
  padding: 7px 8px;
  border-radius: 8px;
  background: rgba(148, 163, 184, 0.09);
}
.process-tool-result.error {
  color: #ef4444;
}
.msg-model {
  font-size: 10px;
  color: var(--text-faint);
  opacity: .75;
  background: rgba(128, 128, 128, 0.15);
  padding: 1px 5px;
  border-radius: 3px;
  white-space: nowrap;
}
.msg-group.self .msg .msg-model {
  color: rgba(255, 255, 255, 0.7);
}
.skill-approval-dialog {
  max-width: 620px;
}
.skill-approval-content {
  padding: 12px 0;
  max-height: 400px;
  overflow-y: auto;
}
.skill-approval-field {
  margin-bottom: 12px;
}
.skill-approval-field label {
  display: block;
  font-size: 12px;
  font-weight: 700;
  color: var(--text-dim);
  margin-bottom: 4px;
}
.skill-approval-name {
  font-weight: 600;
  color: var(--accent);
}
.skill-approval-content-view {
  font-size: 13px;
  font-family: 'SF Mono', 'Fira Code', monospace;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
  padding: 12px;
  background: var(--surface2);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  max-height: 250px;
  overflow-y: auto;
  color: var(--text);
}
@keyframes thinkingPulse {
  0%, 100% { transform: scale(1); opacity: .75; }
  50% { transform: scale(1.35); opacity: 1; }
}
</style>

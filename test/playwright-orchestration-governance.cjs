const { chromium } = require('playwright');

const BASE = process.env.MYNA_BASE || 'http://localhost:3456';
const PASSWORD = process.env.MYNA_PASSWORD || 'admin123';
const QWE_BASE = process.env.QWE_BASE || 'https://qweapi.com/v1';
const QWE_KEY = process.env.QWE_KEY || '';
const MODEL_ID = process.env.QWE_MODEL || 'claude-opus-4-6';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function login() {
  const res = await fetch(`${BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ password: PASSWORD }),
  });
  const text = await res.text();
  const json = text ? JSON.parse(text) : {};
  if (!res.ok || !json.token) throw new Error(`login failed: ${res.status} ${text.slice(0, 200)}`);
  return json.token;
}

async function api(path, options = {}, token) {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  const json = text ? JSON.parse(text) : {};
  if (!res.ok) throw new Error(`${path} HTTP ${res.status}: ${text.slice(0, 500)}`);
  return json;
}

async function waitForMessages(roomId, predicate, token, timeoutMs = 180000) {
  const deadline = Date.now() + timeoutMs;
  let all = [];
  while (Date.now() < deadline) {
    all = ((await api(`/admin/rooms/${roomId}/messages?limit=100`, {}, token)).result || []);
    if (predicate(all)) return all;
    await sleep(2500);
  }
  return all;
}

async function ensureModelConfig(page, token, stamp) {
  await page.locator('[title="设置"]').click();
  await page.getByText('供应商管理').click();
  await page.getByText('新增供应商').click();
  await page.locator('input[placeholder*="OpenAI"]').fill(`QWE Orchestration ${stamp}`);
  await page.locator('input[placeholder="https://api.openai.com/v1"]').fill(QWE_BASE);
  await page.locator('input[placeholder="sk-..."]').fill(QWE_KEY);
  await page.getByText('获取模型列表').click();
  await page.waitForSelector('.model-option', { timeout: 45000 });
  await page.locator('.search-mini').fill(MODEL_ID);
  await page.locator('.model-option', { hasText: MODEL_ID }).first().click();
  await page.waitForSelector('.selected-model', { timeout: 10000 });
  const optionCountAfterSelect = await page.locator('.model-option').count();
  const selectedText = await page.locator('.selected-model').innerText();
  await page.getByText('创建').click();
  await sleep(1000);
  const created = ((await api('/admin/models', {}, token)).result || []).find(m => m.name === `QWE Orchestration ${stamp}`);
  if (!created) throw new Error('model config was not created through UI');
  return { config: created, optionCountAfterSelect, selectedText };
}

function parseMaybeJson(value) {
  if (!value || typeof value !== 'string') return value || null;
  try {
    return JSON.parse(value);
  } catch {
    return value;
  }
}

async function createAgent(token, name, description, modelConfigId) {
  const agent = (await api('/admin/agents', {
    method: 'POST',
    body: JSON.stringify({ name, description }),
  }, token)).result;
  await api(`/admin/agents/${agent.id}`, {
    method: 'PUT',
    body: JSON.stringify({
      name,
      description,
      model_config_id: modelConfigId,
      tools_config: {
        disabled_toolsets: ['terminal', 'file', 'http', 'browser', 'memory', 'skills'],
        preferred_tools: '本轮测试不要使用任何工具，只通过群聊文字协作。',
      },
    }),
  }, token);
  return agent;
}

async function main() {
  if (!QWE_KEY) throw new Error('QWE_KEY is required');

  const token = await login();
  const stamp = Date.now().toString(36);
  const result = {
    base: BASE,
    model: {},
    settingsUi: {},
    collaboration: {},
    lowValueGuard: {},
    interrupt: {},
    screenshots: {},
    passed: {},
  };

  const browser = await chromium.launch({ headless: false, slowMo: 35 });
  const context = await browser.newContext({ viewport: { width: 1440, height: 960 } });
  const page = await context.newPage();
  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(`${msg.type()}: ${msg.text()}`));
  page.on('pageerror', err => consoleLogs.push(`pageerror: ${err.message}`));

  try {
    await page.goto(BASE, { waitUntil: 'domcontentloaded' });
    await page.evaluate(t => localStorage.setItem('hub_auth_token', t), token);
    await page.reload({ waitUntil: 'networkidle' });

    const { config, optionCountAfterSelect, selectedText } = await ensureModelConfig(page, token, stamp);
    result.model = {
      id: config.id,
      model: config.model,
      optionCountAfterSelect,
      selectedText,
    };

    const pmName = `产品经理${stamp}`;
    const devName = `程序开发${stamp}`;
    const qaName = `程序测试${stamp}`;

    const pmDesc = `你是产品经理。收到用户需求后，先给两条验收标准，然后必须 @${devName} 请求开发。回复 80 字以内。不要使用工具。`;
    const devDesc = `你是程序开发。收到产品经理请求后，回复必须包含“开发完成”，然后必须 @${qaName} 请求测试复核。回复 80 字以内。不要使用工具。`;
    const qaDesc = `你是程序测试。收到开发请求后，回复必须包含“测试通过”，然后必须 @${pmName} 回报测试结果。回复 80 字以内。不要使用工具。`;
    const loopDesc = `你是低价值循环测试智能体。无论收到什么，都只回复：@${devName} 收到，谢谢，没有补充。不要使用工具。`;

    const pm = await createAgent(token, pmName, pmDesc, config.id);
    const dev = await createAgent(token, devName, devDesc, config.id);
    const qa = await createAgent(token, qaName, qaDesc, config.id);
    const loop = await createAgent(token, `低价值回复${stamp}`, loopDesc, config.id);

    const room = (await api('/admin/rooms', {
      method: 'POST',
      body: JSON.stringify({
        name: `编排治理测试${stamp}`,
        description: '三智能体协作和防循环真实浏览器测试',
        type: 'group',
      }),
    }, token)).result;
    await api(`/admin/rooms/${room.id}/members`, {
      method: 'POST',
      body: JSON.stringify({ agent_ids: [pm.id, dev.id, qa.id, loop.id] }),
    }, token);
    await api(`/admin/rooms/${room.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        description: '三智能体协作和防循环真实浏览器测试',
        settings_json: {
          collaboration_mode: 'guided',
          context_strategy: 'auto',
          max_chain_depth: 6,
          context_messages_limit: 0,
          collaboration_guide: `用户先 @${pmName}。${pmName} 主动 @${devName}，${devName} 主动 @${qaName}，${qaName} 主动 @${pmName} 汇总。`,
          handoff_rules: [
            { source: pm.name, target: dev.name, keywords: ['验收标准'], trigger: '产品经理拆解后' },
            { source: dev.name, target: qa.name, keywords: ['开发完成'], trigger: '开发完成后' },
            { source: qa.name, target: pm.name, keywords: ['测试通过'], trigger: '测试通过后' },
          ],
          workspace_path: '',
        },
      }),
    }, token);

    await page.reload({ waitUntil: 'networkidle' });
    await page.getByText(room.name).click();
    await page.locator('.more-btn[title="群聊信息"], .more-btn').first().click();
    await page.waitForSelector('select', { timeout: 10000 });
    const selects = page.locator('select');
    await selects.nth(0).selectOption('free');
    await sleep(500);
    await selects.nth(0).selectOption('guided');
    await sleep(500);
    await selects.nth(1).selectOption('fixed');
    await sleep(500);
    await selects.nth(1).selectOption('auto');
    await sleep(800);
    const roomAfterUi = ((await api('/admin/rooms', {}, token)).result || []).find(r => r.id === room.id);
    const savedSettings = typeof roomAfterUi.settings_json === 'string' ? JSON.parse(roomAfterUi.settings_json) : roomAfterUi.settings_json;
    result.settingsUi = {
      savedCollaborationMode: savedSettings.collaboration_mode,
      savedContextStrategy: savedSettings.context_strategy,
      contextInputDisabledInAuto: await page.locator('input[type="number"]').nth(1).isDisabled().catch(() => null),
    };
    result.screenshots.settings = `D:/VSAI/myna/test/orchestration-settings-${stamp}.png`;
    await page.screenshot({ path: result.screenshots.settings, fullPage: true });

    await page.locator('.more-btn[title="返回聊天"], .more-btn.active').first().click();
    await page.waitForSelector('.input-bar textarea', { timeout: 10000 });
    await page.locator('.input-bar textarea').fill(`@${pm.name}，请组织登录页“记住我开关”的小功能协作：先验收标准，再开发，再测试。`);
    await page.keyboard.press('Enter');
    const collabMessages = await waitForMessages(room.id, messages => {
      const pmCount = messages.filter(m => m.sender_id === pm.id).length;
      const senders = new Set(messages.map(m => m.sender_id));
      return pmCount >= 2 && senders.has(dev.id) && senders.has(qa.id);
    }, token, 240000);
    const relevant = collabMessages
      .filter(m => ['user', pm.id, dev.id, qa.id].includes(m.sender_id))
      .map(m => ({
        id: m.id,
        sender_id: m.sender_id,
        sender_name: m.sender_name,
        text: String(m.text || ''),
        mentions: parseMaybeJson(m.mentions) || [],
        metadata: parseMaybeJson(m.metadata),
      }));
    const pmFirst = relevant.find(m => m.sender_id === pm.id);
    const devMsg = relevant.find(m => m.sender_id === dev.id);
    const qaMsg = relevant.find(m => m.sender_id === qa.id);
    const pmFinal = [...relevant].reverse().find(m => m.sender_id === pm.id && m.id !== pmFirst?.id);
    result.collaboration = {
      messages: relevant,
      pmToDev: !!(pmFirst?.mentions || []).includes(dev.id),
      devToQa: !!(devMsg?.mentions || []).includes(qa.id),
      qaToPm: !!(qaMsg?.mentions || []).includes(pm.id),
      pmFinalSeen: !!pmFinal,
    };
    result.screenshots.collaboration = `D:/VSAI/myna/test/orchestration-collab-${stamp}.png`;
    await page.screenshot({ path: result.screenshots.collaboration, fullPage: true });

    const beforeGuardMax = Math.max(0, ...collabMessages.map(m => m.id));
    await page.locator('.input-bar textarea').fill(`@${loop.name}，请回复你的固定话术。`);
    await page.keyboard.press('Enter');
    const guardMessages = await waitForMessages(room.id, messages => {
      return messages.some(m => m.id > beforeGuardMax && m.sender_id === loop.id);
    }, token, 120000);
    await sleep(5000);
    const guardAfter = ((await api(`/admin/rooms/${room.id}/messages?limit=100`, {}, token)).result || []);
    const loopMsg = guardAfter.find(m => m.id > beforeGuardMax && m.sender_id === loop.id);
    const devAfterLoop = guardAfter.find(m => m.id > (loopMsg?.id || beforeGuardMax) && m.sender_id === dev.id);
    const loopMetadata = parseMaybeJson(loopMsg?.metadata);
    result.lowValueGuard = {
      loopReply: loopMsg ? {
        text: loopMsg.text,
        mentions: parseMaybeJson(loopMsg.mentions) || [],
        metadata: loopMetadata,
      } : null,
      suppressed: !!loopMetadata?.handoff?.suppressed?.some(s => s.reason === 'low_value_reply'),
      devWasNotTriggeredAfterLowValue: !devAfterLoop,
    };

    const beforeInterruptMax = Math.max(0, ...guardAfter.map(m => m.id));
    await page.locator('.input-bar textarea').fill(`@${pm.name}，请写一个很长的三段分析，慢慢展开。`);
    await page.keyboard.press('Enter');
    await sleep(1800);
    await page.locator('.input-bar textarea').fill(`@${pm.name}，打断上一条，改成只回复：新的请求收到。`);
    await page.keyboard.press('Enter');
    const interruptMessages = await waitForMessages(room.id, messages => {
      return messages.filter(m => m.id > beforeInterruptMax && m.sender_id === pm.id).length >= 1;
    }, token, 180000);
    const body = await page.locator('body').innerText();
    result.interrupt = {
      sawInterruptedLabel: body.includes('已中断'),
      pmRepliesAfterInterrupt: interruptMessages
        .filter(m => m.id > beforeInterruptMax && m.sender_id === pm.id)
        .map(m => ({ id: m.id, text: String(m.text || '').slice(0, 240), metadata: parseMaybeJson(m.metadata) })),
    };
    result.screenshots.interrupt = `D:/VSAI/myna/test/orchestration-interrupt-${stamp}.png`;
    await page.screenshot({ path: result.screenshots.interrupt, fullPage: true });

    result.passed = {
      modelUiCollapse: optionCountAfterSelect === 0 && String(selectedText || '').includes(MODEL_ID),
      settingsSaved: result.settingsUi.savedCollaborationMode === 'guided' && result.settingsUi.savedContextStrategy === 'auto',
      allThreeAgentsChained: result.collaboration.pmToDev && result.collaboration.devToQa && result.collaboration.qaToPm && result.collaboration.pmFinalSeen,
      lowValueSuppressed: result.lowValueGuard.suppressed && result.lowValueGuard.devWasNotTriggeredAfterLowValue,
      interruptObserved: result.interrupt.sawInterruptedLabel && result.interrupt.pmRepliesAfterInterrupt.length > 0,
    };
    result.consoleLogs = consoleLogs.slice(-30);
    console.log(JSON.stringify(result, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});

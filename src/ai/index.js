/**
 * AI Reply Module
 * Handles LLM API calls for agent responses.
 * Reads config from ~/.hermes/config.yaml and .env
 */

const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const HERMES_HOME = process.env.HERMES_HOME || path.join(require('os').homedir(), '.hermes');
const CONFIG_PATH = path.join(HERMES_HOME, 'config.yaml');
const ENV_PATH = path.join(HERMES_HOME, '.env');

function getConfig() {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
    const config = yaml.load(raw);
    const provider = config.model?.provider || '';
    const providerName = provider.replace('custom:', '');
    const providerConfig = config.providers?.[providerName] || {};
    const keyEnv = providerConfig.key_env || '';
    let apiKey = '';
    if (keyEnv && fs.existsSync(ENV_PATH)) {
      const envContent = fs.readFileSync(ENV_PATH, 'utf8');
      const match = envContent.match(new RegExp(`^${keyEnv}=['"]?([^'"\\n]+)`, 'm'));
      if (match) apiKey = match[1];
    }
    return {
      model: config.model?.default || 'gpt-4o',
      baseUrl: providerConfig.base_url || 'https://api.openai.com/v1',
      apiKey
    };
  } catch (e) {
    return null;
  }
}

/**
 * Call LLM API with chat completions format
 * @param {Object} agent - { id, name, description }
 * @param {Array} messages - conversation history [{role, content, name?}]
 * @param {Object} options - { maxTokens }
 * @returns {string|null} - AI response text or null on failure
 */
async function chatCompletion(agent, messages, options = {}) {
  const config = getConfig();
  if (!config || !config.apiKey) {
    console.error('[AI] No API config found');
    return null;
  }

  const systemPrompt = agent.description
    ? `你是 ${agent.name}。${agent.description}\n\n请用中文回复，保持简洁友好。`
    : `你是 ${agent.name}，一个智能助手。请用中文回复，保持简洁友好。`;

  const body = {
    model: config.model,
    messages: [
      { role: 'system', content: systemPrompt },
      ...messages
    ],
    max_tokens: options.maxTokens || 1024,
    temperature: 0.7
  };

  try {
    const url = config.baseUrl.replace(/\/$/, '') + '/chat/completions';
    const resp = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + config.apiKey
      },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60000)
    });

    if (!resp.ok) {
      const errText = await resp.text().catch(() => '');
      console.error(`[AI] API error ${resp.status}: ${errText.slice(0, 200)}`);
      return null;
    }

    const data = await resp.json();
    const content = data.choices?.[0]?.message?.content;
    return content || null;
  } catch (e) {
    console.error('[AI] Request failed:', e.message);
    return null;
  }
}

/**
 * Process a message and generate AI replies from mentioned/all agents
 * Supports chain collaboration: if agent A's reply @mentions agent B, B will also reply.
 * @param {Object} db - database instance
 * @param {Object} wsManager - WebSocket manager
 * @param {string} roomId - room where message was sent
 * @param {string} senderId - who sent the message (usually 'user' or 'system')
 * @param {string} text - message text
 * @param {Array} mentions - array of agent IDs that were @mentioned
 * @param {string} roomType - 'group' or 'dm'
 * @param {number} chainDepth - recursion depth for chain collaboration (max 5)
 */
async function processMessage(db, wsManager, roomId, senderId, text, mentions = [], roomType = 'group', chainDepth = 0) {
  const MAX_CHAIN_DEPTH = 5; // Prevent infinite loops
  if (chainDepth >= MAX_CHAIN_DEPTH) {
    console.log(`[AI] Chain depth ${chainDepth} reached max, stopping.`);
    return;
  }

  const members = await db.getRoomMembers(roomId);
  
  // Determine which agents should reply
  let respondingAgents = [];
  
  if (roomType === 'dm') {
    // In DM, the agent always replies
    respondingAgents = members.filter(m => m.id !== senderId && m.id !== 'system' && m.id !== 'user');
  } else if (mentions.length > 0) {
    // In group, only mentioned agents reply
    respondingAgents = members.filter(m => mentions.includes(m.id));
  } else if (chainDepth === 0) {
    // First message with no mentions in group: all agents reply
    respondingAgents = members.filter(m => m.id !== senderId && m.id !== 'system' && m.id !== 'user');
  }
  // For chain messages (chainDepth > 0) with no mentions, don't trigger anyone

  if (respondingAgents.length === 0) return;

  // Get recent message history for context
  const recentMessages = await db.getRoomMessages(roomId, 20);
  
  // For each responding agent, call LLM
  for (const agent of respondingAgents) {
    const fullAgent = await db.getAgentById(agent.id);
    if (!fullAgent) continue;

    // Build conversation history
    const history = recentMessages.map(m => ({
      role: m.sender_id === agent.id ? 'assistant' : 'user',
      content: m.sender_name && m.sender_id !== agent.id
        ? `[${m.sender_name}]: ${m.text}`
        : m.text
    }));

    // Add collaboration context if in a chain
    if (chainDepth > 0) {
      history.push({
        role: 'user',
        content: `[系统提示]: 你被 @提及了，请根据上下文回复。如果需要其他智能体协助，可以在回复中 @他们的名字。`
      });
    }

    // Call LLM
    const reply = await chatCompletion(fullAgent, history);
    if (!reply) continue;

    // Save agent's reply as a message
    // Parse any @mentions in the agent's reply for chain collaboration
    const replyMentions = [];
    const mentionRegex = /@(\S+)/g;
    let match;
    const allAgents = await db.listAgents();
    while ((match = mentionRegex.exec(reply)) !== null) {
      const mentioned = allAgents.find(a => a.name === match[1] && a.id !== agent.id);
      if (mentioned) replyMentions.push(mentioned.id);
    }

    const message = await db.createMessage(roomId, agent.id, reply, 'markdown', null, replyMentions);

    // Notify all room members via WebSocket
    for (const member of members) {
      if (member.id !== agent.id) {
        const payload = {
          message_id: message.id,
          room_id: roomId,
          from: { id: agent.id, name: agent.name },
          text: reply,
          parse_mode: 'markdown',
          date: new Date().toISOString()
        };
        await db.pushUpdate(member.id, 'message', payload);
        if (wsManager) {
          wsManager.notify(member.id, { type: 'message', ...payload });
        }
      }
    }

    // Chain collaboration: if agent's reply mentions other agents, trigger them
    if (replyMentions.length > 0 && roomType === 'group') {
      console.log(`[AI] Chain: ${agent.name} mentioned ${replyMentions.length} agent(s), depth=${chainDepth + 1}`);
      // Small delay to make it feel natural
      await new Promise(r => setTimeout(r, 1000));
      await processMessage(db, wsManager, roomId, agent.id, reply, replyMentions, roomType, chainDepth + 1);
    }
  }
}

module.exports = { chatCompletion, processMessage, getConfig };

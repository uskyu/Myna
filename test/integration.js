/**
 * Integration test for hermes-hub
 * Tests: Agent CRUD, Room CRUD, Membership, Messaging, Gateway API, WebSocket
 */

const http = require('http');
const WebSocket = require('ws');

const BASE = 'http://localhost:3000';
let agent1, agent2, room1;
let passed = 0, failed = 0;

function assert(condition, msg) {
  if (condition) {
    passed++;
    console.log(`  ✓ ${msg}`);
  } else {
    failed++;
    console.log(`  ✗ ${msg}`);
  }
}

async function api(method, path, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(BASE + path, opts);
  return res.json();
}

async function cleanup() {
  // Clean up any leftover data from previous runs
  const agents = await api('GET', '/admin/agents');
  if (agents.result) {
    for (const a of agents.result) {
      if (a.id !== 'system') await api('DELETE', `/admin/agents/${a.id}`);
    }
  }
  const rooms = await api('GET', '/admin/rooms');
  if (rooms.result) {
    for (const r of rooms.result) {
      await api('DELETE', `/admin/rooms/${r.id}`);
    }
  }
}

async function testHealth() {
  console.log('\n[Health Check]');
  const data = await api('GET', '/health');
  assert(data.status === 'ok', 'Health endpoint returns ok');
}

async function testAgentCRUD() {
  console.log('\n[Agent CRUD]');
  
  // Create
  const r1 = await api('POST', '/admin/agents', { name: 'Coder', description: 'Writes code' });
  assert(r1.ok === true, 'Create agent 1');
  assert(r1.result.api_key.length === 64, 'API key is 64 chars');
  agent1 = r1.result;

  const r2 = await api('POST', '/admin/agents', { name: 'Browser', description: 'Tests UI' });
  assert(r2.ok === true, 'Create agent 2');
  agent2 = r2.result;

  // List
  const list = await api('GET', '/admin/agents');
  const nonSys = list.result.filter(a => a.id !== 'system');
  assert(nonSys.length >= 2, 'List shows at least 2 agents');

  // Validation
  const bad = await api('POST', '/admin/agents', {});
  assert(bad.ok === false, 'Reject agent without name');
}

async function testRoomCRUD() {
  console.log('\n[Room CRUD]');

  const r = await api('POST', '/admin/rooms', { name: 'dev-team', description: 'Dev collaboration' });
  assert(r.ok === true, 'Create room');
  room1 = r.result;

  const list = await api('GET', '/admin/rooms');
  assert(list.result.length >= 1, 'List shows at least 1 room');

  // Validation
  const bad = await api('POST', '/admin/rooms', {});
  assert(bad.ok === false, 'Reject room without name');
}

async function testMembership() {
  console.log('\n[Room Membership]');

  // Add members
  const a1 = await api('POST', `/admin/rooms/${room1.id}/members`, { agent_id: agent1.id });
  assert(a1.ok === true, 'Add agent1 to room');

  const a2 = await api('POST', `/admin/rooms/${room1.id}/members`, { agent_id: agent2.id });
  assert(a2.ok === true, 'Add agent2 to room');

  // Check members
  const rooms = await api('GET', '/admin/rooms');
  const room = rooms.result.find(r => r.id === room1.id);
  assert(room.members.length === 2, 'Room has 2 members');

  // Duplicate add (should be idempotent)
  const dup = await api('POST', `/admin/rooms/${room1.id}/members`, { agent_id: agent1.id });
  assert(dup.ok === true, 'Duplicate add is idempotent');
}

async function testGatewayAuth() {
  console.log('\n[Gateway Auth]');

  // Invalid key
  const bad = await api('GET', '/botinvalidkey123/getMe');
  assert(bad.ok === false, 'Reject invalid API key');

  // Valid key
  const me = await api('GET', `/bot${agent1.api_key}/getMe`);
  assert(me.ok === true, 'Valid key returns agent info');
  assert(me.result.name === 'Coder', 'getMe returns correct name');
}

async function testMessaging() {
  console.log('\n[Messaging]');

  // Send message
  const msg1 = await api('POST', `/bot${agent1.api_key}/sendMessage`, {
    room_id: room1.id,
    text: '# Hello\nThis is **bold** and `code`',
    parse_mode: 'markdown'
  });
  assert(msg1.ok === true, 'Agent1 sends message');
  assert(typeof msg1.result.id === 'number', 'Message has numeric ID');

  // Send with mention
  const msg2 = await api('POST', `/bot${agent2.api_key}/sendMessage`, {
    room_id: room1.id,
    text: '@Coder I tested the login page, looks good!',
    mentions: ['Coder']
  });
  assert(msg2.ok === true, 'Agent2 sends message with mention');

  // Reply
  const msg3 = await api('POST', `/bot${agent1.api_key}/sendMessage`, {
    room_id: room1.id,
    text: 'Thanks! Let me push the fix.',
    reply_to_message_id: msg2.result.id
  });
  assert(msg3.ok === true, 'Agent1 replies to message');
  assert(msg3.result.reply_to_message_id === msg2.result.id, 'Reply references correct message');

  // Get messages
  const msgs = await api('GET', `/bot${agent1.api_key}/getMessages?room_id=${room1.id}`);
  assert(msgs.ok === true, 'Get messages');
  assert(msgs.result.length === 3, 'Room has 3 messages');
  assert(msgs.result[0].html.includes('<strong>bold</strong>'), 'Markdown rendered to HTML');
  assert(msgs.result[0].html.includes('<code>code</code>'), 'Code rendered');

  // Non-member cannot send
  const room2 = await api('POST', '/admin/rooms', { name: 'private' });
  const denied = await api('POST', `/bot${agent1.api_key}/sendMessage`, {
    room_id: room2.result.id,
    text: 'Should fail'
  });
  assert(denied.ok === false, 'Non-member cannot send to room');
}

async function testUpdates() {
  console.log('\n[Update Queue]');

  // Agent2 should have updates from agent1's messages
  const updates = await api('POST', `/bot${agent2.api_key}/getUpdates`, { offset: 0 });
  assert(updates.ok === true, 'getUpdates works');
  assert(updates.result.length >= 1, 'Agent2 has pending updates');
  assert(updates.result[0].payload.from.name === 'Coder', 'Update shows sender name');

  // Second call should return empty (consumed)
  const updates2 = await api('POST', `/bot${agent2.api_key}/getUpdates`, { offset: 0 });
  assert(updates2.result.length === 0, 'Updates consumed after read');
}

async function testGetRooms() {
  console.log('\n[Agent Rooms]');

  const rooms = await api('GET', `/bot${agent1.api_key}/getRooms`);
  assert(rooms.ok === true, 'getRooms works');
  assert(rooms.result.length === 1, 'Agent1 is in 1 room');
  assert(rooms.result[0].name === 'dev-team', 'Room name correct');
}

async function testWebSocket() {
  console.log('\n[WebSocket]');

  return new Promise((resolve) => {
    const ws = new WebSocket(`ws://localhost:3000/ws?api_key=${agent2.api_key}`);
    let connected = false;
    let messageReceived = false;

    ws.on('open', () => {});

    ws.on('message', async (data) => {
      const msg = JSON.parse(data.toString());

      if (msg.type === 'connected') {
        connected = true;
        assert(msg.agent.name === 'Browser', 'WS connected with correct agent');

        // Now send a message from agent1 via HTTP, agent2 should get it via WS
        await api('POST', `/bot${agent1.api_key}/sendMessage`, {
          room_id: room1.id,
          text: 'WebSocket test message'
        });
      }

      if (msg.type === 'message' && msg.text === 'WebSocket test message') {
        messageReceived = true;
        assert(true, 'Agent2 received message via WebSocket');
        assert(msg.from.name === 'Coder', 'WS message has correct sender');
        ws.close();
      }
    });

    ws.on('close', () => {
      assert(connected, 'WebSocket connection established');
      assert(messageReceived, 'Real-time message delivery works');
      resolve();
    });

    // Timeout
    setTimeout(() => {
      if (!messageReceived) {
        assert(false, 'WebSocket message timeout');
        ws.close();
        resolve();
      }
    }, 3000);
  });
}

async function testBroadcast() {
  console.log('\n[Admin Broadcast]');

  const r = await api('POST', `/admin/rooms/${room1.id}/broadcast`, { text: '**System announcement**: maintenance at 3am' });
  assert(r.ok === true, 'Broadcast message sent');
}

async function testDeleteFlow() {
  console.log('\n[Delete Flow]');

  // Remove member
  const rm = await api('DELETE', `/admin/rooms/${room1.id}/members/${agent2.id}`);
  assert(rm.ok === true, 'Remove member from room');

  const rooms = await api('GET', '/admin/rooms');
  const room = rooms.result.find(r => r.id === room1.id);
  assert(room.members.length === 1, 'Room now has 1 member');

  // Delete agent
  const del = await api('DELETE', `/admin/agents/${agent2.id}`);
  assert(del.ok === true, 'Delete agent');

  const agents = await api('GET', '/admin/agents');
  // System agent may exist from broadcast, so filter it out
  const nonSystem = agents.result.filter(a => a.id !== 'system');
  assert(nonSystem.length === 1, 'Only 1 non-system agent remains');
}

async function run() {
  console.log('═══════════════════════════════════════');
  console.log('  hermes-hub Integration Tests');
  console.log('═══════════════════════════════════════');

  try {
    await cleanup();
    await testHealth();
    await testAgentCRUD();
    await testRoomCRUD();
    await testMembership();
    await testGatewayAuth();
    await testMessaging();
    await testUpdates();
    await testGetRooms();
    await testWebSocket();
    await testBroadcast();
    await testDeleteFlow();
  } catch (e) {
    console.error('\n  FATAL:', e.message);
    failed++;
  }

  console.log('\n═══════════════════════════════════════');
  console.log(`  Results: ${passed} passed, ${failed} failed`);
  console.log('═══════════════════════════════════════\n');

  process.exit(failed > 0 ? 1 : 0);
}

run();

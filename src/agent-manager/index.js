const express = require('express');
const Docker = require('dockerode');
const db = require('../db');

const router = express.Router();

// Docker client - connects to local Docker daemon
let docker;
try {
  docker = new Docker({ socketPath: '/var/run/docker.sock' });
} catch (e) {
  console.warn('[Agent Manager] Docker not available:', e.message);
}

// POST /admin/agents/:id/start - Start agent container
router.post('/agents/:id/start', async (req, res) => {
  if (!docker) {
    return res.status(503).json({ ok: false, error: 'Docker not available' });
  }

  const agent = db.getAgentById(req.params.id);
  if (!agent) {
    return res.status(404).json({ ok: false, error: 'Agent not found' });
  }

  const { image, env } = req.body;
  const containerImage = image || 'ghcr.io/nousresearch/hermes-agent:latest';

  try {
    // Build environment variables
    const hubUrl = process.env.HUB_URL || `http://host.docker.internal:${process.env.PORT || 3000}`;
    const containerEnv = [
      `HERMES_HUB_URL=${hubUrl}`,
      `HERMES_HUB_API_KEY=${agent.api_key}`,
      `HERMES_AGENT_NAME=${agent.name}`,
      ...(env || [])
    ];

    const container = await docker.createContainer({
      Image: containerImage,
      name: `hermes-hub-agent-${agent.name.toLowerCase().replace(/[^a-z0-9]/g, '-')}`,
      Env: containerEnv,
      HostConfig: {
        NetworkMode: 'host',
        RestartPolicy: { Name: 'unless-stopped' }
      },
      Labels: {
        'hermes-hub.agent-id': agent.id,
        'hermes-hub.agent-name': agent.name
      }
    });

    await container.start();
    db.updateAgentContainer(agent.id, container.id);
    db.updateAgentStatus(agent.id, 'online');

    res.json({ ok: true, result: { container_id: container.id } });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// POST /admin/agents/:id/stop - Stop agent container
router.post('/agents/:id/stop', async (req, res) => {
  if (!docker) {
    return res.status(503).json({ ok: false, error: 'Docker not available' });
  }

  const agent = db.getAgentById(req.params.id);
  if (!agent || !agent.container_id) {
    return res.status(404).json({ ok: false, error: 'Agent or container not found' });
  }

  try {
    const container = docker.getContainer(agent.container_id);
    await container.stop();
    await container.remove();
    db.updateAgentContainer(agent.id, null);
    db.updateAgentStatus(agent.id, 'offline');
    res.json({ ok: true });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// GET /admin/agents/:id/logs - Get agent container logs
router.get('/agents/:id/logs', async (req, res) => {
  if (!docker) {
    return res.status(503).json({ ok: false, error: 'Docker not available' });
  }

  const agent = db.getAgentById(req.params.id);
  if (!agent || !agent.container_id) {
    return res.status(404).json({ ok: false, error: 'Agent or container not found' });
  }

  try {
    const container = docker.getContainer(agent.container_id);
    const logs = await container.logs({
      stdout: true,
      stderr: true,
      tail: parseInt(req.query.tail) || 100,
      timestamps: true
    });
    res.type('text/plain').send(logs.toString());
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

// GET /admin/containers - List all hermes-hub containers
router.get('/containers', async (req, res) => {
  if (!docker) {
    return res.status(503).json({ ok: false, error: 'Docker not available' });
  }

  try {
    const containers = await docker.listContainers({
      all: true,
      filters: { label: ['hermes-hub.agent-id'] }
    });
    res.json({ ok: true, result: containers });
  } catch (e) {
    res.status(500).json({ ok: false, error: e.message });
  }
});

module.exports = router;

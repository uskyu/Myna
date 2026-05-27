const express = require('express');
const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

const router = express.Router();

const HERMES_HOME = process.env.HERMES_HOME || path.join(require('os').homedir(), '.hermes');
const CONFIG_PATH = path.join(HERMES_HOME, 'config.yaml');
const ENV_PATH = path.join(HERMES_HOME, '.env');

// GET /admin/config - read current config
router.get('/', (req, res) => {
  try {
    const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
    const config = yaml.load(raw);
    // Extract relevant fields
    const provider = config.model?.provider || '';
    const model = config.model?.default || '';
    const providerName = provider.replace('custom:', '');
    const providerConfig = config.providers?.[providerName] || {};
    
    // Read API key from env
    let apiKey = '';
    const keyEnv = providerConfig.key_env || '';
    if (keyEnv && fs.existsSync(ENV_PATH)) {
      const envContent = fs.readFileSync(ENV_PATH, 'utf8');
      const match = envContent.match(new RegExp(`^${keyEnv}=['"]?([^'"\n]+)`, 'm'));
      if (match) apiKey = match[1];
    }

    res.json({
      ok: true,
      result: {
        model: model,
        provider: providerName,
        base_url: providerConfig.base_url || '',
        api_key: apiKey ? '***' + apiKey.slice(-4) : '',
        has_key: !!apiKey,
        key_env: keyEnv,
        transport: providerConfig.transport || 'chat_completions'
      }
    });
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

// POST /admin/config - update config
router.post('/', (req, res) => {
  try {
    const { base_url, api_key, model, provider_name } = req.body;
    const raw = fs.readFileSync(CONFIG_PATH, 'utf8');
    const config = yaml.load(raw);

    const pName = provider_name || 'custom-provider';
    
    // Update provider
    if (!config.providers) config.providers = {};
    config.providers[pName] = {
      name: pName.toUpperCase(),
      base_url: base_url,
      key_env: pName.toUpperCase().replace(/[^A-Z0-9]/g, '_') + '_KEY',
      default_model: model || config.model?.default || '',
      transport: 'chat_completions'
    };

    // Update model section
    config.model = config.model || {};
    config.model.provider = 'custom:' + pName;
    if (model) config.model.default = model;

    // Write config
    fs.writeFileSync(CONFIG_PATH, yaml.dump(config, { lineWidth: -1 }));

    // Write API key to .env
    if (api_key && !api_key.startsWith('***')) {
      const keyEnvName = pName.toUpperCase().replace(/[^A-Z0-9]/g, '_') + '_KEY';
      let envContent = '';
      if (fs.existsSync(ENV_PATH)) {
        envContent = fs.readFileSync(ENV_PATH, 'utf8');
        // Replace or append
        const regex = new RegExp(`^${keyEnvName}=.*$`, 'm');
        if (regex.test(envContent)) {
          envContent = envContent.replace(regex, `${keyEnvName}='${api_key}'`);
        } else {
          envContent += `\n${keyEnvName}='${api_key}'`;
        }
      } else {
        envContent = `${keyEnvName}='${api_key}'`;
      }
      fs.writeFileSync(ENV_PATH, envContent.trim() + '\n');
    }

    res.json({ ok: true, message: '配置已保存' });
  } catch (e) {
    res.json({ ok: false, error: e.message });
  }
});

// POST /admin/config/models - fetch models from API
router.post('/models', async (req, res) => {
  const { base_url, api_key } = req.body;
  if (!base_url || !api_key) {
    return res.json({ ok: false, error: '请填写 API 地址和密钥' });
  }

  try {
    const url = base_url.replace(/\/$/, '') + '/models';
    const resp = await fetch(url, {
      headers: { 'Authorization': 'Bearer ' + api_key },
      signal: AbortSignal.timeout(10000)
    });
    if (!resp.ok) {
      return res.json({ ok: false, error: `HTTP ${resp.status}: ${resp.statusText}` });
    }
    const data = await resp.json();
    const models = (data.data || data.models || []).map(m => ({
      id: m.id || m.name,
      name: m.id || m.name
    }));
    res.json({ ok: true, result: models });
  } catch (e) {
    res.json({ ok: false, error: '获取失败: ' + e.message });
  }
});

module.exports = router;

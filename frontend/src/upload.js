const CHUNK_SIZE = 256 * 1024

function uploadHeaders() {
  const token = localStorage.getItem('hub_auth_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function parseResponse(response) {
  const text = await response.text().catch(() => '')
  if (!text) return { ok: false, error: response.ok ? '服务器返回空响应' : `HTTP ${response.status}` }
  try { return JSON.parse(text) }
  catch { return { ok: false, error: `HTTP ${response.status}: ${text.slice(0, 120)}` } }
}

async function postJson(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { ...uploadHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const result = await parseResponse(response)
  if (!response.ok || !result.ok) throw new Error(result.error || `HTTP ${response.status}`)
  return result
}

function bytesToBase64(buffer) {
  const bytes = new Uint8Array(buffer)
  let binary = ''
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000))
  }
  return btoa(binary)
}

async function uploadInChunks(file) {
  const uploadId = `${Date.now()}-${crypto.randomUUID?.() || Math.random().toString(36).slice(2)}`
  const total = Math.max(1, Math.ceil(file.size / CHUNK_SIZE))
  for (let index = 0; index < total; index++) {
    const buffer = await file.slice(index * CHUNK_SIZE, Math.min(file.size, (index + 1) * CHUNK_SIZE)).arrayBuffer()
    await postJson('/admin/upload/chunk', {
      upload_id: uploadId,
      index,
      total,
      size: file.size,
      name: file.name || 'file',
      content_type: file.type || 'application/octet-stream',
      data: bytesToBase64(buffer),
    })
  }
  return postJson('/admin/upload/complete', { upload_id: uploadId })
}

export async function uploadFile(file) {
  if (file.size > 200 * 1024 * 1024) throw new Error('文件不能超过 200 MB')

  // Try multipart upload first
  try {
    const form = new FormData()
    form.append('file', file, file.name || 'file')
    const response = await fetch('/admin/upload', {
      method: 'POST',
      body: form,
      credentials: 'same-origin',
      cache: 'no-store',
      headers: uploadHeaders(),
    })
    const result = await parseResponse(response)
    if (response.status === 401) throw new Error('登录已过期，请刷新后重新登录')
    if (response.ok && result.ok) return result
  } catch (error) {
    if (error?.message?.includes('登录已过期')) throw error
  }

  // Fallback: chunked JSON upload (works through proxies that block multipart)
  return uploadInChunks(file)
}

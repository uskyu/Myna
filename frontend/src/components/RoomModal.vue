<template>
  <div class="modal-overlay" @click.self="closeIfIdle">
    <div class="modal room-modal">
      <h3>创建群聊</h3>
      <input v-model="name" type="text" placeholder="群聊名称" :disabled="creating" @keydown.enter="create">
      <input v-model="desc" type="text" placeholder="描述（可选）" :disabled="creating" @keydown.enter="create">
      <p v-if="error" class="form-error">{{ error }}</p>
      <div class="btn-row">
        <button class="btn btn-cancel" :disabled="creating" @click="closeIfIdle">取消</button>
        <button class="btn btn-primary" :disabled="creating || !name.trim()" @click="create">
          {{ creating ? '创建中…' : '创建' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api, loadConversations, store } from '../store.js'

const emit = defineEmits(['close', 'created'])
const name = ref('')
const desc = ref('')
const creating = ref(false)
const error = ref('')

function closeIfIdle() {
  if (!creating.value) emit('close')
}

async function create() {
  const roomName = name.value.trim()
  if (!roomName || creating.value) return
  creating.value = true
  error.value = ''
  const data = await api('POST', '/admin/rooms', { name: roomName, description: desc.value.trim() })
  if (data.ok && data.result) {
    const room = { members: [], last_message: null, ...data.result }
    if (!store.rooms.some(r => r.id === room.id)) store.rooms = [room, ...store.rooms]
    emit('created', room)
    loadConversations()
  } else {
    error.value = data.error || '创建失败，请重试'
    creating.value = false
  }
}
</script>

<style scoped>
.room-modal input:disabled,
.room-modal button:disabled {
  cursor: not-allowed;
  opacity: 0.65;
}
.form-error {
  color: var(--danger, #c44545);
  font-size: 13px;
  line-height: 1.4;
  margin-top: -4px;
}
</style>

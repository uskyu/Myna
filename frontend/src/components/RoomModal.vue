<template>
  <div class="modal-overlay" @click.self="$emit('close')">
    <div class="modal">
      <h3>创建群聊</h3>
      <input v-model="name" type="text" placeholder="群聊名称">
      <input v-model="desc" type="text" placeholder="描述（可选）">
      <div class="btn-row">
        <button class="btn btn-cancel" @click="$emit('close')">取消</button>
        <button class="btn btn-primary" @click="create">创建</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { api, loadConversations } from '../store.js'

const emit = defineEmits(['close', 'created'])
const name = ref('')
const desc = ref('')

async function create() {
  if (!name.value.trim()) return
  const data = await api('POST', '/admin/rooms', { name: name.value, description: desc.value })
  if (data.ok) {
    await loadConversations()
    emit('created', data.result)
  }
}
</script>

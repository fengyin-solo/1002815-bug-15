<template>
  <section class="page" data-module="irrigation-detail">
    <header class="page-head">
      <div>
        <h2>灌溉任务明细</h2>
        <p class="page-desc">每次打开都从后端重新读取，刷新页面也不会再显示旧值。</p>
      </div>
      <div class="page-actions">
        <RouterLink class="btn" to="/irrigation">返回列表</RouterLink>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <table v-if="entry" class="data-table detail-table">
      <tbody>
        <tr v-for="field in fields" :key="field">
          <th>{{ field }}</th>
          <td>{{ entry[field] ?? '—' }}</td>
        </tr>
      </tbody>
    </table>

    <div v-if="entry" class="detail-actions">
      <button
        v-for="action in actions"
        :key="action"
        class="btn"
        type="button"
        @click="runAction(action)"
      >
        {{ action }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { request } from '@/api/client'

type Entry = Record<string, string | number | null>

const fields = ['灌溉编号', '灌溉区域', '灌溉方式', '用水量', '灌溉时段', '灌溉设备', '作业人员', '灌溉状态']
const actions = ['安排灌溉', '开始灌溉', '暂停灌溉']

const route = useRoute()
const entry = ref<Entry | null>(null)
const errorMessage = ref('')

async function loadEntry() {
  errorMessage.value = ''
  entry.value = null
  try {
    const response = await request(`/api/irrigation/${route.params.id}`)
    if (!response.ok) {
      const data = await response.json().catch(() => null)
      throw new Error(data?.detail ?? '灌溉明细读取失败')
    }
    entry.value = await response.json()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '灌溉明细读取失败'
  }
}

async function runAction(action: string) {
  errorMessage.value = ''
  try {
    const response = await request(`/api/irrigation/${route.params.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('灌溉作业动作未生效，请稍后重试')
    }
    // 动作完成后重新拉取，保证页面展示的就是后端最新明细
    await loadEntry()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '灌溉作业操作失败'
  }
}

onMounted(loadEntry)
</script>

<style scoped>
.detail-table {
  max-width: 720px;
}

.detail-table th {
  width: 140px;
  text-align: left;
}

.detail-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}
</style>

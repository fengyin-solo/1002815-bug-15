<template>
  <section class="page" data-module="irrigation">
    <header class="page-head">
      <div>
        <h2>灌溉作业管理</h2>
        <p class="page-desc">维护灌溉任务，围绕灌溉编号、灌溉区域、灌溉方式、用水量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
 <button class="btn primary" type="button" @click="openCreate">登记灌溉任务</button>
        <button class="btn" type="button" @click="triggerImport">导入灌溉表格</button>
        <button class="btn" type="button" @click="exportRows">导出灌溉作业清单</button>
        <input
          ref="fileInput"
          type="file"
          accept=".csv,text/csv"
          style="display: none"
          @change="onFileSelected"
        />
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>灌溉编号</span>
        <input v-model="filters.keyword" placeholder="按灌溉编号检索" />
      </label>
      <label class="filter-item">
        <span>灌溉区域</span>
        <input v-model="filters.area" placeholder="按灌溉区域检索" />
      </label>
      <label class="filter-item">
        <span>灌溉方式</span>
        <input v-model="filters.method" placeholder="按灌溉方式检索" />
      </label>
      <label class="filter-item">
        <span>灌溉状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <section v-if="importReport" class="import-report" :class="{ 'is-error': !importReport.ok }">
      <header>
        <strong>{{ importReport.ok ? '导入结果' : '导入中断' }}</strong>
        <button class="link" type="button" @click="importReport = null">关闭</button>
      </header>
      <p>{{ importReport.message }}</p>
      <ul v-if="importReport.skipped?.length">
        <li v-for="(item, idx) in importReport.skipped" :key="`skip-${idx}`">
          第 {{ item.row }} 行已退回：{{ item.reason }}
        </li>
      </ul>
      <ul v-if="importReport.warnings?.length">
        <li v-for="(item, idx) in importReport.warnings" :key="`warn-${idx}`">
          第 {{ item.row }} 行（{{ item['灌溉编号'] }}）：{{ item.reason }}
        </li>
      </ul>
      <p v-if="importReport.resume_from" class="resume-hint">
        请重新选择数据完整的表格文件，将自动从第 {{ importReport.resume_from }} 行续传。
      </p>
    </section>

    <section class="reconcile-panel">
      <header>
        <strong>班次对账（{{ store.shiftLabel }}）</strong>
        <button class="btn ghost" type="button" @click="loadReconcile">刷新对账</button>
      </header>
      <p v-if="filters.area">仅统计当前选择的灌溉区域：{{ filters.area }}</p>
      <p v-else>未限定灌溉区域时统计全部记录</p>
      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">对账水量合计</span>
          <strong class="stat-value">{{ reconcile?.total_water ?? '—' }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">已填用水量记录</span>
          <strong class="stat-value">{{ reconcile?.measured_count ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">未填用水量记录</span>
          <strong class="stat-value">{{ reconcile?.unmeasured_count ?? 0 }}</strong>
        </article>
      </div>
      <ul v-if="reconcile?.unmeasured.length" class="reconcile-missing">
        <li v-for="item in reconcile.unmeasured" :key="`um-${item.id}`">
          {{ item['灌溉编号'] }}（{{ item['灌溉区域'] || '未填区域' }}）：{{ item.reason }}
        </li>
      </ul>
    </section>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="`irrigation-${row.id}`">
          <td v-for="column in columns" :key="column">
            <RouterLink v-if="column === '灌溉编号'" :to="`/irrigation/${row.id}`">{{ row[column] ?? '—' }}</RouterLink>
            <template v-else>{{ row[column] ?? '—' }}</template>
          </td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无灌溉作业数据，可先登记灌溉任务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条灌溉作业记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>

type ImportReport = {
  ok: boolean
  message: string
  skipped?: { row: number; reason: string }[]
  warnings?: { row: number; reason: string; ['灌溉编号']?: string }[]
  resume_from?: number
  token?: string
}

type Reconcile = {
  total_water: string
  measured_count: number
  unmeasured_count: number
  unmeasured: { id: number; ['灌溉编号']: string; ['灌溉区域']: string; reason: string }[]
}

const ENDPOINT = '/api/irrigation'
const columns = ['灌溉编号', '灌溉区域', '灌溉方式', '用水量', '灌溉时段', '灌溉设备', '作业人员', '灌溉状态']
const actions = ['安排灌溉', '开始灌溉', '暂停灌溉']
const statuses = ['待灌溉', '灌溉中', '已完成', '已暂停']
const stats = [
  { label: '待灌溉区域', value: 0 },
  { label: '灌溉中区域', value: 0 },
  { label: '已完成灌溉', value: 0 },
]

const store = useSessionStore()
const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({ keyword: '', area: '', method: '', status: '' })
const fileInput = ref<HTMLInputElement | null>(null)
const importReport = ref<ImportReport | null>(null)
const reconcile = ref<Reconcile | null>(null)
// 断点续传上下文：服务端已收到第 resumeFrom-1 行之前的数据
let pendingResume: { token: string; resumeFrom: number } | null = null

function buildQuery(): string {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters.value)) {
    if (value) params.set(key, value)
  }
  const query = params.toString()
  return query ? `?${query}` : ''
}

function resetFilters() {
  filters.value = { keyword: '', area: '', method: '', status: '' }
  void reload()
}

function exportRows() {
  // 导出严格按当前筛选条件（含灌溉区域），列由后端保证完整
  window.open(`${ENDPOINT}/export${buildQuery()}`, '_blank')
}

function triggerImport() {
  fileInput.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  const content = await file.text()
  // 批次编号取文件名（去掉扩展名）：同一份表格重复导入只生效一次
  const sheet = file.name.replace(/\.[^.]+$/, '')
  const payload: Record<string, unknown> = { content, sheet }
  if (pendingResume) {
    payload.token = pendingResume.token
    payload.resume_from = pendingResume.resumeFrom
  }
  try {
    const response = await request(`${ENDPOINT}/import`, {
      method: 'POST',
      body: JSON.stringify(payload),
    })
    const data = (await response.json()) as ImportReport & { repeated?: boolean }
    if (data.repeated) {
      data.message = '该批次已导入过，本次未重复入库。'
    }
    importReport.value = data
    if (data.ok) {
      pendingResume = null
    } else if (data.resume_from && data.token) {
      // 后面的数据取不到：下次选文件时从断掉的那一行接着走
      pendingResume = { token: data.token, resumeFrom: data.resume_from }
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '灌溉表格导入失败'
  }
}

function openCreate() {
  errorMessage.value = '灌溉任务登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('灌溉作业动作未生效，请稍后重试')
    }
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '灌溉作业操作失败'
  }
}

async function loadReconcile() {
  try {
    const query = filters.value.area ? `?area=${encodeURIComponent(filters.value.area)}` : ''
    const response = await request(`${ENDPOINT}/reconcile${query}`)
    if (!response.ok) {
      throw new Error('班次对账读取失败')
    }
    reconcile.value = (await response.json()) as Reconcile
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '班次对账读取失败'
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}${buildQuery()}`)
    if (!response.ok) {
      throw new Error('灌溉任务列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await loadReconcile()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '灌溉作业列表读取失败'
  }
}

onMounted(reload)
</script>

<style scoped>
.import-report,
.reconcile-panel {
  border: 1px solid #d9e2ec;
  border-radius: 8px;
  padding: 12px 16px;
  margin: 12px 0;
  background: #f8fafc;
}

.import-report.is-error {
  border-color: #e0a458;
  background: #fff7ed;
}

.import-report header,
.reconcile-panel header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.import-report ul,
.reconcile-missing {
  margin: 8px 0 0;
  padding-left: 20px;
}

.resume-hint {
  color: #b45309;
}
</style>

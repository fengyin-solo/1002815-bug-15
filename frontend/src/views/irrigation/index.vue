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
          class="file-input"
          @change="pickFile"
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
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="importSummary || importRejected.length" class="import-panel">
      <p v-if="importSummary" class="import-summary">{{ importSummary }}</p>
      <ul v-if="importRejected.length" class="rejected-list">
        <li v-for="item in importRejected" :key="item.row">第 {{ item.row }} 行：{{ item.reason }}</li>
      </ul>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in visibleRows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
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
        <tr v-if="!visibleRows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无灌溉作业数据，可先登记灌溉任务</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条灌溉作业记录，已加载 {{ rows.length }} 条</span>
      <button v-if="loadBroken" class="link" type="button" :disabled="loading" @click="resumeLoad">
        从第 {{ rows.length + 1 }} 行继续加载
      </button>
      <button v-if="importBroken" class="link" type="button" :disabled="importing" @click="resumeImport">
        从第 {{ importOffset + 1 }} 行继续导入
      </button>
      <span v-if="loading">读取中…</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="detail" class="detail-mask" @click.self="closeDetail">
      <section class="detail-panel">
        <header class="detail-head">
          <h3>灌溉任务详情</h3>
          <div>
            <button class="btn ghost" type="button" :disabled="detailLoading" @click="refreshDetail()">刷新</button>
            <button class="btn ghost" type="button" @click="closeDetail">关闭</button>
          </div>
        </header>
        <p v-if="detailError" class="error-text">{{ detailError }}</p>
        <p v-if="detailLoading" class="detail-loading">正在读取最新明细…</p>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detail[column] ?? '—' }}</dd>
          </template>
        </dl>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type RejectedRow = { row: number; reason: string }

const ENDPOINT = '/api/irrigation'
const columns = ["灌溉编号", "灌溉区域", "灌溉方式", "用水量", "灌溉时段", "灌溉设备", "作业人员", "灌溉状态"]
const actions = ["安排灌溉", "开始灌溉", "暂停灌溉"]
const statuses = ["待灌溉", "灌溉中", "已完成", "已暂停"]
const stats = [{"label": "待灌溉区域", "value": 0}, {"label": "灌溉中区域", "value": 0}, {"label": "已完成灌溉", "value": 0}]
const PAGE_SIZE = 50
const IMPORT_CHUNK = 10

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const loading = ref(false)
const loadBroken = ref(false)
const filters = ref<Record<string, string>>({})
const filterFields = ["灌溉编号", "灌溉区域", "灌溉方式"]

const fileInput = ref<HTMLInputElement | null>(null)
const importTable = ref<string[][]>([])
const importOffset = ref(0)
const importCreated = ref(0)
const importUpdated = ref(0)
const importRejected = ref<RejectedRow[]>([])
const importSummary = ref('')
const importing = ref(false)
const importBroken = ref(false)

const detail = ref<Row | null>(null)
const detailLoading = ref(false)
const detailError = ref('')

// 灌溉方式后端没有专门参数，已加载的行在前端过滤；编号与区域走后端，导出跟随同一口径。
const visibleRows = computed(() => {
  const method = (filters.value['灌溉方式'] || '').trim()
  if (!method) return rows.value
  return rows.value.filter((row) => String(row['灌溉方式'] ?? '').includes(method))
})

function listQuery(): URLSearchParams {
  const params = new URLSearchParams()
  const keyword = (filters.value['灌溉编号'] || '').trim()
  const area = (filters.value['灌溉区域'] || '').trim()
  if (keyword) params.set('keyword', keyword)
  if (area) params.set('area', area)
  return params
}

function reload() {
  void loadAll(false)
}

function resumeLoad() {
  void loadAll(true)
}

function resetFilters() {
  filters.value = {}
  reload()
}

async function loadAll(resume: boolean) {
  if (!resume) {
    rows.value = []
    total.value = 0
  }
  loading.value = true
  loadBroken.value = false
  errorMessage.value = ''
  // 断点续传：已加载的行保持不动，从断掉的那一页接着取
  let page = Math.floor(rows.value.length / PAGE_SIZE) + 1
  try {
    while (true) {
      const params = listQuery()
      params.set('page', String(page))
      params.set('size', String(PAGE_SIZE))
      const response = await request(`${ENDPOINT}?${params}`)
      if (!response.ok) {
        throw new Error(`第 ${page} 页读取失败（HTTP ${response.status}）`)
      }
      const payload = await response.json()
      const items: Row[] = payload.items ?? []
      rows.value = rows.value.concat(items)
      total.value = payload.total ?? rows.value.length
      if (items.length < PAGE_SIZE || rows.value.length >= total.value) {
        break
      }
      page += 1
    }
  } catch (error) {
    loadBroken.value = true
    const detailText = error instanceof Error ? error.message : '列表读取失败'
    errorMessage.value = `${detailText}；已保留前 ${rows.value.length} 行，可从第 ${rows.value.length + 1} 行接着加载`
  } finally {
    loading.value = false
  }
}

function exportRows() {
  const params = listQuery()
  const query = params.toString()
  window.open(`${ENDPOINT}/export${query ? `?${query}` : ''}`, '_blank')
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
    const result = await response.json()
    if (!response.ok || !result.ok) {
      throw new Error(result.message || '灌溉作业动作未生效，请稍后重试')
    }
    await loadAll(false)
    if (detail.value && detail.value.id === row.id) {
      await refreshDetail()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '灌溉作业操作失败'
  }
}

async function openDetail(row: Row) {
  detail.value = row
  await refreshDetail(row.id)
}

async function refreshDetail(id?: string | number | null) {
  const targetId = id ?? detail.value?.id
  if (targetId === undefined || targetId === null) return
  detailLoading.value = true
  detailError.value = ''
  try {
    // 每次打开/刷新都回源取数，不沿用旧值
    const response = await request(`${ENDPOINT}/${targetId}`, { cache: 'no-store' })
    if (!response.ok) {
      throw new Error(`明细读取失败（HTTP ${response.status}）`)
    }
    detail.value = (await response.json()) as Row
  } catch (error) {
    detailError.value = error instanceof Error ? error.message : '明细读取失败'
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  detail.value = null
  detailError.value = ''
}

function triggerImport() {
  fileInput.value?.click()
}

function parseCsv(text: string): string[][] {
  const table: string[][] = []
  let cell = ''
  let row: string[] = []
  let inQuotes = false
  const pushCell = () => {
    row.push(cell)
    cell = ''
  }
  const pushRow = () => {
    pushCell()
    table.push(row)
    row = []
  }
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i]
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') {
          cell += '"'
          i += 1
        } else {
          inQuotes = false
        }
      } else {
        cell += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      pushCell()
    } else if (ch === '\n') {
      pushRow()
    } else if (ch !== '\r') {
      cell += ch
    }
  }
  pushRow()
  // 只去掉文件末尾的空行伪影，中间真正的空行保留给后端按行号退回
  while (table.length && table[table.length - 1].every((c) => c.trim() === '')) {
    table.pop()
  }
  return table
}

async function pickFile(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  errorMessage.value = ''
  importSummary.value = ''
  importRejected.value = []
  try {
    const table = parseCsv(await file.text())
    if (table.length < 1 || table[0].every((c) => c.trim() === '')) {
      throw new Error('表格为空或缺少表头')
    }
    importTable.value = table
    importOffset.value = 0
    importCreated.value = 0
    importUpdated.value = 0
    importBroken.value = false
    await runImport()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '灌溉表格读取失败'
  }
}

function resumeImport() {
  void runImport()
}

async function runImport() {
  const table = importTable.value
  if (!table.length) return
  const headers = table[0]
  const dataRows = table.slice(1)
  importing.value = true
  importBroken.value = false
  errorMessage.value = ''
  try {
    // 分块入库：取不到后面的数据时停在断点，重新继续时从断掉的那一行接着走
    while (importOffset.value < dataRows.length) {
      const chunk = dataRows.slice(importOffset.value, importOffset.value + IMPORT_CHUNK)
      const response = await request(`${ENDPOINT}/import`, {
        method: 'POST',
        body: JSON.stringify({ columns: headers, rows: chunk, offset: importOffset.value }),
      })
      const result = await response.json()
      if (!response.ok || !result.ok) {
        throw new Error(result.message || `第 ${importOffset.value + 1} 行起导入被拒`)
      }
      importCreated.value += result.created ?? 0
      importUpdated.value += result.updated ?? 0
      importRejected.value = importRejected.value.concat(result.rejected ?? [])
      importOffset.value += chunk.length
    }
    importSummary.value = `导入完成：新增 ${importCreated.value} 条，按灌溉编号合并更新 ${importUpdated.value} 条，退回 ${importRejected.value.length} 行`
    await loadAll(false)
  } catch (error) {
    importBroken.value = true
    const detailText = error instanceof Error ? error.message : '导入失败'
    errorMessage.value = `${detailText}；已入库 ${importOffset.value} 行，可从第 ${importOffset.value + 1} 行接着导入`
    importSummary.value = ''
  } finally {
    importing.value = false
  }
}

onMounted(() => reload())
</script>

<style scoped>
.file-input {
  display: none;
}
.import-panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.import-summary {
  margin: 0 0 4px;
}
.rejected-list {
  margin: 0;
  padding-left: 18px;
  color: #b42318;
}
.detail-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.35);
  display: flex;
  justify-content: flex-end;
  z-index: 10;
}
.detail-panel {
  width: 360px;
  background: #fff;
  padding: 16px;
  overflow-y: auto;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.detail-head h3 {
  margin: 0;
  font-size: 15px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 8px 12px;
  font-size: 13px;
}
.detail-loading {
  color: var(--muted);
  font-size: 12px;
}
.detail-grid dt {
  color: var(--muted);
}
.detail-grid dd {
  margin: 0;
}
</style>

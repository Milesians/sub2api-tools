<script setup lang="ts">
import { computed, ref } from 'vue'
import { buildReport, diagnoseEndpoint, type DiagnoseProgressEvent } from '../../diagnose/runner'
import { getEntrypoints, resultLabel, submitLGReport, type EntrypointSnapshot } from '../../api/lg'
import type { EndpointResult, EntryPoint } from '../../types'

type RunStatus = 'idle' | 'running' | 'done' | 'failed'

interface EndpointState {
  status: RunStatus
  current: string
  logs: string[]
  samples: DiagnoseProgressEvent[]
  result?: EndpointResult
}

const loading = ref(false)
const running = ref(false)
const error = ref('')
const snapshot = ref<EntrypointSnapshot | null>(null)
const selectedIds = ref<string[]>([])
const states = ref<Record<string, EndpointState>>({})
const results = ref<EndpointResult[]>([])
const reportId = ref('')

const entrypoints = computed(() => snapshot.value?.entrypoints || [])
const selectedEndpoints = computed(() => entrypoints.value.filter((endpoint) => selectedIds.value.includes(endpoint.id)))
const canRun = computed(() => Boolean(snapshot.value?.probe && selectedEndpoints.value.length > 0 && !running.value))

loadEntrypoints()

async function loadEntrypoints() {
  loading.value = true
  error.value = ''
  try {
    snapshot.value = await getEntrypoints()
    selectedIds.value = entrypoints.value.map((endpoint) => endpoint.id)
    states.value = {}
    results.value = []
    reportId.value = ''
  } catch (e) {
    error.value = e instanceof Error ? e.message : '读取入口失败'
  } finally {
    loading.value = false
  }
}

async function runDiagnostics() {
  if (!snapshot.value || !canRun.value) return
  running.value = true
  error.value = ''
  results.value = []
  reportId.value = ''
  const runID = `run_${crypto.randomUUID()}`
  try {
    for (const endpoint of selectedEndpoints.value) {
      states.value[endpoint.id] = blankState('待开始')
    }
    for (const endpoint of selectedEndpoints.value) {
      patchState(endpoint.id, { status: 'running', current: '准备测试', logs: ['准备测试'] })
      try {
        const result = await diagnoseEndpoint(endpoint, snapshot.value.probe, runID, (event) => recordProgress(event))
        results.value.push(result)
        patchState(endpoint.id, {
          status: 'done',
          current: '完成',
          result,
          logs: [`完成：${resultLabel(result)}`, ...states.value[endpoint.id].logs].slice(0, 10)
        })
      } catch (e) {
        patchState(endpoint.id, {
          status: 'failed',
          current: '失败',
          logs: [`失败：${e instanceof Error ? e.message : String(e)}`, ...states.value[endpoint.id].logs].slice(0, 10)
        })
      }
    }
    if (!results.value.length) throw new Error('没有入口完成测试')
    const saved = await submitLGReport(buildReport(runID, allSamples(), endpointLabels()))
    reportId.value = saved.report_id
  } catch (e) {
    error.value = e instanceof Error ? e.message : '诊断失败'
  } finally {
    running.value = false
  }
}

function toggleEndpoint(id: string) {
  if (running.value) return
  selectedIds.value = selectedIds.value.includes(id)
    ? selectedIds.value.filter((item) => item !== id)
    : [...selectedIds.value, id]
}

function recordProgress(event: DiagnoseProgressEvent) {
  const id = event.endpoint_id
  const prev = states.value[id] || blankState()
  const line = `${event.label}${event.ok ? '' : ' 失败'}${event.duration_ms != null ? ` ${event.duration_ms}ms` : ''}`
  states.value[id] = {
    ...prev,
    status: 'running',
    current: event.label,
    samples: [...prev.samples, event],
    logs: [line, ...prev.logs].slice(0, 10)
  }
}

function patchState(id: string, patch: Partial<EndpointState>) {
  states.value[id] = { ...(states.value[id] || blankState()), ...patch }
}

function blankState(current = ''): EndpointState {
  return { status: 'idle', current, logs: [], samples: [] }
}

function allSamples() {
  return Object.values(states.value).flatMap((state) => state.samples)
}

function endpointLabels() {
  return Object.fromEntries(entrypoints.value.map((endpoint) => [endpoint.endpoint_public_id || endpoint.id, endpoint.name]))
}

function stateFor(endpoint: EntryPoint) {
  return states.value[endpoint.id] || blankState()
}
</script>

<template>
  <section class="panel lg-view">
    <div class="lg-head">
      <div>
        <h1>网络诊断</h1>
        <div class="muted">选择入口后运行浏览器侧诊断，报告仅保留在当前后端进程内存中</div>
      </div>
      <div class="actions">
        <button type="button" :disabled="loading || running" @click="loadEntrypoints">刷新入口</button>
        <button type="button" :disabled="!canRun" @click="runDiagnostics">{{ running ? '诊断中' : '开始诊断' }}</button>
      </div>
    </div>

    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="reportId" class="success">报告已生成：{{ reportId }}</div>
    <div v-if="loading" class="muted">读取中...</div>

    <div v-if="entrypoints.length" class="entry-list">
      <article
        v-for="entry in entrypoints"
        :key="entry.id"
        class="entry"
        :class="{ selected: selectedIds.includes(entry.id) }"
      >
        <label>
          <input type="checkbox" :checked="selectedIds.includes(entry.id)" :disabled="running" @change="toggleEndpoint(entry.id)" />
          <span class="entry-name">{{ entry.name }}</span>
        </label>
        <div class="muted">{{ entry.base_url }}</div>
        <div class="probe">{{ entry.probe_base_url }}</div>
        <div class="status-row">
          <strong>{{ stateFor(entry).current || '待测试' }}</strong>
          <span v-if="stateFor(entry).result">{{ resultLabel(stateFor(entry).result!) }}</span>
        </div>
        <ul v-if="stateFor(entry).logs.length" class="logs">
          <li v-for="line in stateFor(entry).logs" :key="line">{{ line }}</li>
        </ul>
      </article>
    </div>
    <div v-else-if="!loading" class="muted">暂无入口</div>

    <div v-if="results.length" class="result-grid">
      <div v-for="result in results" :key="result.endpoint_id" class="result">
        <div class="result-title">{{ result.name }}</div>
        <div>等级：{{ result.level }}</div>
        <div>成功率：{{ Math.round(result.browser.success_rate * 100) }}%</div>
        <div>P95：{{ result.browser.p95_duration_ms ?? '-' }}ms</div>
        <div>下载：{{ result.browser.download_mbps ?? '-' }} Mbps</div>
        <div>上传：{{ result.browser.upload_mbps ?? '-' }} Mbps</div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.lg-view {
  overflow-x: auto;
}

.lg-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 16px;
}

h1 {
  margin: 0 0 4px;
  font-size: 20px;
}

.actions {
  display: flex;
  gap: 8px;
}

button {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: #fff;
  padding: 7px 10px;
  cursor: pointer;
}

button:disabled {
  cursor: not-allowed;
  opacity: 0.55;
}

.success {
  margin-bottom: 12px;
  color: #16835a;
}

.entry-list {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 12px;
}

.entry {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: #fff;
}

.entry.selected {
  border-color: var(--accent);
}

.entry label {
  display: flex;
  gap: 8px;
  align-items: center;
}

.entry-name,
.result-title {
  font-weight: 700;
}

.probe {
  margin-top: 4px;
  color: #475467;
  overflow-wrap: anywhere;
  font-size: 12px;
}

.status-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 10px;
}

.logs {
  margin: 10px 0 0;
  padding-left: 18px;
  color: #475467;
  font-size: 12px;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.result {
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px;
  background: #fbfcfd;
}
</style>

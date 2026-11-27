<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-input v-model="q.usercode" :placeholder="t('syslog.usercode')" clearable style="width:180px" @keyup.enter="loadData" />
        <el-input v-model="q.username" :placeholder="t('syslog.username')" clearable style="width:180px" @keyup.enter="loadData" />
        <el-date-picker
          v-model="dateRange" type="daterange" :range-separator="t('syslog.to')"
          :start-placeholder="t('syslog.from')" :end-placeholder="t('syslog.end')"
          value-format="YYYY-MM-DD" style="width:260px"
        />
        <el-select v-model="q.success" style="width:120px" clearable :placeholder="t('syslog.result')">
          <el-option :label="t('syslog.success')" :value="1" />
          <el-option :label="t('syslog.failed')" :value="0" />
        </el-select>
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button @click="reset"><el-icon><RefreshRight /></el-icon> {{ t('common.reset') }}</el-button>
        <el-button @click="saveCondition"><el-icon><Select /></el-icon> {{ t('syslog.saveCondition') }}</el-button>
        <el-button @click="loadCondition"><el-icon><FolderOpened /></el-icon> {{ t('syslog.loadCondition') }}</el-button>
        <el-button @click="exportCsv"><el-icon><Download /></el-icon> {{ t('syslog.export') }}</el-button>
      </div>

      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%">
          <el-table-column prop="seq" :label="t('syslog.seq')" width="70" align="center" />
          <el-table-column prop="usercode" :label="t('syslog.usercode')" min-width="120" sortable />
          <el-table-column prop="username" :label="t('syslog.username')" min-width="200" show-overflow-tooltip sortable />
          <el-table-column prop="terminal" :label="t('syslog.terminal')" min-width="110" sortable />
          <el-table-column prop="product" :label="t('syslog.product')" min-width="90" />
          <el-table-column prop="device" :label="t('syslog.device')" min-width="160" show-overflow-tooltip />
          <el-table-column prop="success" :label="t('syslog.successLabel')" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="row.success === 1 ? 'success' : 'danger'" size="small">
                {{ row.success === 1 ? t('syslog.yes') : t('syslog.no') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="client_ip" :label="t('syslog.clientIp')" min-width="140" sortable />
          <el-table-column prop="cost" :label="t('syslog.cost')" width="100" align="right" />
          <el-table-column prop="log_time" :label="t('syslog.logTime')" min-width="170" sortable />
          <el-table-column prop="remark" :label="t('syslog.remark')" min-width="160" show-overflow-tooltip />
        </el-table>
      </div>

      <div class="pager">
        <el-pagination
          v-model:current-page="page" v-model:page-size="pageSize"
          :total="total" :page-sizes="[20, 50, 100, 200]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadData" @current-change="loadData"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Search, RefreshRight, Select, FolderOpened, Download } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const COND_KEY = 'ops_sys_log_condition'
const q = ref({ usercode: '', username: '', success: null })
const dateRange = ref([])
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const rows = ref([])
const loading = ref(false)

function params() {
  const p = {
    usercode: q.value.usercode || undefined,
    username: q.value.username || undefined,
    success: q.value.success,
    date_from: dateRange.value?.[0] || '',
    date_to: dateRange.value?.[1] || '',
    page: page.value,
    page_size: pageSize.value,
  }
  return p
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/system/login-logs', { params: params() })
    rows.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

function reset() {
  q.value = { usercode: '', username: '', success: null }
  dateRange.value = []
  page.value = 1
  loadData()
}

function saveCondition() {
  localStorage.setItem(COND_KEY, JSON.stringify({ q: q.value, dateRange: dateRange.value }))
  ElMessage.success(t('syslog.conditionSaved'))
}
function loadCondition() {
  const raw = localStorage.getItem(COND_KEY)
  if (!raw) { ElMessage.warning(t('syslog.noCondition')); return }
  try {
    const o = JSON.parse(raw)
    q.value = o.q || q.value
    dateRange.value = o.dateRange || []
    page.value = 1
    loadData()
  } catch (e) { ElMessage.warning(t('syslog.badCondition')) }
}

function exportCsv() {
  const header = [t('syslog.seq'), t('syslog.usercode'), t('syslog.username'), t('syslog.terminal'),
    t('syslog.product'), t('syslog.device'), t('syslog.successLabel'), t('syslog.clientIp'),
    t('syslog.cost'), t('syslog.logTime'), t('syslog.remark')]
  const lines = rows.value.map((r) => [
    r.seq, r.usercode, r.username, r.terminal, r.product, r.device,
    r.success === 1 ? t('syslog.yes') : t('syslog.no'), r.client_ip, r.cost, r.log_time, r.remark,
  ].map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','))
  const csv = '\uFEFF' + [header.join(','), ...lines].join('\r\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  a.download = 'login_log.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(loadData)
</script>

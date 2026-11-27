<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-input v-model="q.usercode" :placeholder="t('syslog.usercode')" clearable style="width:180px" @keyup.enter="loadData" />
        <el-input v-model="q.username" :placeholder="t('syslog.username')" clearable style="width:180px" @keyup.enter="loadData" />
        <el-select v-model="q.minutes" style="width:150px">
          <el-option :label="t('online.window30')" :value="30" />
          <el-option :label="t('online.window60')" :value="60" />
          <el-option :label="t('online.window120')" :value="120" />
          <el-option :label="t('online.window240')" :value="240" />
        </el-select>
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button @click="reset"><el-icon><RefreshRight /></el-icon> {{ t('common.reset') }}</el-button>
        <el-button type="danger" plain :disabled="!selected.length" @click="kickSelected">
          <el-icon><SwitchButton /></el-icon> {{ t('online.kick') }}
        </el-button>
        <el-button @click="exportCsv"><el-icon><Download /></el-icon> {{ t('syslog.export') }}</el-button>
        <el-button @click="saveCondition"><el-icon><Select /></el-icon> {{ t('syslog.saveCondition') }}</el-button>
        <el-button @click="loadCondition"><el-icon><FolderOpened /></el-icon> {{ t('syslog.loadCondition') }}</el-button>
      </div>

      <div class="tip-line">
        {{ t('online.tip') }} <b>{{ q.minutes }}</b> {{ t('online.minutes') }} · {{ t('online.total') }} <b>{{ total }}</b>
      </div>

      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%" @selection-change="onSelect">
          <el-table-column type="selection" width="46" />
          <el-table-column prop="seq" :label="t('syslog.seq')" width="70" align="center" />
          <el-table-column prop="usercode" :label="t('syslog.usercode')" min-width="120" sortable />
          <el-table-column prop="username" :label="t('syslog.username')" min-width="200" show-overflow-tooltip sortable />
          <el-table-column prop="terminal" :label="t('syslog.terminal')" min-width="110" sortable />
          <el-table-column prop="postname" :label="t('online.post')" min-width="180" show-overflow-tooltip sortable />
          <el-table-column prop="deptname" :label="t('online.dept')" min-width="160" show-overflow-tooltip sortable />
          <el-table-column prop="client_ip" :label="t('syslog.clientIp')" min-width="140" sortable />
          <el-table-column prop="login_time" :label="t('online.loginTime')" min-width="170" sortable />
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, RefreshRight, Select, FolderOpened, Download, SwitchButton } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const COND_KEY = 'ops_online_condition'
const q = ref({ usercode: '', username: '', minutes: 120 })
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const rows = ref([])
const selected = ref([])
const loading = ref(false)

function params() {
  return {
    usercode: q.value.usercode || undefined,
    username: q.value.username || undefined,
    minutes: q.value.minutes,
    page: page.value,
    page_size: pageSize.value,
  }
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/system/online-users', { params: params() })
    rows.value = res.items || []
    total.value = res.total || 0
    selected.value = []
  } finally { loading.value = false }
}

function reset() {
  q.value = { usercode: '', username: '', minutes: 120 }
  page.value = 1
  loadData()
}

function onSelect(val) { selected.value = val }

async function kickSelected() {
  const names = selected.value.map((r) => r.usercode).join(', ')
  await ElMessageBox.confirm(t('online.kickConfirm', { users: names }), t('online.kick'), { type: 'warning' })
  for (const r of selected.value) {
    await api.post('/system/online-users/kick', { usercode: r.usercode, remark: t('online.kickRemark') })
  }
  ElMessage.success(t('online.kicked'))
  loadData()
}

function saveCondition() {
  localStorage.setItem(COND_KEY, JSON.stringify(q.value))
  ElMessage.success(t('syslog.conditionSaved'))
}
function loadCondition() {
  const raw = localStorage.getItem(COND_KEY)
  if (!raw) { ElMessage.warning(t('syslog.noCondition')); return }
  try {
    q.value = { ...q.value, ...JSON.parse(raw) }
    page.value = 1
    loadData()
  } catch (e) { ElMessage.warning(t('syslog.badCondition')) }
}

function exportCsv() {
  const header = [t('syslog.seq'), t('syslog.usercode'), t('syslog.username'), t('syslog.terminal'),
    t('online.post'), t('online.dept'), t('syslog.clientIp'), t('online.loginTime')]
  const lines = rows.value.map((r) => [r.seq, r.usercode, r.username, r.terminal,
    r.postname, r.deptname, r.client_ip, r.login_time]
    .map((v) => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','))
  const csv = '\uFEFF' + [header.join(','), ...lines].join('\r\n')
  const a = document.createElement('a')
  a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }))
  a.download = 'online_users.csv'
  a.click()
  URL.revokeObjectURL(a.href)
}

onMounted(loadData)
</script>

<style scoped>
.tip-line { color: #606266; font-size: 13px; margin: 0 0 10px; }
.tip-line b { color: #409eff; }
</style>

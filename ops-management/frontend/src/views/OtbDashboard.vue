<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-select v-model="fiscalYear" style="width:140px">
          <el-option label="FY2027" value="FY2027" />
          <el-option label="FY2026" value="FY2026" />
        </el-select>
        <el-button type="primary" @click="loadAll"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button type="success" @click="openHeader"><el-icon><Edit /></el-icon> {{ t('otb.dash.editHeader') }}</el-button>
        <el-button type="warning" @click="triggerCalc" :loading="calcLoading"><el-icon><Cpu /></el-icon> {{ t('otb.dash.runCalc') }}</el-button>
        <el-button @click="openImport"><el-icon><Upload /></el-icon> {{ t('otb.dash.importDraft') }}</el-button>
        <el-button @click="runValidate"><el-icon><CircleCheck /></el-icon> {{ t('otb.dash.validate') }}</el-button>
      </div>

      <!-- KPI 卡片 -->
      <el-row :gutter="16" v-if="dash.otb_header">
        <el-col :span="6">
          <el-card shadow="never" class="kpi-card">
            <div class="kpi-label">{{ t('otb.dash.otbCost') }}</div>
            <div class="kpi-value">{{ fmtMoney(dash.otb_header.otb_cost) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="kpi-card">
            <div class="kpi-label">{{ t('otb.dash.planSalesRetail') }}</div>
            <div class="kpi-value">{{ fmtMoney(dash.otb_header.planned_sales_total_retail) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="kpi-card">
            <div class="kpi-label">{{ t('otb.dash.openingStock') }}</div>
            <div class="kpi-value">{{ fmtMoney(dash.otb_header.opening_stock_cost) }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="never" class="kpi-card">
            <div class="kpi-label">{{ t('otb.dash.toOrderItems') }}</div>
            <div class="kpi-value">{{ dash.items?.to_order || 0 }} <span class="kpi-sub">/ {{ dash.items?.total || 0 }}</span></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- 12 个月拆解：Excel 风格转置表（月份作列、指标作行） -->
      <div class="section-title">{{ t('otb.dash.pivotTitle') }}</div>
      <div class="table-flex" style="height:460px">
        <el-table :data="pivotRows" v-loading="loading" border size="small" height="100%"
          :row-class-name="pivotRowClass">
          <el-table-column prop="label" label="Remarks" width="170" fixed />
          <el-table-column v-for="(col, idx) in pivotColumns" :key="col" :label="col"
            :min-width="col === 'FY2027' ? 140 : 120" align="right">
            <template #default="{ row }">
              <span :class="{ 'cell-emphasis': row.emphasis, 'fy-total': col === 'FY2027' }">
                {{ cellText(row.values[idx]) }}
              </span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="calcResult" class="calc-summary">
        <el-alert v-if="calcResult.summary.check_budget && calcResult.summary.check_funds" type="success"
          :closable="false" :title="t('otb.dash.calcOk')" />
        <el-alert v-else type="warning" :closable="false"
          :title="t('otb.dash.calcWarn')" />
      </div>
    </div>

    <!-- 主参数编辑 -->
    <el-dialog v-model="headerVisible" :title="t('otb.dash.headerTitle')" width="640px" destroy-on-close>
      <el-form :model="form" label-width="180px">
        <el-form-item :label="t('otb.dash.fiscalYear')"><el-input v-model="form.fiscal_year" /></el-form-item>
        <el-form-item :label="t('otb.dash.businessUnit')"><el-input v-model="form.bu_code" /></el-form-item>
        <el-form-item label="Opening Stock Cost"><el-input-number v-model="form.opening_stock_cost" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item :label="t('otb.dash.planCost')"><el-input-number v-model="form.planned_sales_cost" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item :label="t('otb.dash.planTotal')"><el-input-number v-model="form.planned_sales_total_retail" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="Planned Markdown Cost"><el-input-number v-model="form.planned_markdown_cost" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="Good In-Transit Cost"><el-input-number v-model="form.good_in_transit_cost" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="Stock Cover (Months)"><el-input-number v-model="form.stock_cover_months" :min="1" :max="24" /></el-form-item>
        <el-form-item label="GP%"><el-input-number v-model="form.gp_pct" :precision="4" :min="0" :max="1" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="headerVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveHeader" :loading="saving">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- Excel 导入 -->
    <el-dialog v-model="importVisible" :title="t('otb.dash.importTitle')" width="520px" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom:16px"
        :title="t('otb.dash.importTip')" />
      <el-upload ref="uploadRef" :auto-upload="false" :limit="1" accept=".xlsx,.xlsm"
        :on-change="onFileChange" drag>
        <el-icon style="font-size:40px;color:#409eff"><UploadFilled /></el-icon>
        <div>{{ t('otb.dash.dropExcel') }} <em>{{ t('bu.def.pickFile') }}</em></div>
      </el-upload>
      <template #footer>
        <el-button @click="importVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="doImport" :loading="importing">{{ t('bu.def.startImport') }}</el-button>
      </template>
    </el-dialog>

    <!-- 校验结果 -->
    <el-dialog v-model="validateVisible" :title="t('otb.dash.validateTitle')" width="600px">
      <el-table :data="validateResult.checks || []" border size="small">
        <el-table-column prop="item" :label="t('otb.dash.checkItem')" min-width="180" />
        <el-table-column prop="valid" :label="t('otb.dash.result')" width="90">
          <template #default="{ row }"><el-tag :type="row.valid ? 'success' : 'danger'">{{ row.valid ? t('otb.dash.pass') : t('otb.dash.fail') }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="sale_mix_total" :label="t('otb.dash.mixTotal')" width="120">
          <template #default="{ row }">{{ row.sale_mix_total != null ? (row.sale_mix_total*100).toFixed(2)+'%' : '-' }}</template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const { t } = useI18n()
const fiscalYear = ref('FY2027')
const loading = ref(false)
const calcLoading = ref(false)
const saving = ref(false)
const importing = ref(false)
const monthly = ref([])
const pivotColumns = ref([])
const pivotRows = ref([])
const dash = ref({})
const calcResult = ref(null)
const headerVisible = ref(false)
const importVisible = ref(false)
const validateVisible = ref(false)
const validateResult = ref({})
const uploadFile = ref(null)
const currentHeaderId = ref(null)

const emptyForm = () => ({
  fiscal_year: 'FY2027', bu_code: 'X-Beauty', opening_stock_cost: 55000000,
  planned_sales_cost: 112000000, planned_sales_total_retail: 320000000,
  planned_markdown_cost: 0, good_in_transit_cost: 0, stock_cover_months: 5, gp_pct: 0.65,
})
const form = ref(emptyForm())

function fmtMoney(v) {
  if (v == null) return '-'
  return Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })
}

function cellText(v) {
  if (v == null || v === '') return ''
  if (typeof v === 'string' && (v.endsWith('%') || v === 'TRUE' || v === 'FALSE')) return v
  return Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })
}

function pivotRowClass({ row }) {
  return row.label === 'Total' ? 'total-row' : ''
}

async function loadAll() {
  loading.value = true
  try {
    const [headers, dashboard] = await Promise.all([
      api.get('/otb/headers', { params: { fiscal_year: fiscalYear.value } }),
      api.get('/otb/dashboard', { params: { fiscal_year: fiscalYear.value } }),
    ])
    dash.value = dashboard
    if (headers.length) {
      currentHeaderId.value = headers[0].id
      const pivot = await api.get('/otb/monthly/pivot', {
        params: { header_id: headers[0].id, fiscal_year: fiscalYear.value },
      })
      pivotColumns.value = pivot.columns || []
      pivotRows.value = pivot.rows || []
    } else {
      pivotColumns.value = []
      pivotRows.value = []
    }
  } finally {
    loading.value = false
  }
}

function openHeader() {
  const h = dash.value.otb_header
  form.value = h ? { ...h } : emptyForm()
  headerVisible.value = true
}

async function saveHeader() {
  saving.value = true
  try {
    const saved = await api.post('/otb/headers', form.value)
    currentHeaderId.value = saved.id
    ElMessage.success(t('otb.dash.msgHeaderSaved'))
    headerVisible.value = false
    await loadAll()
  } finally { saving.value = false }
}

async function triggerCalc() {
  if (!currentHeaderId.value) { ElMessage.warning(t('otb.dash.msgSaveFirst')); return }
  calcLoading.value = true
  try {
    calcResult.value = await api.post('/otb/calculate', {
      header_id: currentHeaderId.value, fiscal_year: fiscalYear.value,
    })
    ElMessage.success(t('otb.dash.msgCalcDone'))
    await loadAll()
  } finally { calcLoading.value = false }
}

function openImport() { importVisible.value = true }
function onFileChange(file) { uploadFile.value = file.raw }

async function doImport() {
  if (!uploadFile.value) { ElMessage.warning(t('otb.dash.msgPickExcel')); return }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', uploadFile.value)
    fd.append('fiscal_year', fiscalYear.value)
    const res = await api.post('/otb/import', fd)
    ElMessage.success(t('otb.dash.msgImported', { b: res.brand_summary || 0, i: res.item_plan || 0 }))
    importVisible.value = false
    await loadAll()
  } finally { importing.value = false }
}

async function runValidate() {
  validateResult.value = await api.get('/otb/validate', { params: { fiscal_year: fiscalYear.value } })
  validateVisible.value = true
}

onMounted(loadAll)
</script>

<style scoped>
.kpi-card { text-align: center; }
.kpi-label { font-size: 13px; color: #909399; }
.kpi-value { font-size: 24px; font-weight: 600; color: #303133; margin-top: 8px; }
.kpi-sub { font-size: 14px; color: #909399; }
.section-title { font-weight: 600; margin: 18px 0 10px; color: #303133; }
.calc-summary { margin-top: 12px; }
.cell-emphasis { font-weight: 600; color: #303133; }
.fy-total { font-weight: 700; color: #409eff; }
:deep(.total-row) { background: #f5f7fa !important; font-weight: 600; }
:deep(.el-table__cell) { padding: 6px 0; }
</style>

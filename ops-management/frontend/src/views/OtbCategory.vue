<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-select v-model="fiscalYear" style="width:140px">
          <el-option label="FY2027" value="FY2027" />
        </el-select>
        <el-select v-model="filterBu" clearable filterable :placeholder="t('otb.cat.allBu')" style="width:150px" @change="loadData">
          <el-option v-for="b in buList" :key="b.bu_code" :label="b.label || b.bu_code" :value="b.bu_code" />
        </el-select>
        <el-input v-model="keyword" :placeholder="t('otb.cat.search')" clearable style="width:180px" />
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button type="success" @click="openGenerate"><el-icon><Plus /></el-icon> {{ t('otb.cat.addCategory') }}</el-button>
        <el-button type="primary" :loading="saving" :disabled="!dirty" @click="batchSave">
          <el-icon><Check /></el-icon> {{ t('otb.cat.batchSave') }}
        </el-button>
        <span :class="['mix-total', check.valid ? 'ok' : 'bad']" style="margin-left:auto">
          Retail {{ fmt(check.sales_retail_total) }}/{{ fmt(check.planned_sales_total) }} ·
          Buy {{ fmt(check.fc_buy_plan_total) }}/{{ fmt(check.planned_sales_cost) }} {{ check.valid ? '✓' : '✗' }}
        </span>
      </div>

      <!-- OTB 风格校验条 -->
      <div :class="['check-bar', check.valid ? 'ok' : 'bad']">
        <span class="check-item">{{ t('otb.cat.mixTotal') }}<b>{{ (check.sale_mix_total*100).toFixed(2) }}%</b></span>
        <span class="check-item">{{ t('otb.cat.retailSum') }}<b>{{ fmt(check.sales_retail_total) }}</b> / {{ t('otb.cat.target') }} <b>{{ fmt(check.planned_sales_total) }}</b> {{ t('otb.cat.diff') }} <b>{{ fmt(check.diff) }}</b></span>
        <span class="check-item">{{ t('otb.cat.buySum') }}<b>{{ fmt(check.fc_buy_plan_total) }}</b> / {{ t('otb.cat.target') }} <b>{{ fmt(check.planned_sales_cost) }}</b> {{ t('otb.cat.diff') }} <b>{{ fmt(check.cost_diff) }}</b></span>
        <span class="check-item check-result">{{ check.valid ? t('otb.cat.valid') : t('otb.cat.invalid') }}</span>
      </div>

      <div class="table-flex">
        <el-table :data="filteredRows" v-loading="loading" border stripe size="small" height="100%" @cell-click="onCellClick">
          <el-table-column prop="bu_code" :label="t('otb.cat.buCode')" width="105" sortable />
          <el-table-column prop="brandid" :label="t('otb.cat.brandCode')" width="95" sortable>
            <template #default="{ row }">{{ row.brandid || '-' }}</template>
          </el-table-column>
          <el-table-column prop="brand_name" :label="t('otb.cat.brandName')" min-width="130" sortable>
            <template #default="{ row }">{{ row.brand_name || t('otb.cat.catLevel') }}</template>
          </el-table-column>
          <el-table-column prop="category_code" :label="t('otb.cat.catCode')" width="100" sortable />
          <el-table-column prop="category_name" :label="t('otb.cat.catName')" min-width="140" sortable />
          <el-table-column prop="sales_retail" label="SALES Retail" min-width="145" sortable>
            <template #default="{ row }"><span class="readonly-cell">{{ fmt(row.sales_retail) }}</span></template>
          </el-table-column>
          <el-table-column prop="sale_mix_pct" label="Sale Mix %" width="150" sortable>
            <template #default="{ row }">
              <el-input-number
                :model-value="toPct(row.sale_mix_pct)" :precision="4" :min="0" :max="100" :step="1"
                :controls="false" size="small" style="width:100%"
                @update:model-value="val => onMixInput(row, val)"
              />
            </template>
          </el-table-column>
          <el-table-column prop="fc_buy_plan" label="FC Buy Plan" min-width="140" sortable>
            <template #default="{ row }"><span class="readonly-cell">{{ fmt(row.fc_buy_plan) }}</span></template>
          </el-table-column>
          <el-table-column prop="cost_rate" :label="t('otb.cat.costRate')" width="95" sortable>
            <template #default="{ row }">{{ (row.cost_rate * 100).toFixed(2) }}%</template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 新增品类：选 BU 自动生成 -->
    <el-dialog v-model="generateVisible" :title="t('otb.cat.genTitle')" width="560px" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom:14px"
        :title="t('otb.cat.genTip')" />
      <el-form label-width="100px">
        <el-form-item label="BU" required>
          <el-select v-model="genBu" filterable :placeholder="t('otb.cat.pickBu')" style="width:100%">
            <el-option v-for="b in buList" :key="b.bu_code" :label="b.label || b.bu_code" :value="b.bu_code" />
          </el-select>
        </el-form-item>
      </el-form>
      <div v-if="genResult" class="gen-result">
        <el-alert :type="genResult.created > 0 ? 'success' : 'warning'" :closable="false"
          :title="t('otb.cat.genResult', { b: genResult.brands, c: genResult.created, s: genResult.skipped })" />
      </div>
      <template #footer>
        <el-button @click="generateVisible=false">{{ t('otb.cat.close') }}</el-button>
        <el-button type="primary" :loading="generating" :disabled="!genBu" @click="generate">{{ t('otb.cat.generate') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Search, Plus, Check } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const fiscalYear = ref('FY2027')
const filterBu = ref('')
const keyword = ref('')
const buList = ref([])
const rows = ref([])
const original = ref([])   // 原始数据快照，用于判断 dirty
const check = ref({ sale_mix_total: 0, sales_retail_total: 0, planned_sales_total: 0, diff: 0,
  fc_buy_plan_total: 0, planned_sales_cost: 0, cost_diff: 0, valid: true })
const loading = ref(false)
const saving = ref(false)
const generating = ref(false)
const generateVisible = ref(false)
const genBu = ref('')
const genResult = ref(null)

const fmt = v => v == null ? '-' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })
// 表格展示百分比数值（0-100），提交时除以100还原为0-1小数
const toPct = v => Number(((Number(v) || 0) * 100).toFixed(4))
function onMixInput(row, val) {
  row.sale_mix_pct = (Number(val) || 0) / 100
  onMixChange(row)
}

const filteredRows = computed(() => {
  const kw = keyword.value.trim().toUpperCase()
  if (!kw) return rows.value
  return rows.value.filter(r =>
    (r.brand_name || '').toUpperCase().includes(kw) ||
    (r.brandid || '').toUpperCase().includes(kw) ||
    (r.category_code || '').toUpperCase().includes(kw) ||
    (r.category_name || '').toUpperCase().includes(kw)
  )
})

const dirty = computed(() => {
  if (rows.value.length !== original.value.length) return true
  return rows.value.some((r, i) => Number(r.sale_mix_pct) !== Number(original.value[i]?.sale_mix_pct))
})

async function loadBu() {
  buList.value = await api.get('/bu/options') || []
}

async function loadData() {
  loading.value = true
  try {
    const params = { fiscal_year: fiscalYear.value }
    if (filterBu.value) params.bu_code = filterBu.value
    const [list, chk] = await Promise.all([
      api.get('/otb/categories', { params }),
      api.get('/otb/categories/check', { params }),
    ])
    rows.value = (list || []).map(r => ({ ...r }))
    original.value = (list || []).map(r => ({ ...r }))
    check.value = chk || {}
  } finally { loading.value = false }
}

// Sale Mix 变更：即时预览 Sales Retail / FC Buy Plan，并更新本地校验（与后端口径一致）
function onMixChange(row) {
  const target = Number(check.value.planned_sales_total) || 0
  const costTarget = Number(check.value.planned_sales_cost) || 0
  const mix = Number(row.sale_mix_pct) || 0
  row.sales_retail = target * mix
  row.fc_buy_plan = costTarget * mix
  const total = rows.value.reduce((s, r) => s + (Number(r.sale_mix_pct) || 0), 0)
  const retailTotal = rows.value.reduce((s, r) => s + (Number(r.sales_retail) || 0), 0)
  const buyTotal = rows.value.reduce((s, r) => s + (Number(r.fc_buy_plan) || 0), 0)
  check.value.sale_mix_total = total
  check.value.sales_retail_total = retailTotal
  check.value.diff = retailTotal - target
  check.value.fc_buy_plan_total = buyTotal
  check.value.cost_diff = buyTotal - costTarget
  check.value.valid = Math.abs(retailTotal - target) <= 1 && Math.abs(buyTotal - costTarget) <= 1
    && Math.abs(total - 1) <= 0.005
}
function onCellClick() { /* 行内编辑已由 el-input-number 直接支持 */ }

async function batchSave() {
  saving.value = true
  try {
    for (const r of rows.value) {
      await api.post('/otb/categories', r)
    }
    ElMessage.success(t('otb.cat.msgSaved'))
    await loadData()
  } finally { saving.value = false }
}

function openGenerate() { genBu.value = ''; genResult.value = null; generateVisible.value = true }
async function generate() {
  if (!genBu.value) { ElMessage.warning(t('otb.cat.pickBu')); return }
  generating.value = true
  try {
    genResult.value = await api.post('/otb/categories/generate', {
      fiscal_year: fiscalYear.value, bu_code: genBu.value,
    })
    ElMessage.success(t('otb.cat.msgGenerated', { n: genResult.value.created }))
    filterBu.value = genBu.value
    await loadData()
  } finally { generating.value = false }
}

onMounted(async () => { await loadBu(); await loadData() })
</script>

<style scoped>
.mix-total { font-weight: 600; }
.mix-total.ok { color: #67c23a; }
.mix-total.bad { color: #f56c6c; }
.check-bar {
  display: flex; flex-wrap: wrap; align-items: center; gap: 18px;
  padding: 8px 12px; margin-bottom: 8px; border-radius: 4px; font-size: 13px;
}
.check-bar.ok { background: #f0f9eb; color: #67c23a; }
.check-bar.bad { background: #fef0f0; color: #f56c6c; }
.check-item b { font-weight: 600; }
.check-result { margin-left: auto; font-weight: 600; }
.readonly-cell { color: #606266; }
.gen-result { margin-top: 12px; }
</style>

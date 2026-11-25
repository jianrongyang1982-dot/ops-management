<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-select v-model="fiscalYear" style="width:140px" @change="loadData">
          <el-option label="FY2027" value="FY2027" />
        </el-select>
        <el-select v-model="filterBu" clearable filterable :placeholder="t('otb.cat.allBu')" style="width:150px" @change="loadData">
          <el-option v-for="b in buList" :key="b.bu_code" :label="b.label || b.bu_code" :value="b.bu_code" />
        </el-select>
        <el-input v-model="keyword" :placeholder="t('otb.brand.brandName')" clearable style="width:180px" @keyup.enter="loadData" />
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button @click="keyword='';filterBu='';loadData()"><el-icon><RefreshLeft /></el-icon> {{ t('common.reset') }}</el-button>
        <el-button type="warning" @click="openGenerate"><el-icon><Refresh /></el-icon> {{ t('otb.brand.genTitle') }}</el-button>
        <el-button type="primary" :loading="savingMix" :disabled="!mixDirty" @click="batchSaveMix">
          <el-icon><Check /></el-icon> {{ t('otb.brand.batchSave') }}
        </el-button>
        <span :class="['mix-check', mixSumValid ? 'ok' : 'bad']" style="margin-left:auto">
          {{ t('otb.brand.pageMixTotal') }} {{ (mixSum*100).toFixed(2) }}% {{ mixSumValid ? '✓' : t('otb.brand.overLimit') }}
        </span>
      </div>

      <div class="check-bar">
        <span class="check-item">{{ t('otb.brand.tip') }}</span>
      </div>

      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%" show-summary :summary-method="getSummaries" :default-sort="{ prop: 'sale_mix_pct', order: 'descending' }">
          <el-table-column type="index" :label="t('otb.brand.seq')" width="65" fixed align="center" />
          <el-table-column prop="brand_name" :label="t('otb.brand.brandName')" min-width="140" fixed sortable />
          <el-table-column prop="sub_brand_id" :label="t('otb.brand.subBrandId')" width="110" sortable>
            <template #default="{ row }"><span :class="{'cell-muted':!row.sub_brand_id}">{{ row.sub_brand_id || '-' }}</span></template>
          </el-table-column>
          <el-table-column :label="t('otb.brand.bu')" min-width="110" sortable prop="bu_label">
            <template #default="{ row }"><span :class="{'cell-muted':!row.bu_label}">{{ row.bu_label || t('otb.brand.notSet') }}</span></template>
          </el-table-column>
          <el-table-column prop="item_count" :label="t('otb.brand.itemCount')" width="90" sortable />
          <el-table-column prop="sale_mix_pct" :label="t('otb.brand.mixPct')" width="130" sortable fixed>
            <template #default="{ row }">
              <el-input-number
                :model-value="toPct(row.sale_mix_pct)" :precision="4" :min="0" :max="100" :step="1"
                :controls="false" size="small" style="width:100%"
                @update:model-value="val => onMixInput(row, val)"
              />
            </template>
          </el-table-column>
          <el-table-column prop="fc_sales_plan" :label="t('otb.brand.fcSales')" min-width="130" sortable align="right" header-align="right"><template #default="{ row }">{{ fmt(row.fc_sales_plan) }}</template></el-table-column>
          <el-table-column prop="fc_buy_plan" :label="t('otb.brand.fcBuy')" min-width="130" sortable align="right" header-align="right"><template #default="{ row }">{{ fmt(row.fc_buy_plan) }}</template></el-table-column>
          <el-table-column v-for="m in 12" :key="m" :label="MONTHS[m-1]" :prop="'monthly_buy.' + (m-1)" width="105" align="right">
            <template #default="{ row }"><span class="monthly-cell">{{ fmt((row.monthly_buy||[])[m-1]) }}</span></template>
          </el-table-column>
          <el-table-column :label="t('otb.brand.op')" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openMonthly(row)">{{ t('otb.brand.curve') }}</el-button>
              <el-button link type="primary" size="small" @click="openEdit(row)">{{ t('otb.brand.edit') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pagination">
        <el-pagination background layout="total, sizes, prev, pager, next"
          :total="total" v-model:current-page="page" v-model:page-size="pageSize"
          :page-sizes="[20,50,100,200,300]" @current-change="loadData" @size-change="loadData" />
      </div>
    </div>

    <!-- 品牌月度拆解 -->
    <el-dialog v-model="monthlyVisible" :title="`${currentBrand?.brand_name} - ${t('otb.brand.monthlyTitle')}`" width="980px">
      <el-alert type="warning" :closable="false" style="margin-bottom:12px" :title="t('otb.brand.monthlyAlert')" />
      <el-table :data="sortedMonthly" border size="small">
        <el-table-column :label="t('otb.brand.month')" width="80"><template #default="{ row }">{{ monthLabel(row.month_seq) }}</template></el-table-column>
        <el-table-column prop="mix_pct" :label="t('otb.brand.mix')" width="100"><template #default="{ row }">{{ (row.mix_pct*100).toFixed(2) }}%</template></el-table-column>
        <el-table-column prop="buy_amount" :label="t('otb.brand.buyAmount')" min-width="140"><template #default="{ row }">{{ fmt(row.buy_amount) }}</template></el-table-column>
        <el-table-column prop="amount_basis" :label="t('otb.brand.basis')" width="90" />
      </el-table>
      <div class="monthly-summary">
        {{ t('otb.brand.monthTotal') }}：<b>{{ fmt(monthlyData.total) }}</b>　FC Buy Plan：<b>{{ fmt(monthlyData.fc_buy_plan) }}</b>　{{ t('otb.brand.diff') }}：<b>{{ fmt(monthlyData.diff) }}</b>
      </div>
      <template #footer>
        <el-button @click="monthlyVisible=false">{{ t('otb.brand.close') }}</el-button>
        <el-button type="primary" @click="openMixEdit">{{ t('otb.brand.editCurve') }}</el-button>
      </template>
    </el-dialog>

    <!-- 品牌月度曲线编辑 -->
    <el-dialog v-model="mixVisible" :title="`${currentBrand?.brand_name} - ${t('otb.brand.curveTitle')}`" width="680px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px" :title="t('otb.brand.curveTip')" />
      <el-table :data="mixForm" border size="small">
        <el-table-column prop="month_seq" :label="t('otb.brand.monthSeq')" width="70" />
        <el-table-column :label="t('otb.brand.month')" width="90"><template #default="{ row }">{{ monthLabel(row.month_seq) }}</template></el-table-column>
        <el-table-column :label="t('otb.brand.mix')" width="160">
          <template #default="{ row }"><el-input-number v-model="row.mix_pct" :precision="4" :min="0" :max="1" :controls="false" style="width:100%" /></template>
        </el-table-column>
      </el-table>
      <div class="monthly-summary">{{ t('otb.brand.total') }}：<b :class="mixTotalValid ? 'ok' : 'bad'">{{ (mixTotal*100).toFixed(2) }}%</b></div>
      <template #footer>
        <el-button @click="mixVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveMix" :disabled="!mixTotalValid">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 品牌编辑 -->
    <el-dialog v-model="editVisible" :title="t('otb.brand.editTitle')" width="640px" destroy-on-close>
      <el-alert type="info" :closable="false" style="margin-bottom:12px" :title="t('otb.brand.editTip')" />
      <el-form :model="editForm" label-width="170px">
        <el-form-item :label="t('otb.brand.brandName')"><el-input v-model="editForm.brand_name" disabled /></el-form-item>
        <el-form-item :label="t('otb.brand.subBrandId')"><el-input v-model="editForm.sub_brand_id" disabled /></el-form-item>
        <el-form-item :label="t('otb.brand.mixPct')"><el-input-number v-model="editForm.sale_mix_pct" :precision="4" :min="0" :max="1" style="width:100%" /></el-form-item>
        <el-form-item :label="t('otb.brand.fcSales')"><el-input :model-value="fmt(editForm.fc_sales_plan)" disabled /></el-form-item>
        <el-form-item :label="t('otb.brand.fcBuy')"><el-input :model-value="fmt(editForm.fc_buy_plan)" disabled /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" @click="saveBrand">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 按 BRANDCHILD 生成品牌数据 -->
    <el-dialog v-model="genVisible" :title="t('otb.brand.genTitle')" width="960px" top="6vh">
      <el-alert type="info" :closable="false" style="margin-bottom:12px" :title="t('otb.brand.genAlert')" />

      <div class="gen-controls">
        <span>{{ t('otb.brand.fiscalYear') }}：</span>
        <el-select v-model="genFiscalYear" style="width:130px">
          <el-option label="FY2027" value="FY2027" />
        </el-select>
        <span style="margin-left:16px">BU：</span>
        <el-select v-model="genBu" filterable :placeholder="t('otb.cat.pickBu')" style="width:180px">
          <el-option v-for="b in buList" :key="b.bu_code" :label="b.label || b.bu_code" :value="b.bu_code" />
        </el-select>
        <el-button type="primary" :loading="genLoading" style="margin-left:16px" @click="doPreview">{{ t('otb.brand.preview') }}</el-button>
      </div>

      <template v-if="genPreviewed">
        <div class="preview-section-title">{{ t('otb.brand.brandData', { t: genData.total || 0, m: genData.matched || 0, u: genData.unmatched || 0 }) }}</div>
        <el-table :data="genRows" border stripe size="small" max-height="380" :default-sort="{ prop: 'sub_brand_id', order: 'ascending' }">
          <el-table-column prop="sub_brand_id" :label="t('otb.brand.subId')" width="120" sortable />
          <el-table-column prop="brand_name" :label="t('otb.brand.subName')" min-width="160" sortable />
          <el-table-column :label="t('otb.brand.mixPct')" width="120" sortable prop="sale_mix_pct">
            <template #default="{ row }">{{ (row.sale_mix_pct*100).toFixed(2) }}%</template>
          </el-table-column>
          <el-table-column prop="fc_sales_plan" :label="t('otb.brand.fcSales')" min-width="130" sortable>
            <template #default="{ row }">{{ fmt(row.fc_sales_plan) }}</template>
          </el-table-column>
          <el-table-column prop="fc_buy_plan" :label="t('otb.brand.fcBuy')" min-width="130" sortable>
            <template #default="{ row }">{{ fmt(row.fc_buy_plan) }}</template>
          </el-table-column>
          <el-table-column :label="t('otb.brand.source')" width="120" sortable prop="matched">
            <template #default="{ row }"><el-tag :type="row.matched ? 'success' : 'info'" size="small">{{ row.matched ? t('otb.brand.fromExcel') : t('otb.brand.newBrand') }}</el-tag></template>
          </el-table-column>
        </el-table>
        <div class="preview-summary" :class="{ 'over-limit': genData.over_limit }">
          {{ t('otb.brand.saleMixTotal') }}：<b>{{ ((genData.sale_mix_total||0)*100).toFixed(2) }}%</b>
          <span v-if="genData.over_limit" style="color:#f56c6c">{{ t('otb.brand.over100') }}</span>
        </div>
      </template>

      <template #footer>
        <el-button @click="genVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="genLoading" :disabled="!genPreviewed || !genBu || genData.over_limit" @click="confirmGenerate">{{ t('otb.brand.confirmGen') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh, Search, RefreshLeft, Check } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const fiscalYear = ref('FY2027')
const keyword = ref('')
const filterBu = ref('')
const buList = ref([])
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(50)
const loading = ref(false)
const monthlyVisible = ref(false)
const mixVisible = ref(false)
const editVisible = ref(false)
const currentBrand = ref(null)
const monthlyData = ref({})
const mixForm = ref([])
const editForm = ref({})
const retailTarget = ref(320000000)
const costTarget = ref(103666666.67)
const globalSummary = ref({})   // 后端返回的全量汇总（不受分页影响）

function getSummaries({ columns }) {
  const s = globalSummary.value || {}
  return columns.map(col => {
    // 按列 property 匹配（与语言无关）
    const prop = col.property
    if (col.type === 'index') return t('otb.brand.total')
    if (prop === 'sale_mix_pct') return ((s.sale_mix_total || 0) * 100).toFixed(2) + '%'
    if (prop === 'fc_sales_plan') return fmt(s.fc_sales_plan_total)
    if (prop === 'fc_buy_plan') return fmt(s.fc_buy_plan_total)
    const m = /^monthly_buy\.(\d+)$/.exec(prop || '')
    if (m) return fmt((s.monthly_buy_total || [])[Number(m[1])])
    return ''
  })
}

// 行内批量编辑 Sale Mix
const originalMix = ref({})   // id -> 原始 sale_mix_pct
const savingMix = ref(false)
const mixDirty = computed(() => rows.value.some(r => Number(r.sale_mix_pct) !== Number(originalMix.value[r.id])))
const mixSum = computed(() => rows.value.reduce((s, r) => s + (Number(r.sale_mix_pct) || 0), 0))
const mixSumValid = computed(() => mixSum.value <= 1.005)

// 生成品牌数据（BRANDCHILD）
const genVisible = ref(false)
const genFiscalYear = ref('FY2027')
const genBu = ref('')
const genLoading = ref(false)
const genPreviewed = ref(false)
const genData = ref({})
const genRows = computed(() => genData.value.rows || [])

// 自然月顺序：1月=Jan ... 12月=Dec（月序与后端 month_seq 1-12 一致）
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
const monthLabel = seq => MONTHS[Number(seq) - 1] || ''
// 拆解弹窗按 month_seq 1-12 升序排列（不再用后端财年 month_label）
const sortedMonthly = computed(() => (monthlyData.value.monthly || []).slice().sort((a, b) => Number(a.month_seq) - Number(b.month_seq)))
const fmt = v => v == null ? '-' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })
const mixTotal = computed(() => mixForm.value.reduce((s, r) => s + (Number(r.mix_pct) || 0), 0))
const mixTotalValid = computed(() => Math.abs(mixTotal.value - 1) <= 0.005)

// Sale Mix% 显示为 1-100，存储为 0-1
const toPct = v => Number(((Number(v) || 0) * 100).toFixed(4))
function onMixInput(row, val) {
  row.sale_mix_pct = (Number(val) || 0) / 100
  // 本地实时预览 FC 计划与 1-12 月采买值（与后端公式一致）
  row.fc_sales_plan = Math.round(retailTarget.value * row.sale_mix_pct * 100) / 100
  row.fc_buy_plan = Math.round(costTarget.value * row.sale_mix_pct * 100) / 100
  const curve = row.monthly_mix || []
  if (curve.length === 12) {
    const months = curve.map(c => Math.round(row.fc_buy_plan * Number(c) * 100) / 100)
    months[11] = Math.round((row.fc_buy_plan - months.slice(0, 11).reduce((s, x) => s + x, 0)) * 100) / 100
    row.monthly_buy = months
  }
}

async function batchSaveMix() {
  if (!mixSumValid.value) { ElMessage.warning(t('otb.brand.msgOverLimit')); return }
  savingMix.value = true
  try {
    const items = rows.value
      .filter(r => Number(r.sale_mix_pct) !== Number(originalMix.value[r.id]))
      .map(r => ({ id: r.id, sale_mix_pct: r.sale_mix_pct }))
    const res = await api.post('/otb/brands/batch-sale-mix', {
      fiscal_year: fiscalYear.value, items,
    })
    ElMessage.success(t('otb.brand.msgSavedMix', { n: res.updated }))
    await loadData()
  } finally { savingMix.value = false }
}

async function loadBu() {
  buList.value = await api.get('/bu/options') || []
}

async function loadData() {
  loading.value = true
  try {
    const params = { fiscal_year: fiscalYear.value, keyword: keyword.value, page: page.value, page_size: pageSize.value }
    if (filterBu.value) params.bu_code = filterBu.value
    const res = await api.get('/otb/brands', { params })
    rows.value = (res.items || []).map(r => ({ ...r }))
    total.value = res.total
    if (res.planned_sales_total != null) retailTarget.value = res.planned_sales_total
    if (res.otb_cost != null) costTarget.value = res.otb_cost
    globalSummary.value = res.summary || {}
    originalMix.value = Object.fromEntries(rows.value.map(r => [r.id, r.sale_mix_pct]))
  } finally { loading.value = false }
}

async function openMonthly(row) {
  currentBrand.value = row
  monthlyData.value = await api.get(`/otb/brands/${row.id}/monthly`, { params: { fiscal_year: fiscalYear.value } })
  monthlyVisible.value = true
}

async function openMixEdit() {
  let mix = await api.get(`/otb/brands/${currentBrand.value.id}/mix`, { params: { fiscal_year: fiscalYear.value } })
  if (!mix || !mix.length) {
    const global = await api.get('/otb/sales-mix', { params: { fiscal_year: fiscalYear.value } })
    mix = global.map(m => ({ month_seq: m.month_seq, mix_pct: m.mix_pct }))
  }
  mixForm.value = mix
  mixVisible.value = true
}

async function saveMix() {
  await api.put(`/otb/brands/${currentBrand.value.id}/mix`, {
    items: mixForm.value, version: 'v1', fiscal_year: fiscalYear.value,
  })
  ElMessage.success(t('otb.brand.msgCurveSaved'))
  mixVisible.value = false
  monthlyData.value = await api.get(`/otb/brands/${currentBrand.value.id}/monthly`, { params: { fiscal_year: fiscalYear.value } })
}

function openEdit(row) { currentBrand.value = row; editForm.value = { ...row }; editVisible.value = true }
async function saveBrand() {
  await api.post('/otb/brands', editForm.value)
  ElMessage.success(t('otb.brand.msgBrandSaved'))
  editVisible.value = false
  await loadData()
}

// ---- BRANDCHILD 生成 ----
function openGenerate() {
  genFiscalYear.value = fiscalYear.value
  genBu.value = filterBu.value || ''
  genPreviewed.value = false
  genData.value = {}
  genVisible.value = true
}

async function doPreview() {
  if (!genBu.value) { ElMessage.warning(t('otb.brand.msgPickBu')); return }
  genLoading.value = true
  try {
    genData.value = await api.get('/otb/brands/generate/preview', {
      params: { fiscal_year: genFiscalYear.value, bu_code: genBu.value },
    })
    genPreviewed.value = true
  } finally { genLoading.value = false }
}

async function confirmGenerate() {
  genLoading.value = true
  try {
    const res = await api.post('/otb/brands/generate', {
      fiscal_year: genFiscalYear.value, bu_code: genBu.value,
    })
    ElMessage.success(t('otb.brand.msgGenerated', { t: res.total, c: res.created, r: res.reused, l: res.bu_linked }))
    genVisible.value = false
    fiscalYear.value = genFiscalYear.value
    filterBu.value = genBu.value
    await loadData()
  } finally { genLoading.value = false }
}

onMounted(() => { loadBu(); loadData() })
</script>

<style scoped>
.monthly-summary { margin-top: 12px; font-size: 14px; }
.ok { color: #67c23a; } .bad { color: #f56c6c; }
.cell-muted { color: #c0c4cc; }
.preview-section-title { font-weight: 600; font-size: 13px; margin-bottom: 8px; color: #606266; }
.preview-summary { margin-top: 12px; font-size: 14px; }
.preview-summary.over-limit { color: #f56c6c; }
.gen-controls { display: flex; align-items: center; gap: 4px; margin-bottom: 14px; font-size: 13px; color: #606266; }
.mix-check { font-size: 13px; }
.mix-check.ok { color: #67c23a; }
.mix-check.bad { color: #f56c6c; }
.check-bar { display: flex; align-items: center; padding: 6px 12px; margin-bottom: 6px; background: #f4f4f5; border-radius: 4px; font-size: 12px; color: #606266; }
.check-item { line-height: 1.4; }
.monthly-cell { color: #303133; }
</style>

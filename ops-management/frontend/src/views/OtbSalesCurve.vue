<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-select v-model="fiscalYear" style="width:140px" @change="loadData">
          <el-option label="FY2027" value="FY2027" />
        </el-select>
        <el-button type="primary" :loading="saving" :disabled="!globalDirty" @click="saveGlobal">
          <el-icon><Check /></el-icon> {{ t('otb.curve.saveGlobal') }}
        </el-button>
        <el-button @click="resetGlobal"><el-icon><RefreshLeft /></el-icon> {{ t('common.reset') }}</el-button>
        <span :class="['mix-check', globalValid ? 'ok' : 'bad']" style="margin-left:auto">
          {{ t('otb.curve.total') }} {{ (globalSum * 100).toFixed(2) }}%
          {{ globalValid ? '✓' : t('otb.curve.notHundred') }}
        </span>
      </div>

      <div class="check-bar">
        <el-icon><InfoFilled /></el-icon>
        <span style="margin-left:6px">{{ t('otb.curve.tip') }}</span>
        <el-tag v-if="overview.global_is_default" type="warning" size="small" style="margin-left:10px">
          {{ t('otb.curve.usingDefault') }}
        </el-tag>
      </div>

      <!-- 全局曲线 -->
      <div class="section-title">{{ t('otb.curve.globalTitle') }}</div>
      <div class="curve-grid">
        <div v-for="(m, i) in months" :key="m" class="curve-cell">
          <div class="curve-month">{{ m }}</div>
          <el-input-number
            v-model="globalCurve[i]" :precision="2" :min="0" :max="100" :step="0.5"
            :controls="false" size="small" style="width:100%"
            @change="onGlobalChange"
          />
          <div class="curve-hint">%</div>
        </div>
      </div>

      <!-- 曲线可视化 -->
      <div class="bar-chart">
        <div v-for="(m, i) in months" :key="'bar' + m" class="bar-col">
          <div class="bar" :style="{ height: barHeight(globalCurve[i]) }"></div>
          <div class="bar-label">{{ (Number(globalCurve[i]) || 0).toFixed(1) }}</div>
          <div class="bar-month">{{ m }}</div>
        </div>
      </div>

      <!-- 品牌曲线覆盖 -->
      <div class="section-title" style="margin-top:18px">
        {{ t('otb.curve.brandTitle') }}
        <span class="sub-note">
          {{ t('otb.curve.brandCoverage', { own: overview.brand_overridden || 0, total: overview.brand_count || 0 }) }}
        </span>
      </div>

      <div class="toolbar" style="margin:8px 0">
        <el-input v-model="brandKeyword" :placeholder="t('otb.curve.searchBrand')" clearable style="width:200px" />
        <el-select v-model="brandFilter" style="width:160px">
          <el-option :label="t('otb.curve.filterAll')" value="" />
          <el-option :label="t('otb.curve.filterOwn')" value="own" />
          <el-option :label="t('otb.curve.filterInherit')" value="inherit" />
        </el-select>
        <el-button type="primary" :loading="savingBrand" :disabled="!brandDirty" @click="saveBrands">
          <el-icon><Check /></el-icon> {{ t('otb.curve.saveBrand') }}
        </el-button>
        <span style="margin-left:auto;color:#909399;font-size:13px">
          {{ t('otb.curve.brandCount', { n: filteredBrands.length }) }}
        </span>
      </div>

      <div class="table-flex" style="flex:1">
        <el-table :data="pagedBrands" v-loading="loading" border stripe size="small" height="100%">
          <el-table-column type="index" :label="t('otb.curve.seq')" width="60" fixed align="center" />
          <el-table-column prop="brand_name" :label="t('otb.curve.brandName')" min-width="140" fixed />
          <el-table-column prop="sub_brand_id" :label="t('otb.curve.subBrandId')" width="110" />
          <el-table-column :label="t('otb.curve.curveType')" width="110" align="center">
            <template #default="{ row }">
              <el-tag :type="row.has_own_curve ? 'success' : 'info'" size="small">
                {{ row.has_own_curve ? t('otb.curve.own') : t('otb.curve.inherit') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column v-for="(m, i) in months" :key="'c' + m" :label="m" width="82" align="right">
            <template #default="{ row }">
              <span :class="{ 'cell-inherit': !row.has_own_curve }">
                {{ ((row.curve || [])[i] * 100).toFixed(2) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column :label="t('otb.curve.op')" width="150" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEdit(row)">{{ t('otb.curve.edit') }}</el-button>
              <el-button v-if="row.has_own_curve" link type="danger" size="small" @click="clearBrand(row)">
                {{ t('otb.curve.clearOwn') }}
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pagination">
        <el-pagination background layout="total, sizes, prev, pager, next"
          :total="filteredBrands.length" v-model:current-page="page" v-model:page-size="pageSize"
          :page-sizes="[50,100,200,300]" />
      </div>
    </div>

    <!-- 编辑品牌曲线 -->
    <el-dialog v-model="editVisible" :title="`${currentBrand?.brand_name} - ${t('otb.curve.editTitle')}`" width="780px">
      <el-alert type="info" :closable="false" style="margin-bottom:12px" :title="t('otb.curve.editAlert')" />
      <div class="curve-grid">
        <div v-for="(m, i) in months" :key="'e' + m" class="curve-cell">
          <div class="curve-month">{{ m }}</div>
          <el-input-number
            v-model="editCurve[i]" :precision="2" :min="0" :max="100" :step="0.5"
            :controls="false" size="small" style="width:100%"
          />
          <div class="curve-hint">%</div>
        </div>
      </div>
      <div class="monthly-summary">
        {{ t('otb.curve.total') }}：<b :class="editValid ? 'ok-text' : 'bad-text'">{{ (editSum * 100).toFixed(2) }}%</b>
        <el-button link type="primary" size="small" style="margin-left:12px" @click="fillFromGlobal">
          {{ t('otb.curve.copyGlobal') }}
        </el-button>
      </div>
      <template #footer>
        <el-button @click="editVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :disabled="!editValid" @click="applyEdit">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Check, RefreshLeft, InfoFilled } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const fiscalYear = ref('FY2027')
const months = ref(['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])

const loading = ref(false)
const saving = ref(false)
const savingBrand = ref(false)
const overview = ref({})

// 全局曲线（前端按 1-100 显示，提交时除以 100）
const globalCurve = ref(Array(12).fill(0))
const originalGlobal = ref(Array(12).fill(0))
const globalDirty = ref(false)

const globalSum = computed(() => globalCurve.value.reduce((s, v) => s + (Number(v) || 0) / 100, 0))
const globalValid = computed(() => Math.abs(globalSum.value - 1) <= 0.005)

// 品牌曲线
const brands = ref([])
const brandEdits = ref({})     // brand_id -> curve(百分比数组)
const brandDirty = computed(() => Object.keys(brandEdits.value).length > 0)
const brandKeyword = ref('')
const brandFilter = ref('')
const page = ref(1)
const pageSize = ref(100)

const editVisible = ref(false)
const currentBrand = ref(null)
const editCurve = ref(Array(12).fill(0))
const editSum = computed(() => editCurve.value.reduce((s, v) => s + (Number(v) || 0) / 100, 0))
const editValid = computed(() => Math.abs(editSum.value - 1) <= 0.005)

const filteredBrands = computed(() => {
  let list = brands.value
  const kw = brandKeyword.value.trim().toUpperCase()
  if (kw) {
    list = list.filter(b => String(b.brand_name || '').toUpperCase().includes(kw)
      || String(b.sub_brand_id || '').toUpperCase().includes(kw))
  }
  if (brandFilter.value === 'own') list = list.filter(b => b.has_own_curve)
  else if (brandFilter.value === 'inherit') list = list.filter(b => !b.has_own_curve)
  return list
})

const pagedBrands = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredBrands.value.slice(start, start + pageSize.value).map(b => ({
    ...b,
    curve: brandEdits.value[b.brand_id] || b.curve,
    has_own_curve: brandEdits.value[b.brand_id] ? true : b.has_own_curve,
  }))
})

const barHeight = (v) => `${Math.max(2, Math.min(100, (Number(v) || 0) * 7))}%`

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/otb/curve', { params: { fiscal_year: fiscalYear.value } })
    overview.value = res
    if (res.months?.length === 12) months.value = res.months
    globalCurve.value = (res.global_curve || []).map(v => Number((v * 100).toFixed(2)))
    originalGlobal.value = [...globalCurve.value]
    globalDirty.value = false
    brandEdits.value = {}
    brands.value = res.brands || []
    page.value = 1
  } finally { loading.value = false }
}

function onGlobalChange() { globalDirty.value = true }

function resetGlobal() {
  globalCurve.value = [...originalGlobal.value]
  globalDirty.value = false
}

async function saveGlobal() {
  if (!globalValid.value) {
    ElMessage.warning(t('otb.curve.notHundred'))
    return
  }
  saving.value = true
  try {
    await api.put('/otb/curve/global', {
      fiscal_year: fiscalYear.value,
      version: 'v1',
      items: globalCurve.value.map((v, i) => ({ month_seq: i + 1, mix_pct: Number(v) / 100 })),
    })
    ElMessage.success(t('otb.curve.msgSaved'))
    await loadData()
  } finally { saving.value = false }
}

function openEdit(row) {
  currentBrand.value = row
  const base = brandEdits.value[row.brand_id] || (row.curve || []).map(v => Number((v * 100).toFixed(2)))
  editCurve.value = [...base]
  editVisible.value = true
}

function fillFromGlobal() {
  editCurve.value = [...globalCurve.value]
}

function applyEdit() {
  brandEdits.value = {
    ...brandEdits.value,
    [currentBrand.value.brand_id]: [...editCurve.value],
  }
  editVisible.value = false
}

async function clearBrand(row) {
  try {
    await ElMessageBox.confirm(t('otb.curve.confirmClear', { name: row.brand_name }), t('common.tip'), {
      type: 'warning',
    })
  } catch { return }
  const res = await api.post('/otb/curve/brands', {
    fiscal_year: fiscalYear.value,
    items: [{ brand_id: row.brand_id, curve: null }],
  })
  ElMessage.success(t('otb.curve.msgCleared', { n: res.cleared }))
  await loadData()
}

async function saveBrands() {
  const items = Object.entries(brandEdits.value).map(([id, curve]) => {
    const total = curve.reduce((s, v) => s + (Number(v) || 0) / 100, 0)
    if (Math.abs(total - 1) > 0.005) {
      const b = brands.value.find(x => String(x.brand_id) === String(id))
      throw new Error(t('otb.curve.brandNotHundred', { name: b?.brand_name || id,
        pct: (total * 100).toFixed(2) }))
    }
    return { brand_id: Number(id), curve: curve.map(v => Number(v) / 100) }
  })
  savingBrand.value = true
  try {
    const res = await api.post('/otb/curve/brands', { fiscal_year: fiscalYear.value, items })
    ElMessage.success(t('otb.curve.msgBrandSaved', { n: res.saved }))
    await loadData()
  } catch (e) {
    if (e?.message && !e.response) ElMessage.warning(e.message)
  } finally { savingBrand.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.section-title {
  font-size: 14px; font-weight: 600; color: #303133;
  margin: 10px 0 8px; padding-left: 8px; border-left: 3px solid #409eff;
}
.sub-note { font-weight: 400; font-size: 12px; color: #909399; margin-left: 8px; }
.curve-grid {
  display: grid; grid-template-columns: repeat(12, 1fr); gap: 8px;
}
.curve-cell { text-align: center; }
.curve-month { font-size: 12px; color: #606266; margin-bottom: 4px; font-weight: 600; }
.curve-hint { font-size: 11px; color: #c0c4cc; }
.bar-chart {
  display: flex; align-items: flex-end; gap: 10px;
  height: 140px; margin: 14px 0 6px; padding: 0 4px;
  border-bottom: 1px solid #ebeef5;
}
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }
.bar {
  width: 60%; max-width: 42px; background: linear-gradient(180deg, #79bbff, #409eff);
  border-radius: 3px 3px 0 0; transition: height .2s;
}
.bar-label { font-size: 11px; color: #409eff; margin-top: 2px; }
.bar-month { font-size: 11px; color: #909399; }
.mix-check { font-size: 13px; font-weight: 600; }
.mix-check.ok { color: #67c23a; }
.mix-check.bad { color: #f56c6c; }
.ok-text { color: #67c23a; }
.bad-text { color: #f56c6c; }
.cell-inherit { color: #a8abb2; font-style: italic; }
.monthly-summary { margin-top: 12px; font-size: 13px; color: #606266; }
</style>

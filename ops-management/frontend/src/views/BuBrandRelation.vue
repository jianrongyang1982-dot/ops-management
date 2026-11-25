<template>
  <div class="list-page">
    <div class="list-page-card rel-page">
      <div class="toolbar">
        <el-select v-model="selectedBu" filterable :placeholder="t('bu.rel.pickBu')" style="width:220px" @change="onBuChange">
          <el-option v-for="b in buList" :key="b.bu_code" :label="b.label || b.bu_code" :value="b.bu_code" />
        </el-select>
        <el-input v-model="brandKeyword" :placeholder="t('bu.rel.searchBrand')" clearable style="width:200px" />
        <el-button type="primary" @click="loadBrands"><el-icon><Search /></el-icon> {{ t('bu.rel.refresh') }}</el-button>
        <el-button type="success" :disabled="!selectedBu" :loading="saving" @click="save">
          <el-icon><Check /></el-icon> {{ t('bu.rel.saveSetting') }}
        </el-button>
        <span class="tip-text">{{ t('bu.rel.tip') }}</span>
      </div>

      <div class="rel-body">
        <div class="bu-panel">
          <div class="panel-title">{{ t('bu.rel.buList', { n: buList.length }) }}</div>
          <div class="bu-list">
            <div
              v-for="b in buList"
              :key="b.bu_code"
              :class="['bu-item', { active: b.bu_code === selectedBu }]"
              @click="selectBu(b.bu_code)"
            >
              <span class="bu-name">{{ b.label || b.bu_code }}</span>
              <span class="bu-code">{{ b.bu_code }}</span>
            </div>
            <div v-if="!buList.length" class="empty-tip">{{ t('bu.rel.emptyBu') }}</div>
          </div>
        </div>

        <div class="brand-panel">
          <template v-if="selectedBu">
            <div class="panel-title">
              {{ t('bu.rel.setFor', { n: buLabel, c: checkedCount }) }}
              <el-button link type="primary" size="small" @click="selectAll">{{ t('bu.rel.selectAll') }}</el-button>
              <el-button link type="info" size="small" @click="clearAll">{{ t('bu.rel.clearAll') }}</el-button>
            </div>
            <div class="brand-table-wrap">
              <el-table :data="filteredBrandRows" v-loading="loading" border stripe size="small" height="100%">
                <el-table-column width="70" align="center">
                  <template #header><el-checkbox v-model="allChecked" @change="toggleAll" /></template>
                  <template #default="{ row }">
                    <el-checkbox v-model="row.checked" @change="onCheckChange(row)" />
                  </template>
                </el-table-column>
                <el-table-column width="80" :label="t('bu.rel.primary')" align="center">
                  <template #default="{ row }">
                    <el-radio
                      v-model="primaryBrand"
                      :value="row.brand_name"
                      :disabled="!row.checked"
                      @change="onPrimaryChange(row)"
                    >&nbsp;</el-radio>
                  </template>
                </el-table-column>
                <el-table-column prop="brand_name" :label="t('bu.rel.brandName')" min-width="160" />
                <el-table-column prop="note" :label="t('bu.rel.note')" width="100">
                  <template #default="{ row }">{{ row.note || '-' }}</template>
                </el-table-column>
                <el-table-column prop="brandid" :label="t('bu.rel.brandId')" width="100" />
                <el-table-column :label="t('bu.rel.sort')" width="110" align="center">
                  <template #default="{ row }">
                    <el-input-number v-model="row.sort_no" :min="0" size="small" controls-position="right" style="width:88px" />
                  </template>
                </el-table-column>
                <el-table-column :label="t('bu.rel.remark')" min-width="160">
                  <template #default="{ row }"><el-input v-model="row.remark" size="small" :placeholder="t('bu.rel.optional')" /></template>
                </el-table-column>
              </el-table>
            </div>
            <div class="save-bar">
              <span>{{ t('bu.rel.savedInfo', { n: checkedCount, primary: primaryBrand ? ' · ' + t('bu.rel.primary') : t('bu.rel.noPrimary'), p: primaryBrand }) }}</span>
              <el-button type="primary" :loading="saving" @click="save">{{ t('bu.rel.saveSetting') }}</el-button>
            </div>
          </template>
          <div v-else class="empty-select">
            <el-icon><OfficeBuilding /></el-icon>
            <p>{{ t('bu.rel.selectBuHint') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Search, Check, OfficeBuilding } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const buList = ref([])
const brandOptions = ref([])
const allRels = ref([])
const selectedBu = ref('')
const brandKeyword = ref('')
const brandRows = ref([])
const primaryBrand = ref('')
const allChecked = ref(false)
const loading = ref(false)
const saving = ref(false)

const buLabel = computed(() => {
  const b = buList.value.find(x => x.bu_code === selectedBu.value)
  return b ? (b.label || b.bu_code) : selectedBu.value
})

const filteredBrandRows = computed(() => {
  const kw = brandKeyword.value.trim().toUpperCase()
  if (!kw) return brandRows.value
  return brandRows.value.filter(r =>
    (r.brand_name || '').toUpperCase().includes(kw) ||
    (r.note || '').toUpperCase().includes(kw)
  )
})

const checkedCount = computed(() => brandRows.value.filter(r => r.checked).length)

function buildRows(opts, rels) {
  const relMap = {}
  for (const r of rels) relMap[r.brand_name] = r
  return opts.map((o, idx) => {
    const rel = relMap[o.brand_name]
    return {
      brand_name: o.brand_name,
      brandid: o.brandid,
      note: o.note,
      checked: !!rel,
      sort_no: rel ? (rel.sort_no || idx) : idx,
      remark: rel ? (rel.remark || '') : '',
    }
  })
}

async function loadAll() {
  loading.value = true
  try {
    const [buOpts, brandOpts] = await Promise.all([
      api.get('/bu/options'),
      api.get('/bu/brand-options'),
    ])
    buList.value = buOpts || []
    brandOptions.value = brandOpts || []

    if (selectedBu.value && buList.value.some(b => b.bu_code === selectedBu.value)) {
      await loadBrands()
    } else if (buList.value.length) {
      selectedBu.value = buList.value[0].bu_code
      await loadBrands()
    } else {
      selectedBu.value = ''
      brandRows.value = []
    }
  } finally { loading.value = false }
}

async function loadBrands() {
  if (!selectedBu.value) return
  loading.value = true
  try {
    const rels = await api.get(`/bu/${encodeURIComponent(selectedBu.value)}/brands`)
    allRels.value = Array.isArray(rels) ? rels : []
    applyBu(selectedBu.value)
  } finally { loading.value = false }
}

function applyBu(buCode) {
  const rels = allRels.value.filter(r => r.bu_code === buCode)
  brandRows.value = buildRows(brandOptions.value, rels)
  const primary = rels.find(r => r.is_primary === 1)
  primaryBrand.value = primary ? primary.brand_name : ''
  syncAllChecked()
}

async function onBuChange() { await loadBrands() }
function selectBu(code) { if (code !== selectedBu.value) { selectedBu.value = code; loadBrands() } }

function onCheckChange(row) {
  if (!row.checked && primaryBrand.value === row.brand_name) primaryBrand.value = ''
  syncAllChecked()
}
function onPrimaryChange(row) {
  if (primaryBrand.value === row.brand_name) row.checked = true
}
function toggleAll(val) {
  brandRows.value.forEach(r => { r.checked = val })
  if (!val) primaryBrand.value = ''
  syncAllChecked()
}
function selectAll() { brandRows.value.forEach(r => { r.checked = true }); syncAllChecked() }
function clearAll() { brandRows.value.forEach(r => { r.checked = false }); primaryBrand.value = ''; syncAllChecked() }
function syncAllChecked() {
  allChecked.value = brandRows.value.length > 0 && brandRows.value.every(r => r.checked)
}

async function save() {
  if (!selectedBu.value) { ElMessage.warning(t('bu.rel.msgPickBu')); return }
  const items = brandRows.value.filter(r => r.checked).map((r, idx) => ({
    brand_name: r.brand_name,
    brandid: r.brandid || null,
    brand_note: r.note || null,
    is_primary: primaryBrand.value === r.brand_name ? 1 : 0,
    sort_no: r.sort_no != null ? r.sort_no : idx,
    remark: r.remark || '',
  }))
  saving.value = true
  try {
    await api.post(`/bu/${encodeURIComponent(selectedBu.value)}/brands`, { bu_code: selectedBu.value, items })
    ElMessage.success(t('bu.rel.msgSaved', { n: buLabel.value, c: items.length }))
    await loadBrands()
  } finally { saving.value = false }
}

onMounted(loadAll)
</script>

<style scoped>
.tip-text { margin-left: auto; color: #909399; font-size: 12px; }
.rel-page { display: flex; flex-direction: column; height: 100%; }
.rel-body { display: flex; flex: 1; min-height: 0; gap: 12px; padding-top: 10px; }
.bu-panel { width: 240px; flex-shrink: 0; border: 1px solid #ebeef5; border-radius: 4px; display: flex; flex-direction: column; min-height: 0; }
.brand-panel { flex: 1; min-width: 0; border: 1px solid #ebeef5; border-radius: 4px; display: flex; flex-direction: column; min-height: 0; }
.panel-title { font-weight: 600; padding: 10px 12px; border-bottom: 1px solid #ebeef5; background: #fafafa; display: flex; align-items: center; gap: 8px; }
.bu-list { flex: 1; overflow: auto; padding: 4px 0; }
.bu-item { display: flex; flex-direction: column; padding: 8px 12px; cursor: pointer; border-left: 3px solid transparent; }
.bu-item:hover { background: #f5f7fa; }
.bu-item.active { background: #ecf5ff; border-left-color: #409eff; }
.bu-name { font-size: 13px; }
.bu-code { font-size: 11px; color: #909399; }
.empty-tip { padding: 20px 12px; color: #909399; font-size: 12px; text-align: center; }
.brand-table-wrap { flex: 1; min-height: 0; padding: 10px 12px; }
.save-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-top: 1px solid #f5f7fa; color: #606266; font-size: 13px; }
.empty-select { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #c0c4cc; font-size: 14px; }
.empty-select .el-icon { font-size: 48px; }
</style>

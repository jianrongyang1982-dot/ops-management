<template>
  <div class="list-page">
    <div class="list-page-card rel-page">
      <div class="toolbar">
        <el-input v-model="brandKeyword" :placeholder="t('otb.brandCat.searchBrand')" clearable style="width:200px" />
        <el-button type="primary" @click="loadAll"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button type="success" :disabled="!currentBrand" :loading="saving" @click="save">
          <el-icon><Check /></el-icon> {{ t('otb.brandCat.saveSetting') }}
        </el-button>
        <span class="tip-text">{{ t('otb.brandCat.tip') }}</span>
      </div>

      <div class="rel-body">
        <!-- 左侧：品牌列表 -->
        <div class="brand-panel">
          <div class="panel-title">{{ t('otb.brandCat.brandList', { n: filteredBrands.length }) }}</div>
          <div class="brand-list">
            <div
              v-for="b in filteredBrands"
              :key="b.brand_name"
              :class="['brand-item', { active: b.brand_name === currentBrand }]"
              @click="selectBrand(b)"
            >
              <span class="brand-name">{{ b.brand_name }}<em v-if="b.note" class="brand-note">{{ b.note }}</em></span>
              <span class="brand-count">{{ (brandRelCount[b.brand_name] || 0) }} {{ t('otb.brandCat.catUnit') }}</span>
            </div>
            <div v-if="!filteredBrands.length" class="empty-tip">{{ t('otb.brandCat.emptyBrand') }}</div>
          </div>
        </div>

        <!-- 右侧：品类设定 -->
        <div class="cat-panel">
          <template v-if="currentBrand">
            <div class="panel-title">
              {{ t('otb.brandCat.setFor', { n: currentBrand }) }}
              <el-button link type="primary" size="small" @click="selectAll">{{ t('otb.brandCat.selectAll') }}</el-button>
              <el-button link type="info" size="small" @click="clearAll">{{ t('otb.brandCat.clearAll') }}</el-button>
            </div>
            <div class="brandid-row">
              <span class="brandid-label">{{ t('otb.brandCat.masterId') }}</span>
              <el-input v-model="currentBrandid" placeholder="mdmbasedb.brand.brandid" clearable style="width:240px" />
            </div>
            <div class="cat-table-wrap">
              <el-table :data="categoryRows" v-loading="loading" border stripe size="small" height="100%">
                <el-table-column width="70" align="center">
                  <template #header><el-checkbox v-model="allChecked" @change="toggleAll" /></template>
                  <template #default="{ row }">
                    <el-checkbox v-model="row.checked" @change="onCheckChange(row)" />
                  </template>
                </el-table-column>
                <el-table-column width="80" :label="t('otb.brandCat.primary')" align="center">
                  <template #default="{ row }">
                    <el-radio
                      v-model="primaryCategory"
                      :value="row.categoryid"
                      :disabled="!row.checked"
                      @change="onPrimaryChange(row)"
                    >&nbsp;</el-radio>
                  </template>
                </el-table-column>
                <el-table-column prop="categoryid" :label="t('otb.brandCat.catId')" width="100" />
                <el-table-column prop="categoryname" :label="t('otb.brandCat.catEn')" min-width="160" />
                <el-table-column prop="note" :label="t('otb.brandCat.catCn')" min-width="140" />
                <el-table-column :label="t('otb.brandCat.sort')" width="110" align="center">
                  <template #default="{ row }">
                    <el-input-number v-model="row.sort_no" :min="0" size="small" controls-position="right" style="width:88px" />
                  </template>
                </el-table-column>
                <el-table-column :label="t('otb.brandCat.remark')" min-width="160">
                  <template #default="{ row }">
                    <el-input v-model="row.remark" size="small" :placeholder="t('otb.brandCat.optional')" />
                  </template>
                </el-table-column>
              </el-table>
            </div>
            <div class="save-bar">
              <span>{{ t('otb.brandCat.savedInfo', { n: checkedCount, primary: primaryCategory ? ' · ' + t('otb.brandCat.primary') : t('otb.brandCat.noPrimary'), p: primaryCategory }) }}</span>
              <el-button type="primary" :loading="saving" @click="save">{{ t('otb.brandCat.saveSetting') }}</el-button>
            </div>
          </template>
          <div v-else class="empty-select">
            <el-icon><Shop /></el-icon>
            <p>{{ t('otb.brandCat.selectBrand') }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Check, Shop } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const brandKeyword = ref('')
const brands = ref([])            // [{ brand_name }]
const categoryOptions = ref([])   // [{ categoryid, categoryname, note, label }]
const allRels = ref([])           // 该财年全部关系
const currentBrand = ref('')
const currentBrandid = ref('')
const categoryRows = ref([])      // [{ categoryid, categoryname, note, checked, is_primary, sort_no, remark }]
const primaryCategory = ref('')
const allChecked = ref(false)
const loading = ref(false)
const saving = ref(false)

const filteredBrands = computed(() => {
  const kw = brandKeyword.value.trim().toUpperCase()
  if (!kw) return brands.value
  return brands.value.filter(b => (b.brand_name || '').toUpperCase().includes(kw))
})

const brandRelCount = computed(() => {
  const m = {}
  for (const r of allRels.value) m[r.brand_name] = (m[r.brand_name] || 0) + 1
  return m
})

const checkedCount = computed(() => categoryRows.value.filter(r => r.checked).length)

function buildRows(categoryList, rels) {
  const relMap = {}
  for (const r of rels) relMap[r.categoryid] = r
  return categoryList.map((c, idx) => {
    const rel = relMap[c.categoryid]
    return {
      categoryid: c.categoryid,
      categoryname: c.categoryname,
      note: c.note,
      checked: !!rel,
      is_primary: rel ? rel.is_primary : 0,
      sort_no: rel ? (rel.sort_no || idx) : idx,
      remark: rel ? (rel.remark || '') : '',
    }
  })
}

async function loadAll() {
  loading.value = true
  try {
    const [brandList, catList, relList] = await Promise.all([
      api.get('/otb/brand-options', { params: { main_only: true } }),
      api.get('/otb/category-options'),
      api.get('/otb/brand-categories'),
    ])
    brands.value = brandList || []
    categoryOptions.value = catList || []
    allRels.value = relList || []
    if (currentBrand.value && brands.value.some(b => b.brand_name === currentBrand.value)) {
      await selectBrand(brands.value.find(b => b.brand_name === currentBrand.value))
    } else if (brands.value.length) {
      await selectBrand(brands.value[0])
    } else {
      currentBrand.value = ''
      categoryRows.value = []
    }
  } finally {
    loading.value = false
  }
}

async function selectBrand(brand) {
  const name = brand && brand.brand_name
  if (!name) return
  if (name === currentBrand.value && categoryRows.value.length) return
  currentBrand.value = name
  const rels = allRels.value.filter(r => r.brand_name === name)
  const first = rels[0]
  // 优先用已存关系的 brandid，其次用主数据品牌字典带出的 brandid
  currentBrandid.value = (first && first.brandid) || (brand.brandid || '')
  categoryRows.value = buildRows(categoryOptions.value, rels)
  const primary = rels.find(r => r.is_primary === 1)
  primaryCategory.value = primary ? primary.categoryid : ''
  syncAllChecked()
}

function onCheckChange(row) {
  if (!row.checked && primaryCategory.value === row.categoryid) {
    primaryCategory.value = ''
  }
  syncAllChecked()
}

function onPrimaryChange(row) {
  if (primaryCategory.value === row.categoryid) {
    row.checked = true
  }
}

function toggleAll(val) {
  categoryRows.value.forEach(r => { r.checked = val })
  if (!val) primaryCategory.value = ''
}

function selectAll() {
  categoryRows.value.forEach(r => { r.checked = true })
  syncAllChecked()
}

function clearAll() {
  categoryRows.value.forEach(r => { r.checked = false })
  primaryCategory.value = ''
  syncAllChecked()
}

function syncAllChecked() {
  allChecked.value = categoryRows.value.length > 0 && categoryRows.value.every(r => r.checked)
}

async function save() {
  if (!currentBrand.value) { ElMessage.warning(t('otb.brandCat.msgPickBrand')); return }
  const items = categoryRows.value.filter(r => r.checked).map((r, idx) => ({
    categoryid: r.categoryid,
    categoryname: r.categoryname,
    category_note: r.note,
    is_primary: primaryCategory.value === r.categoryid ? 1 : 0,
    sort_no: r.sort_no != null ? r.sort_no : idx,
    remark: r.remark || '',
  }))
  saving.value = true
  try {
    await api.post('/otb/brand-categories', {
      brand_name: currentBrand.value,
      brandid: currentBrandid.value || null,
      items,
    })
    ElMessage.success(t('otb.brandCat.msgSaved', { n: currentBrand.value, c: items.length }))
    await loadAll()
  } finally {
    saving.value = false
  }
}

onMounted(loadAll)
</script>

<style scoped>
.tip-text { margin-left: auto; color: #909399; font-size: 12px; }
.rel-page { display: flex; flex-direction: column; height: 100%; }
.rel-body { display: flex; flex: 1; min-height: 0; gap: 12px; padding-top: 10px; }
.brand-panel { width: 260px; flex-shrink: 0; border: 1px solid #ebeef5; border-radius: 4px; display: flex; flex-direction: column; min-height: 0; }
.cat-panel { flex: 1; min-width: 0; border: 1px solid #ebeef5; border-radius: 4px; display: flex; flex-direction: column; min-height: 0; }
.panel-title { font-weight: 600; padding: 10px 12px; border-bottom: 1px solid #ebeef5; background: #fafafa; display: flex; align-items: center; gap: 8px; }
.brand-list { flex: 1; overflow: auto; padding: 4px 0; }
.brand-item { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; cursor: pointer; border-left: 3px solid transparent; }
.brand-item:hover { background: #f5f7fa; }
.brand-item.active { background: #ecf5ff; border-left-color: #409eff; }
.brand-name { font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.brand-note { color: #909399; font-size: 11px; font-style: normal; margin-left: 6px; }
.brand-count { color: #909399; font-size: 12px; flex-shrink: 0; }
.empty-tip { padding: 20px 12px; color: #909399; font-size: 12px; text-align: center; }
.brandid-row { padding: 10px 12px 0; display: flex; align-items: center; gap: 10px; }
.brandid-label { color: #606266; font-size: 12px; }
.cat-table-wrap { flex: 1; min-height: 0; padding: 10px 12px; }
.save-bar { display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-top: 1px solid #ebeef5; color: #606266; font-size: 13px; }
.empty-select { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; color: #c0c4cc; font-size: 14px; }
.empty-select .el-icon { font-size: 48px; }
</style>

<template>
  <div class="list-page">
    <div class="list-page-card">
      <!-- 查询条件 -->
      <div class="toolbar">
        <el-select v-model="filters.workmode" :placeholder="t('performance.workmode')" clearable style="width:170px">
          <el-option v-for="o in workmodeOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-select v-model="filters.ownerid" filterable allow-create default-first-option clearable :placeholder="t('performance.ownerid')">
          <el-option v-for="o in ownerOptions" :key="o.value" :label="`${o.value} ${o.label}`" :value="o.value" />
        </el-select>
        <el-select v-model="filters.cateid" filterable allow-create default-first-option clearable :placeholder="t('performance.cateid')">
          <el-option v-for="c in categoryOptions" :key="c.cateid" :label="`${c.cateid} ${c.catename}`" :value="c.cateid" />
        </el-select>
        <el-input v-model="filters.catename" :placeholder="t('performance.catename')" clearable />
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button @click="resetFilters"><el-icon><RefreshLeft /></el-icon> {{ t('common.reset') }}</el-button>
      </div>

      <!-- 操作按钮 -->
      <div class="toolbar">
        <el-button type="success" @click="openCreate"><el-icon><Plus /></el-icon> {{ t('performance.create') }}</el-button>
        <el-button type="warning" @click="openImport"><el-icon><Upload /></el-icon> {{ t('performance.import') }}</el-button>
        <el-button @click="exportData"><el-icon><Download /></el-icon> {{ t('performance.export') }}</el-button>
        <span style="margin-left:auto;color:#909399;font-size:13px">{{ t('common.total', { n: total }) }}</span>
      </div>

      <!-- 数据表格：列顺序与参考界面一致 -->
      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%">
          <el-table-column prop="id" :label="t('performance.coefficientNo')" width="90" />
          <el-table-column :label="t('performance.workmode')" width="120">
            <template #default="{ row }">{{ workmodeLabel(row.workmode) }}</template>
          </el-table-column>
          <el-table-column prop="cateid" :label="t('performance.cateid')" width="120" />
          <el-table-column prop="catename" :label="t('performance.catename')" min-width="200" show-overflow-tooltip />
          <el-table-column prop="price1" :label="t('performance.price1')" min-width="120" />
          <el-table-column prop="price2" :label="t('performance.price2')" min-width="120" />
          <el-table-column prop="price3" :label="t('performance.price3')" min-width="120" />
          <el-table-column prop="createTime" :label="t('performance.createdAt')" min-width="170" />
          <el-table-column prop="modifytime" :label="t('performance.modifiedAt')" min-width="170" />
          <el-table-column prop="creator" :label="t('performance.createdBy')" width="110" />
          <el-table-column prop="modifier" :label="t('performance.modifiedBy')" width="110" />
          <el-table-column :label="t('container.operation')" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEdit(row)">{{ t('common.edit') }}</el-button>
              <el-button link type="danger" size="small" @click="handleDelete(row)">{{ t('common.delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pagination">
        <el-pagination
          background
          layout="total, sizes, prev, pager, next"
          :total="total"
          v-model:current-page="filters.page"
          v-model:page-size="filters.page_size"
          :page-sizes="[20, 50, 100, 200]"
          @current-change="loadData"
          @size-change="loadData"
        />
      </div>
    </div>

    <!-- 新增 / 编辑 -->
    <el-dialog
      v-model="formVisible"
      :title="editingId ? t('performance.editTitle') : t('performance.createTitle')"
      width="560px"
      destroy-on-close
    >
      <el-form :model="form" :label-width="locale === 'enUS' ? '130px' : '110px'">
        <el-form-item :label="t('performance.ownerid')" required>
          <el-select
            v-model="form.ownerid"
            filterable
            allow-create
            default-first-option
            clearable
            style="width:100%"
            :placeholder="t('performance.ownerid')"
          >
            <el-option v-for="o in ownerOptions" :key="o.value" :label="`${o.value} ${o.label}`" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('performance.workmode')" required>
          <el-select v-model="form.workmode" style="width:100%">
            <el-option v-for="o in workmodeOptions" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('performance.cateid')">
          <el-select
            v-model="form.cateid"
            filterable
            allow-create
            default-first-option
            clearable
            style="width:100%"
            :placeholder="t('performance.cateid')"
            @change="fillCategoryName"
          >
            <el-option v-for="c in categoryOptions" :key="c.cateid" :label="`${c.cateid} ${c.catename}`" :value="c.cateid" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('performance.catename')">
          <el-input v-model="form.catename" />
        </el-form-item>
        <el-form-item :label="t('performance.price1')">
          <el-input-number v-model="form.price1" :precision="5" :step="0.00001" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item :label="t('performance.price2')">
          <el-input-number v-model="form.price2" :precision="5" :step="0.00001" :min="0" style="width:100%" />
        </el-form-item>
        <el-form-item :label="t('performance.price3')">
          <el-input-number v-model="form.price3" :precision="5" :step="0.00001" :min="0" style="width:100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 导入 -->
    <el-dialog v-model="importVisible" :title="t('performance.importTitle')" width="520px">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom:16px">
        {{ t('performance.importTemplate') }}
      </el-alert>
      <el-upload ref="uploadRef" class="upload-demo" drag :auto-upload="false" :limit="1" accept=".xlsx" @change="onFileChange">
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">{{ t('container.importDrag') }}<em>{{ t('container.importClick') }}</em></div>
      </el-upload>
      <template #footer>
        <el-button @click="importVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="importing" @click="submitImport">{{ t('container.importStart') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, RefreshLeft, Plus, Upload, Download } from '@element-plus/icons-vue'
import api from '../api'
import { useCommonDicts } from '../composables/useCommonDicts'

const { t, locale } = useI18n()
const { owners: ownerOptions, load: loadCommonDicts } = useCommonDicts()

const workmodeOptions = ref([])
const workmodeFallbackKeys = {
  '1': 'performance.picking',
  '2': 'performance.scanning',
  '3': 'performance.replenishment',
}

function workmodeLabel(value) {
  const key = String(value ?? '')
  const hit = workmodeOptions.value.find((o) => o.value === key)
  if (hit) return hit.label
  if (workmodeFallbackKeys[key]) return t(workmodeFallbackKeys[key])
  return value || '--'
}

const categoryOptions = ref([])

function fillCategoryName() {
  const key = String(form.cateid ?? '').trim()
  const hit = categoryOptions.value.find((c) => c.cateid === key)
  if (hit) form.catename = hit.catename
}

const filters = reactive({ workmode: '', ownerid: '', cateid: '', catename: '', page: 1, page_size: 20 })
const rows = ref([])
const total = ref(0)
const loading = ref(false)

const formVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const form = reactive({
  ownerid: '', cateid: '', catename: '', price1: 0, price2: 0, price3: 0, workmode: '1',
})

const importVisible = ref(false)
const importFile = ref(null)
const importing = ref(false)

function queryParams(includePaging = true) {
  const params = {}
  Object.keys(filters).forEach((key) => {
    if (!includePaging && (key === 'page' || key === 'page_size')) return
    const value = filters[key]
    if (value !== '' && value !== null && value !== undefined) params[key] = value
  })
  return params
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/performance/coefficients', { params: queryParams() })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(filters, { workmode: '', ownerid: '', cateid: '', catename: '', page: 1 })
  loadData()
}

function openCreate() {
  editingId.value = null
  Object.assign(form, { ownerid: '', cateid: '', catename: '', price1: 0, price2: 0, price3: 0, workmode: '1' })
  formVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    ownerid: row.ownerid || '',
    cateid: row.cateid || '',
    catename: row.catename || '',
    price1: Number(row.price1 || 0),
    price2: Number(row.price2 || 0),
    price3: Number(row.price3 || 0),
    workmode: row.workmode || '1',
  })
  formVisible.value = true
}

async function submitForm() {
  if (!form.ownerid) {
    ElMessage.warning(t('performance.needOwnerid'))
    return
  }
  saving.value = true
  try {
    const payload = { ...form }
    if (editingId.value) {
      await api.put(`/performance/coefficients/${editingId.value}`, payload)
      ElMessage.success(t('performance.editSuccess'))
    } else {
      await api.post('/performance/coefficients', payload)
      ElMessage.success(t('performance.createSuccess'))
    }
    formVisible.value = false
    loadData()
  } finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(
      t('performance.deleteConfirm', { name: row.catename || row.cateid || row.id }),
      t('common.tip'),
      { type: 'warning' }
    )
    await api.delete(`/performance/coefficients/${row.id}`)
    ElMessage.success(t('performance.deleteSuccess'))
    loadData()
  } catch (e) {
    // 用户取消
  }
}

function openImport() {
  importFile.value = null
  importVisible.value = true
}
function onFileChange(file) {
  importFile.value = file.raw
}
async function submitImport() {
  if (!importFile.value) {
    ElMessage.warning(t('container.needFile'))
    return
  }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    const res = await api.post('/performance/coefficients/import', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(t('performance.importResult', {
      inserted: res.inserted, updated: res.updated, skipped: res.skipped,
    }))
    if (res.warnings?.length) {
      ElMessageBox.alert(res.warnings.join('\n'), t('performance.importTip'), { type: 'warning' })
    }
    importVisible.value = false
    loadData()
  } finally {
    importing.value = false
  }
}

async function exportData() {
  const blob = await api.get('/performance/coefficients/export', {
    params: queryParams(false),
    responseType: 'blob',
  })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'workprice.xlsx'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

async function loadWorkmodeOptions() {
  try {
    workmodeOptions.value = await api.get('/performance/coefficients/workmodes')
  } catch (e) {
    // 接口异常时保留内置兜底文案
  }
}

async function loadCategoryOptions() {
  try {
    categoryOptions.value = await api.get('/performance/categories')
  } catch (e) {
    // 字典接口异常时仍允许手工录入
  }
}

onMounted(() => {
  loadCommonDicts()
  loadWorkmodeOptions()
  loadCategoryOptions()
  loadData()
})
</script>

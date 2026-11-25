<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-input v-model="keyword" :placeholder="t('bu.def.search')" clearable style="width:200px" @keyup.enter="loadData" />
        <el-select v-model="status" style="width:120px" clearable :placeholder="t('bu.def.allStatus')">
          <el-option :label="t('bu.def.enabled')" :value="1" />
          <el-option :label="t('bu.def.disabled')" :value="0" />
        </el-select>
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button type="success" @click="openCreate"><el-icon><Plus /></el-icon> {{ t('bu.def.add') }}</el-button>
        <el-button type="warning" @click="openImport"><el-icon><Upload /></el-icon> {{ t('bu.def.import') }}</el-button>
        <el-button @click="exportData"><el-icon><Download /></el-icon> {{ t('bu.def.export') }}</el-button>
      </div>

      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%">
          <el-table-column prop="bu_code" :label="t('bu.def.buCode')" min-width="140" />
          <el-table-column prop="bu_name" :label="t('bu.def.buName')" min-width="160" />
          <el-table-column prop="bu_name_en" :label="t('bu.def.buNameEn')" min-width="160" />
          <el-table-column prop="status" :label="t('bu.def.status')" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">{{ row.status === 1 ? t('bu.def.enabled') : t('bu.def.disabled') }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="sort_no" :label="t('bu.def.sort')" width="80" align="center" />
          <el-table-column prop="brand_count" :label="t('bu.def.brandCount')" width="90" align="center" />
          <el-table-column prop="remark" :label="t('bu.def.remark')" min-width="160" show-overflow-tooltip />
          <el-table-column :label="t('bu.def.op')" width="140" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openEdit(row)">{{ t('bu.def.edit') }}</el-button>
              <el-button link type="danger" size="small" @click="del(row)">{{ t('bu.def.del') }}</el-button>
            </template>
          </el-table-column>
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

    <!-- 新增/编辑 -->
    <el-dialog v-model="dialogVisible" :title="editing ? t('bu.def.editTitle') : t('bu.def.addTitle')" width="480px" destroy-on-close>
      <el-form :model="form" label-width="100px">
        <el-form-item :label="t('bu.def.buCode')" required>
          <el-input v-model="form.bu_code" :disabled="editing" :placeholder="t('bu.def.codePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('bu.def.buName')"><el-input v-model="form.bu_name" /></el-form-item>
        <el-form-item :label="t('bu.def.buNameEn')"><el-input v-model="form.bu_name_en" /></el-form-item>
        <el-form-item :label="t('bu.def.status')">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" :active-text="t('bu.def.enabled')" :inactive-text="t('bu.def.disabled')" />
        </el-form-item>
        <el-form-item :label="t('bu.def.sort')"><el-input-number v-model="form.sort_no" :min="0" style="width:100%" /></el-form-item>
        <el-form-item :label="t('bu.def.remark')"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 导入 -->
    <el-dialog v-model="importVisible" :title="t('bu.def.importTitle')" width="520px">
      <div class="import-tip">
        {{ t('bu.def.importTip') }}<br />
        {{ t('bu.def.importTip2') }}
      </div>
      <el-upload
        class="upload-area" drag :auto-upload="false" :limit="1"
        accept=".xlsx,.xlsm" :on-change="onFileChange" :file-list="[]"
      >
        <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
        <div class="el-upload__text">{{ t('bu.def.dropFile') }} <em>{{ t('bu.def.pickFile') }}</em></div>
      </el-upload>
      <template #footer>
        <el-button @click="importVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="importing" @click="submitImport">{{ t('bu.def.startImport') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Upload, Download, UploadFilled } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const keyword = ref('')
const status = ref(null)
const page = ref(1)
const pageSize = ref(50)
const total = ref(0)
const rows = ref([])
const loading = ref(false)
const saving = ref(false)

const dialogVisible = ref(false)
const editing = ref(false)
const form = ref({})

const importVisible = ref(false)
const importFile = ref(null)
const importing = ref(false)

function queryParams(withPaging = true) {
  const p = { keyword: keyword.value || undefined, status: status.value }
  if (withPaging) { p.page = page.value; p.page_size = pageSize.value }
  return p
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/bu/list', { params: queryParams() })
    rows.value = res.items || []
    total.value = res.total || 0
  } finally { loading.value = false }
}

function resetForm() {
  return { bu_code: '', bu_name: '', bu_name_en: '', status: 1, sort_no: 0, remark: '' }
}
function openCreate() { editing.value = false; form.value = resetForm(); dialogVisible.value = true }
function openEdit(row) { editing.value = true; form.value = { ...row }; dialogVisible.value = true }

async function save() {
  if (!form.value.bu_code) { ElMessage.warning(t('bu.def.msgCodeRequired')); return }
  saving.value = true
  try {
    if (editing.value) {
      await api.put(`/bu/${form.value.id}`, form.value)
    } else {
      await api.post('/bu/', form.value)
    }
    ElMessage.success(t('bu.def.msgSaved'))
    dialogVisible.value = false
    await loadData()
  } finally { saving.value = false }
}

async function del(row) {
  await ElMessageBox.confirm(t('bu.def.deleteConfirm', { code: row.bu_code }), t('bu.def.tip'), { type: 'warning' })
  await api.delete(`/bu/${row.id}`)
  ElMessage.success(t('bu.def.msgDeleted'))
  await loadData()
}

function openImport() { importFile.value = null; importVisible.value = true }
function onFileChange(file) { importFile.value = file.raw }
async function submitImport() {
  if (!importFile.value) { ElMessage.warning(t('bu.def.msgPickFile')); return }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    const res = await api.post('/bu/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success(t('bu.def.msgImported', { i: res.inserted, u: res.updated }))
    importVisible.value = false
    await loadData()
  } finally { importing.value = false }
}

async function exportData() {
  const blob = await api.get('/bu/export', { params: queryParams(false), responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = 'bu_def.xlsx'
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

onMounted(loadData)
</script>

<style scoped>
.pager { display: flex; justify-content: flex-end; padding-top: 10px; }
.import-tip { color: #606266; font-size: 13px; line-height: 1.8; margin-bottom: 12px; }
.upload-area { width: 100%; }
</style>

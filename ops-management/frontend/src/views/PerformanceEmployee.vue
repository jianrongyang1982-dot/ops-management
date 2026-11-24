<template>
  <div class="list-page">
    <div class="list-page-card">
      <!-- 查询条件 -->
      <div class="toolbar">
        <el-select v-model="filters.ownerid" filterable allow-create default-first-option clearable
                   :placeholder="t('performance.ownerid')" style="width:220px">
          <el-option v-for="o in ownerOptions" :key="o.value" :label="`${o.value} ${o.label}`" :value="o.value" />
        </el-select>
        <el-date-picker v-model="filters.start_date" type="date" value-format="YYYY-MM-DD"
                        :placeholder="t('performance.empStartDate')" style="width:160px" />
        <el-date-picker v-model="filters.end_date" type="date" value-format="YYYY-MM-DD"
                        :placeholder="t('performance.empEndDate')" style="width:160px" />
        <el-input v-model="filters.operator" :placeholder="t('performance.empOperator')" clearable style="width:180px" />
        <el-select v-model="filters.workmode" clearable :placeholder="t('performance.empWorkmode')" style="width:170px">
          <el-option v-for="o in workmodeOptions" :key="o.value" :label="o.label" :value="o.value" />
        </el-select>
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button @click="resetFilters"><el-icon><RefreshLeft /></el-icon> {{ t('common.reset') }}</el-button>
        <span style="margin-left:auto;color:#909399;font-size:13px">{{ t('common.total', { n: total }) }}</span>
      </div>

      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%">
          <el-table-column :label="t('performance.empSeq')" width="70" align="center">
            <template #default="{ $index }">{{ (filters.page - 1) * filters.page_size + $index + 1 }}</template>
          </el-table-column>
          <el-table-column :label="t('performance.empMonth')" width="150">
            <template #default="{ row }">
              <div style="display:flex;align-items:center;gap:6px">
                <span>{{ row.month }}</span>
                <el-tag size="small" :type="row.work_mode === '1' ? 'success' : 'primary'">
                  {{ workmodeLabel(row.work_mode) }}
                </el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column :label="t('performance.empOwner')" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ ownerText(row.owner_id) }}</template>
          </el-table-column>
          <el-table-column prop="operator" :label="t('performance.empOperator')" min-width="220" show-overflow-tooltip />
          <el-table-column prop="cateid" :label="t('performance.empCateid')" width="120" />
          <el-table-column :label="t('performance.empCatename')" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">{{ cateNameText(row) }}</template>
          </el-table-column>
          <el-table-column :label="t('performance.empQty')" width="140" align="right">
            <template #default="{ row }">{{ num(row.total_operate_qty, 0) }}</template>
          </el-table-column>
          <el-table-column :label="t('performance.empAmount')" width="150" align="right">
            <template #default="{ row }">{{ num(row.total_operate_amcount, 2) }}</template>
          </el-table-column>
          <el-table-column :label="t('performance.empFee1')" width="150" align="right">
            <template #default="{ row }">{{ num(row.total_operate_fee1, 2) }}</template>
          </el-table-column>
          <el-table-column :label="t('performance.empFee2')" width="150" align="right">
            <template #default="{ row }">{{ num(row.total_operate_fee2, 2) }}</template>
          </el-table-column>
          <el-table-column :label="t('performance.empFee3')" width="150" align="right">
            <template #default="{ row }">{{ num(row.total_operate_fee3, 2) }}</template>
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Search, RefreshLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../api'
import { useCommonDicts } from '../composables/useCommonDicts'

const { t, locale } = useI18n()
const { owners: ownerOptions, load: loadCommonDicts } = useCommonDicts()

function dateStr(date) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function defaultDateRange() {
  const now = new Date()
  return {
    // 开始日期：上个月1号；结束日期：本月最后一天
    start_date: dateStr(new Date(now.getFullYear(), now.getMonth() - 1, 1)),
    end_date: dateStr(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
  }
}

const filters = reactive({
  ownerid: '', ...defaultDateRange(), operator: '', workmode: '',
  page: 1, page_size: 20,
})
const rows = ref([])
const total = ref(0)
const loading = ref(false)
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

function ownerText(value) {
  const raw = String(value ?? '')
  const hit = ownerOptions.value.find((o) => raw.startsWith(o.value))
  return hit ? `${hit.value} ${hit.label}` : (raw || '--')
}

function cateNameText(row) {
  const name = String(row.cate_name ?? '')
  const prefix = row.cateid ? `${row.cateid} ` : ''
  return name.startsWith(prefix) ? name.slice(prefix.length) : (name || '--')
}

function num(value, digits = 2) {
  const n = Number(value || 0)
  return n.toLocaleString(locale.value === 'enUS' ? 'en-US' : 'zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

async function loadData() {
  if (!filters.start_date) {
    ElMessage.warning(t('performance.empNeedStartDate'))
    return
  }
  loading.value = true
  try {
    const params = {}
    Object.keys(filters).forEach((key) => {
      const value = filters[key]
      if (value !== '' && value !== null && value !== undefined) params[key] = value
    })
    const res = await api.get('/performance/employees', { params })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(filters, {
    ownerid: '', ...defaultDateRange(), operator: '', workmode: '', page: 1,
  })
  loadData()
}

async function loadWorkmodeOptions() {
  try {
    workmodeOptions.value = await api.get('/performance/coefficients/workmodes')
  } catch (e) {
    // 使用内置兜底文案
  }
}

onMounted(() => {
  loadCommonDicts()
  loadWorkmodeOptions()
  loadData()
})
</script>

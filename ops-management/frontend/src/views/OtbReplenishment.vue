<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-input v-model="keyword" :placeholder="t('otb.replen.search')" clearable style="width:240px" @keyup.enter="loadData" />
        <el-select v-model="onlyToOrder" style="width:150px">
          <el-option :label="t('otb.replen.allItems')" value="" />
          <el-option :label="t('otb.replen.onlyOrder')" value="1" />
        </el-select>
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button type="warning" @click="generate" :loading="generating"><el-icon><Cpu /></el-icon> {{ t('otb.replen.generate') }}</el-button>
        <span style="margin-left:auto;color:#909399;font-size:13px">{{ t('otb.replen.totalItems', { n: total }) }}</span>
      </div>

      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%"
          :row-class-name="rowClass">
          <el-table-column prop="item_code" label="Item Code" width="110" fixed />
          <el-table-column prop="product_name" label="Product Name" min-width="240" show-overflow-tooltip />
          <el-table-column prop="sale_mix_pct" label="Mix%" width="90"><template #default="{ row }">{{ (row.sale_mix_pct*100).toFixed(2) }}%</template></el-table-column>
          <el-table-column prop="fc_sales_plan_retail" label="FC Sales Retail" min-width="130"><template #default="{ row }">{{ fmt(row.fc_sales_plan_retail) }}</template></el-table-column>
          <el-table-column prop="fc_buy_plan_cost" label="FC Buy Cost" min-width="130"><template #default="{ row }">{{ fmt(row.fc_buy_plan_cost) }}</template></el-table-column>
          <el-table-column label="UAE WH" width="90"><template #default="{ row }">{{ row.uae_wh }}</template></el-table-column>
          <el-table-column label="UAE ST" width="90"><template #default="{ row }">{{ row.uae_stores }}</template></el-table-column>
          <el-table-column label="QTR WH" width="90"><template #default="{ row }">{{ row.qtr_wh }}</template></el-table-column>
          <el-table-column label="QTR ST" width="90"><template #default="{ row }">{{ row.qtr_stores }}</template></el-table-column>
          <el-table-column label="BAH WH" width="90"><template #default="{ row }">{{ row.bah_wh }}</template></el-table-column>
          <el-table-column label="BAH ST" width="90"><template #default="{ row }">{{ row.bah_stores }}</template></el-table-column>
          <el-table-column prop="total_stock" label="TOTAL STOCK" width="110" />
          <el-table-column prop="ros_wk_ytd" label="ROS/WK" width="100" />
          <el-table-column prop="spot_week_cover" label="Spot WK Cover" width="120" />
          <el-table-column prop="stocks_in_transit" label="InTransit" width="100" />
          <el-table-column prop="forecasted_wk_cover" label="Target WK" width="100" />
          <el-table-column prop="propose_the_qty" label="Propose Qty" width="120">
            <template #default="{ row }"><b :class="row.propose_the_qty > 0 ? 'to-order' : 'no-order'">{{ row.propose_the_qty }}</b></template>
          </el-table-column>
          <el-table-column prop="order_remarks" label="Order Remarks" width="130" fixed="right">
            <template #default="{ row }">
              <el-tag :type="row.order_remarks === 'Ok to Order' ? 'danger' : 'info'" size="small">{{ row.order_remarks }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column :label="t('otb.replen.op')" width="120" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="recalc(row)">{{ t('otb.replen.recalc') }}</el-button>
              <el-button link type="primary" size="small" @click="openWeekly(row)">W1-W52</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="pagination">
        <el-pagination background layout="total, sizes, prev, pager, next"
          :total="total" v-model:current-page="page" v-model:page-size="pageSize"
          :page-sizes="[50,100,200,500]" @current-change="loadData" @size-change="loadData" />
      </div>
    </div>

    <!-- W1-W52 周销量 -->
    <el-dialog v-model="weeklyVisible" :title="`${currentItem?.item_code}${t('otb.replen.weeklyTitle')}`" width="1000px">
      <el-table :data="weekly" border size="small" height="500">
        <el-table-column prop="week_seq" :label="t('otb.replen.weekSeq')" width="80" />
        <el-table-column prop="sales_qty" :label="t('otb.replen.salesQty')" width="100" />
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Search, Cpu } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const keyword = ref('')
const onlyToOrder = ref('')
const rows = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(100)
const loading = ref(false)
const generating = ref(false)
const weeklyVisible = ref(false)
const weekly = ref([])
const currentItem = ref(null)

const fmt = v => v == null ? '-' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })
const rowClass = ({ row }) => row.propose_the_qty > 0 ? 'need-order-row' : ''

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/otb/items', {
      params: { keyword: keyword.value, page: page.value, page_size: pageSize.value },
    })
    rows.value = res.items
    total.value = res.total
  } finally { loading.value = false }
}

async function recalc(row) {
  const result = await api.post(`/otb/items/${row.item_code}/recalculate`)
  ElMessage.success(t('otb.replen.msgRecalc', { code: row.item_code, qty: result.propose_the_qty }))
  await loadData()
}

async function openWeekly(row) {
  currentItem.value = row
  weekly.value = await api.get(`/otb/items/${row.item_code}/weekly`)
  weeklyVisible.value = true
}

async function generate() {
  generating.value = true
  try {
    const res = await api.post('/otb/replenishment/generate', { fiscal_year: 'FY2027' })
    ElMessage.success(t('otb.replen.msgGenerated', { n: res.created }))
  } finally { generating.value = false }
}

onMounted(loadData)
</script>

<style scoped>
.to-order { color: #f56c6c; }
.no-order { color: #909399; }
:deep(.need-order-row) { background: #fef0f0 !important; }
</style>

<template>
  <div class="list-page">
    <div class="list-page-card">
      <!-- 查询条件 -->
      <div class="toolbar">
        <el-select v-model="fiscalYear" style="width:130px" @change="reloadAll">
          <el-option label="FY2027" value="FY2027" />
          <el-option label="FY2026" value="FY2026" />
        </el-select>
        <el-input v-model="subKeyword" :placeholder="t('otb.replen.subSearch')" clearable
          style="width:190px" @keyup.enter="loadSubBrands" @clear="loadSubBrands">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="loadSubBrands">{{ t('common.search') }}</el-button>
        <el-divider direction="vertical" />
        <el-input v-model="itemKeyword" :placeholder="t('otb.replen.itemSearch')" clearable
          style="width:210px" @keyup.enter="loadItems" @clear="loadItems">
          <template #prefix><el-icon><Search /></el-icon></template>
        </el-input>
        <el-button type="primary" @click="loadItems">{{ t('common.search') }}</el-button>
        <el-button type="primary" :loading="savingMix" :disabled="!mixDirty" @click="saveMix">
          <el-icon><Check /></el-icon> {{ t('otb.replen.saveMix') }}
        </el-button>
        <span style="margin-left:auto" :class="['mix-check', mixSumValid ? 'ok' : 'bad']">
          {{ t('otb.replen.mixTotal') }} {{ (mixSum * 100).toFixed(2) }}%
          {{ mixSumValid ? '✓' : t('otb.replen.mixOver') }}
        </span>
      </div>

      <div class="split-body">
        <!-- 左侧：子品牌 -->
        <div class="left-pane">
          <div class="pane-header">
            <span>{{ t('otb.replen.subBrandList') }}</span>
            <span class="pane-count">{{ subTotal }}</span>
          </div>
          <div class="pane-list" v-loading="loadingSub">
            <div v-for="s in subBrands" :key="s.sub_brand_id"
              :class="['sub-item', { active: s.sub_brand_id === currentSub?.sub_brand_id }]"
              @click="selectSub(s)">
              <div class="sub-main">
                <span class="sub-name">{{ s.sub_brand_name }}</span>
                <span class="sub-code">{{ s.sub_brand_id }}</span>
              </div>
              <div class="sub-meta">
                <span class="sub-items">{{ t('otb.replen.itemsN', { n: s.item_count }) }}</span>
                <span v-if="s.fc_sales_plan" class="sub-plan">{{ fmtShort(s.fc_sales_plan) }}</span>
              </div>
            </div>
            <el-empty v-if="!loadingSub && !subBrands.length" :description="t('otb.replen.noSub')" :image-size="60" />
          </div>
          <div class="pane-footer">
            <el-pagination small layout="prev, pager, next" :total="subTotal"
              v-model:current-page="subPage" :page-size="subPageSize" @current-change="loadSubBrands" />
          </div>
        </div>

        <!-- 右侧：商品明细 -->
        <div class="right-pane">
          <div class="pane-header">
            <span v-if="currentSub">
              {{ currentSub.sub_brand_name }}
              <span class="pane-code">{{ currentSub.sub_brand_id }}</span>
              <span class="pane-hint">
                {{ t('otb.replen.brandPlan') }}
                {{ t('otb.replen.retail') }} <b>{{ fmt(itemData.brand_retail) }}</b>
                {{ t('otb.replen.buy') }} <b>{{ fmt(itemData.brand_buy) }}</b>
                <el-tag v-if="itemData.plan_source === 'otb_header'" size="small" type="warning" effect="plain">
                  {{ t('otb.replen.planDerived') }}
                </el-tag>
                <el-tag v-else-if="itemData.plan_source === 'equal_split'" size="small" type="info" effect="plain">
                  {{ t('otb.replen.planEqualSplit') }}
                </el-tag>
              </span>
            </span>
            <span v-else>{{ t('otb.replen.pickSub') }}</span>
            <span class="pane-count">{{ itemData.total || 0 }}</span>
          </div>

          <div class="table-flex">
            <el-table :data="items" v-loading="loadingItems" border stripe size="small" height="100%"
              :row-class-name="rowClass" :default-sort="{ prop: 'fc_buy_plan_cost', order: 'descending' }">
              <el-table-column type="index" :label="t('otb.replen.seq')" width="55" fixed align="center" />
              <el-table-column prop="item_code" label="Item Code" width="100" fixed sortable />
              <el-table-column prop="product_name" label="Product Name" min-width="220" show-overflow-tooltip sortable />
              <el-table-column prop="barcode" label="Barcode" width="140" sortable>
                <template #default="{ row }"><span class="mono">{{ row.barcode || '-' }}</span></template>
              </el-table-column>
              <el-table-column prop="sale_mix_pct" :label="t('otb.replen.saleMix')" width="110" sortable align="right" header-align="right">
                <template #default="{ row }">
                  <el-input-number :model-value="toPct(row.sale_mix_pct)" :precision="2" :min="0" :max="100"
                    :step="0.5" :controls="false" size="small" style="width:100%"
                    @update:model-value="val => onMixInput(row, val)" />
                </template>
              </el-table-column>
              <el-table-column prop="fc_sales_plan_retail" label="2027 FC Sales Plan Retail" min-width="150"
                sortable align="right" header-align="right">
                <template #default="{ row }">{{ fmt(row.fc_sales_plan_retail) }}</template>
              </el-table-column>
              <el-table-column prop="fc_buy_plan_cost" label="2027 FC Buy Plan Cost" min-width="145"
                sortable align="right" header-align="right">
                <template #default="{ row }">{{ fmt(row.fc_buy_plan_cost) }}</template>
              </el-table-column>
              <el-table-column prop="uae_wh" label="UAE WH" width="85" sortable align="right" header-align="right" />
              <el-table-column prop="uae_stores" label="UAE ST" width="85" sortable align="right" header-align="right" />
              <el-table-column prop="total_stock" label="TOTAL STOCK" width="110" sortable align="right" header-align="right" />
              <el-table-column prop="ytd_sell_qty" label="YTD Sell Qty" width="105" sortable align="right" header-align="right" />
              <el-table-column prop="ros_wk_ytd" label="ROS/WK" width="95" sortable align="right" header-align="right">
                <template #default="{ row }">{{ row.ros_wk_ytd != null ? Number(row.ros_wk_ytd).toFixed(2) : '-' }}</template>
              </el-table-column>
              <el-table-column prop="spot_week_cover" label="Spot WK Cover" width="120" sortable align="right" header-align="right">
                <template #default="{ row }">{{ row.spot_week_cover != null ? Number(row.spot_week_cover).toFixed(2) : '-' }}</template>
              </el-table-column>
              <el-table-column prop="stocks_in_transit" label="InTransit" width="95" sortable align="right" header-align="right" />
              <el-table-column prop="forecasted_wk_cover" label="Target WK" width="95" sortable align="right" header-align="right" />
              <el-table-column prop="propose_the_qty" label="Propose Qty" width="115" sortable align="right" header-align="right">
                <template #default="{ row }">
                  <b :class="(row.propose_the_qty || 0) > 0 ? 'to-order' : 'no-order'">
                    {{ row.propose_the_qty ?? '-' }}
                  </b>
                </template>
              </el-table-column>
              <el-table-column prop="order_remarks" label="Order Remarks" width="125" fixed="right" sortable>
                <template #default="{ row }">
                  <el-tag :type="row.order_remarks === 'Ok to Order' ? 'danger' : 'info'" size="small">
                    {{ row.order_remarks }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column :label="t('otb.replen.op')" width="85" fixed="right">
                <template #default="{ row }">
                  <el-button link type="primary" size="small" @click="openWeekly(row)">W1-W52</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="pagination">
            <el-pagination background layout="total, sizes, prev, pager, next"
              :total="itemData.total || 0" v-model:current-page="itemPage" v-model:page-size="itemPageSize"
              :page-sizes="[50,100,200,500]" @current-change="loadItems" @size-change="loadItems" />
          </div>
        </div>
      </div>
    </div>

    <!-- W1-W52 周销量 -->
    <el-dialog v-model="weeklyVisible" :title="`${currentItem?.item_code}${t('otb.replen.weeklyTitle')}`" width="760px">
      <el-table :data="weekly" border size="small" height="440">
        <el-table-column prop="week_seq" :label="t('otb.replen.weekSeq')" width="130" />
        <el-table-column prop="sales_qty" :label="t('otb.replen.salesQty')" width="120" align="right" />
      </el-table>
      <div class="monthly-summary">
        {{ t('otb.replen.ytdTotal') }}：<b>{{ (currentItem?.ytd_sell_qty || 0).toFixed(0) }}</b>
        　ROS/WK：<b>{{ (currentItem?.ros_wk_ytd || 0).toFixed(2) }}</b>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Search, Check } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()

const fiscalYear = ref('FY2027')
// 左侧子品牌
const subKeyword = ref('')
const subBrands = ref([])
const subTotal = ref(0)
const subPage = ref(1)
const subPageSize = ref(100)
const loadingSub = ref(false)
const currentSub = ref(null)

// 右侧商品
const itemKeyword = ref('')
const items = ref([])
const itemData = ref({})
const itemPage = ref(1)
const itemPageSize = ref(100)
const loadingItems = ref(false)
const originalMix = ref({})

// 周销量
const weeklyVisible = ref(false)
const weekly = ref([])
const currentItem = ref(null)
const savingMix = ref(false)

const fmt = v => (v == null || v === '') ? '-' : Number(v).toLocaleString('en-US', { maximumFractionDigits: 0 })
const fmtShort = v => {
  const n = Number(v) || 0
  if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2) + 'M'
  if (Math.abs(n) >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return n.toFixed(0)
}
const toPct = v => Number(((Number(v) || 0) * 100).toFixed(2))
const rowClass = ({ row }) => (row.propose_the_qty || 0) > 0 ? 'need-order-row' : ''

const mixSum = computed(() => items.value.reduce((s, r) => s + (Number(r.sale_mix_pct) || 0), 0))
const mixSumValid = computed(() => mixSum.value <= 1.005)
const mixDirty = computed(() => items.value.some(
  r => Number(r.sale_mix_pct) !== Number(originalMix.value[r.item_code])
))

async function loadSubBrands() {
  loadingSub.value = true
  try {
    const res = await api.get('/otb/sub-brands', {
      params: { fiscal_year: fiscalYear.value, keyword: subKeyword.value,
        page: subPage.value, page_size: subPageSize.value },
    })
    subBrands.value = res.items || []
    subTotal.value = res.total || 0
    // 首次加载自动选中第一个有商品的子品牌
    if (!currentSub.value && subBrands.value.length) {
      const first = subBrands.value.find(s => s.item_count > 0) || subBrands.value[0]
      selectSub(first)
    }
  } finally { loadingSub.value = false }
}

function selectSub(s) {
  if (currentSub.value?.sub_brand_id === s.sub_brand_id) return
  currentSub.value = s
  itemPage.value = 1
  itemKeyword.value = ''
  loadItems()
}

async function loadItems() {
  if (!currentSub.value) return
  loadingItems.value = true
  try {
    const res = await api.get(`/otb/sub-brands/${currentSub.value.sub_brand_id}/items`, {
      params: { fiscal_year: fiscalYear.value, keyword: itemKeyword.value,
        page: itemPage.value, page_size: itemPageSize.value },
    })
    itemData.value = res
    items.value = res.items || []
    originalMix.value = Object.fromEntries(items.value.map(r => [r.item_code, r.sale_mix_pct]))
  } finally { loadingItems.value = false }
}

function onMixInput(row, val) {
  const pct = Number(val) || 0
  row.sale_mix_pct = pct / 100
  // 前端即时联动 FC 计划
  row.fc_sales_plan_retail = Math.round((Number(itemData.value.brand_retail) || 0) * row.sale_mix_pct * 100) / 100
  row.fc_buy_plan_cost = Math.round((Number(itemData.value.brand_buy) || 0) * row.sale_mix_pct * 100) / 100
}

async function saveMix() {
  if (!mixSumValid.value) {
    ElMessage.warning(t('otb.replen.mixOver'))
    return
  }
  savingMix.value = true
  try {
    const changed = items.value.filter(
      r => Number(r.sale_mix_pct) !== Number(originalMix.value[r.item_code])
    )
    const res = await api.post('/otb/items/batch-sale-mix', {
      fiscal_year: fiscalYear.value,
      items: changed.map(r => ({ item_code: r.item_code, sale_mix_pct: r.sale_mix_pct })),
    })
    ElMessage.success(t('otb.replen.msgMixSaved', { n: res.updated }))
    await loadItems()
  } finally { savingMix.value = false }
}

async function openWeekly(row) {
  currentItem.value = row
  // 周销量由明细接口一并返回（实时 sync_somdb 聚合），无需再请求
  weekly.value = (row.weekly || []).slice().sort((a, b) => a.week_seq - b.week_seq)
  weeklyVisible.value = true
}

function reloadAll() {
  currentSub.value = null
  subPage.value = 1
  loadSubBrands()
}

onMounted(loadSubBrands)
</script>

<style scoped>
.split-body {
  display: flex; gap: 12px; flex: 1; min-height: 0; overflow: hidden;
}
.left-pane {
  width: 260px; flex: 0 0 260px; display: flex; flex-direction: column;
  border: 1px solid #ebeef5; border-radius: 4px; background: #fafafa; overflow: hidden;
}
.right-pane {
  flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden;
}
.pane-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 10px; font-size: 13px; font-weight: 600; color: #303133;
  background: #f5f7fa; border-bottom: 1px solid #ebeef5; min-height: 38px;
}
.right-pane .pane-header { background: #fff; }
.pane-code { font-weight: 400; color: #909399; font-size: 12px; margin-left: 6px; }
.pane-hint { font-weight: 400; font-size: 12px; color: #909399; margin-left: 10px; }
.pane-hint b { color: #409eff; }
.pane-count {
  font-size: 12px; font-weight: 400; color: #909399;
  background: #ecf5ff; padding: 1px 8px; border-radius: 10px;
}
.pane-list { flex: 1; overflow-y: auto; padding: 6px; }
.sub-item {
  padding: 7px 9px; border-radius: 4px; cursor: pointer; margin-bottom: 4px;
  background: #fff; border: 1px solid transparent; transition: all .15s;
}
.sub-item:hover { border-color: #c6e2ff; background: #ecf5ff; }
.sub-item.active { border-color: #409eff; background: #ecf5ff; }
.sub-main { display: flex; align-items: baseline; justify-content: space-between; gap: 6px; }
.sub-name { font-size: 13px; color: #303133; font-weight: 500; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.sub-code { font-size: 11px; color: #909399; font-family: monospace; flex-shrink: 0; }
.sub-meta { display: flex; justify-content: space-between; margin-top: 3px; font-size: 11px; }
.sub-items { color: #909399; }
.sub-plan { color: #67c23a; font-weight: 500; }
.pane-footer { border-top: 1px solid #ebeef5; padding: 4px; text-align: center; background: #fff; }
.mono { font-family: monospace; font-size: 12px; color: #606266; }
.to-order { color: #f56c6c; }
.no-order { color: #909399; }
:deep(.need-order-row) { background: #fef0f0 !important; }
.mix-check { font-size: 13px; font-weight: 600; }
.mix-check.ok { color: #67c23a; }
.mix-check.bad { color: #f56c6c; }
.monthly-summary { margin-top: 10px; font-size: 13px; color: #606266; }
</style>

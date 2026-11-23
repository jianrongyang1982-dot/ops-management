<template>
  <div class="list-page">
    <div class="list-page-card">
      <!-- 工具栏 -->
      <div class="toolbar">
        <el-select v-model="filters.brand" :placeholder="t('container.brand')" clearable filterable>
          <el-option v-for="d in dict.brands" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
        <el-select v-model="filters.forwarder" :placeholder="t('container.forwarder')" clearable filterable>
          <el-option v-for="d in dict.forwarders" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
        <el-select v-model="filters.ship_co" :placeholder="t('container.shipCo')" clearable filterable>
          <el-option v-for="d in dict.shipCompanies" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
        <el-input v-model="filters.bl" :placeholder="t('container.bl')" clearable />
        <el-input v-model="filters.container_no" :placeholder="t('container.containerNo')" clearable />
        <el-select v-model="filters.status" :placeholder="t('container.status')" clearable style="width:130px">
          <el-option v-for="s in statusOptions" :key="s.value" :label="t(s.labelKey)" :value="s.value" />
        </el-select>
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button @click="resetFilters"><el-icon><RefreshLeft /></el-icon> {{ t('common.reset') }}</el-button>
      </div>
      <div class="toolbar">
        <el-button type="success" @click="openCreate"><el-icon><Plus /></el-icon> {{ t('container.create') }}</el-button>
        <el-button type="warning" @click="openImport"><el-icon><Upload /></el-icon> {{ t('container.import') }}</el-button>
        <el-button @click="downloadTemplate"><el-icon><Download /></el-icon> {{ t('container.downloadTemplate') }}</el-button>
        <!-- 列设置：显隐 + 拖拽排序 -->
        <el-popover placement="bottom-start" :width="240" trigger="click">
          <template #reference>
            <el-button><el-icon><Setting /></el-icon> {{ t('common.columns') }}</el-button>
          </template>
          <div class="col-setting">
            <div class="col-setting-tip">{{ t('common.colSettingTip') }}</div>
            <draggable v-model="columns" item-key="key" handle=".col-drag-handle" @end="onColumnChange">
              <template #item="{ element }">
                <div class="col-setting-item">
                  <el-icon class="col-drag-handle"><Rank /></el-icon>
                  <el-checkbox v-model="element.visible" @change="onColumnChange">{{ t(element.labelKey) }}</el-checkbox>
                </div>
              </template>
            </draggable>
            <div class="col-setting-footer">
              <el-button link type="primary" size="small" @click="resetColumns">{{ t('common.resetDefault') }}</el-button>
            </div>
          </div>
        </el-popover>
        <!-- 视图切换：表格 / 卡片 -->
        <el-radio-group v-model="viewMode" size="small" @change="onViewChange">
          <el-radio-button value="table"><el-icon><List /></el-icon> {{ t('common.tableView') }}</el-radio-button>
          <el-radio-button value="card"><el-icon><Grid /></el-icon> {{ t('common.cardView') }}</el-radio-button>
        </el-radio-group>
        <span style="margin-left:auto;color:#909399;font-size:13px">{{ t('common.total', { n: total }) }}</span>
      </div>

      <!-- 数据表格（列由 columns 动态渲染，支持显隐与排序） -->
      <div class="table-flex" v-show="viewMode === 'table'">
        <el-table :data="rows" v-loading="loading && viewMode === 'table'" border stripe size="small" height="100%">
          <template v-for="col in columns" :key="col.key">
            <el-table-column v-if="col.visible" :prop="col.prop" :label="t(col.labelKey)"
                             :width="col.width" :min-width="col.minWidth" :fixed="col.fixed"
                             :show-overflow-tooltip="col.tooltip || false">
              <template v-if="col.slot === 'brand'" #default="{row}">
                {{ row.brand_name || row.brand }}
              </template>
              <template v-else-if="col.slot === 'status'" #default="{row}">
                <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
              </template>
              <template v-else-if="col.slot === 'url'" #default="{row}">
                <a v-if="row.url" :href="row.url" target="_blank" rel="noopener noreferrer" class="table-track-link">
                  <el-icon><Link /></el-icon> {{ t('container.trackLink') }}
                </a>
                <span v-else style="color:#c0c4cc">—</span>
              </template>
              <template v-else-if="col.slot === 'days'" #default="{row}">
                {{ dayText(row[col.prop]) }}
              </template>
              <template v-else-if="col.slot === 'operation'" #default="{row}">
                <el-button link type="success" size="small" :loading="logisticsingId === row.id" @click="syncLogistics(row)">{{ t('container.logisticsAction') }}</el-button>
                <el-button link type="warning" size="small" :loading="syncingId === row.id" @click="syncRow(row)">{{ t('container.syncAction') }}</el-button>
                <el-button link type="info" size="small" :loading="resettingId === row.id" @click="resetFlag(row)">{{ t('container.resetFlag') }}</el-button>
                <el-button link type="primary" size="small" @click="openEdit(row)">{{ t('common.edit') }}</el-button>
                <el-button link type="danger" size="small" @click="handleDelete(row)">{{ t('common.delete') }}</el-button>
              </template>
            </el-table-column>
          </template>
        </el-table>
      </div>

      <!-- 卡片视图：每行一张卡片，上方列信息 + 下方飞驼链路条 -->
      <div class="card-flex" v-show="viewMode === 'card'" v-loading="loading && viewMode === 'card'">
        <div class="card-grid">
          <div class="track-card" v-for="(row, idx) in rows" :key="row.id">
            <!-- 卡片头：序号 + 提单号 + 状态 + 操作 -->
            <div class="card-head">
              <div class="card-head-left">
                <span class="card-seq">{{ (filters.page - 1) * filters.page_size + idx + 1 }}</span>
                <span class="card-brand">{{ row.brand_name || row.brand }}</span>
                <span class="card-bl" :title="row.bl">{{ row.bl || '—' }}</span>
                <a v-if="row.url" class="card-track-link" :href="row.url" target="_blank" rel="noopener noreferrer" :title="row.url">
                  <el-icon><Link /></el-icon> {{ t('container.trackLink') }}
                </a>
                <span class="head-goods" :class="goodsTypeClass(row.cargotype)" :title="t('container.goodsType')">
                  <el-icon><component :is="goodsTypeIcon(row.cargotype)" /></el-icon>{{ goodsTypeText(row.cargotype) }}
                </span>
                <span class="head-duration" :title="t('container.acceptDuration')">{{ t('container.acceptDuration') }} <b>{{ acceptDuration(row) }}</b></span>
                <span class="head-duration" :title="t('container.shelfDuration')">{{ t('container.shelfDuration') }} <b>{{ shelfDuration(row) }}</b></span>
              </div>
              <div class="card-head-right">
                <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
                <el-button link type="success" size="small" :loading="logisticsingId === row.id" @click="syncLogistics(row)">{{ t('container.logisticsAction') }}</el-button>
                <el-button link type="warning" size="small" :loading="syncingId === row.id" @click="syncRow(row)">{{ t('container.syncAction') }}</el-button>
                <el-button link type="info" size="small" :loading="resettingId === row.id" @click="resetFlag(row)">{{ t('container.resetFlag') }}</el-button>
                <el-button link type="primary" size="small" @click="openEdit(row)">{{ t('common.edit') }}</el-button>
                <el-button link type="danger" size="small" @click="handleDelete(row)">{{ t('common.delete') }}</el-button>
              </div>
            </div>
            <!-- 卡片信息网格（列上面的信息） -->
            <div class="card-info">
              <div class="info-item"><span class="info-label">{{ t('container.containerNo') }}</span><span class="info-value">{{ row.container_no || '—' }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.warehouseBinNo') }}</span><span class="info-value">{{ row.warehousebinno || '—' }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.warehouse') }}</span><span class="info-value">{{ row.wh || '—' }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.shipName') }}</span><span class="info-value">{{ row.ship_name || '—' }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.pol') }}</span><span class="info-value">{{ row.pol || '—' }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.pod') }}</span><span class="info-value">{{ row.pod || '—' }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.eta') }}</span><span class="info-value">{{ fmtDateTime(row.eta) || '—' }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.acdate') }}</span><span class="info-value">{{ fmtDateTime(row.acdate) || '—' }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.planDays') }}</span><span class="info-value">{{ dayText(row.plan_days) }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.actualDays') }}</span><span class="info-value">{{ dayText(row.actual_days) }}</span></div>
              <div class="info-item"><span class="info-label">{{ t('container.currentStatus') }}</span><span class="info-value" :title="currentStatusText(row)">{{ currentStatusText(row) || '—' }}</span></div>
              <div class="info-item info-remark"><span class="info-label">{{ t('container.remark') }}</span><span class="info-value" :title="row.remark">{{ row.remark || '—' }}</span></div>
            </div>
            <!-- 链路条：分两组（飞驼状态 + 物流状态），同一卡片 -->
            <div class="track-groups">
              <div class="track-group">
                <div class="track-group-title"><span class="track-group-badge freight">{{ t('container.trackGroupFreightower') }}</span></div>
                <div class="track-bar">
                  <div class="track-node" v-for="node in freightNodes(row)" :key="node.key"
                       :class="{ reached: !!node.date, estimated: node.estimated }"
                       :title="node.date ? (node.estimated ? t('container.planned') : t('container.actual')) : ''">
                    <div class="track-date">{{ node.date || t('common.empty') }}</div>
                    <div class="track-line"><span class="track-dot"></span></div>
                    <div class="track-label">{{ t(node.labelKey) }}<span v-if="node.date && node.estimated" class="plan-mark">{{ t('container.plannedMark') }}</span></div>
                  </div>
                </div>
              </div>
              <div class="track-group logistic-group">
                <div class="track-group-title"><span class="track-group-badge logistic">{{ t('container.trackGroupLogistics') }}</span></div>
                <div class="track-bar">
                  <div class="track-node" v-for="node in logisticsNodes(row)" :key="node.key" :class="{ reached: !!node.date }">
                    <div class="track-date">{{ node.fullDate || t('common.empty') }}</div>
                    <div class="track-line"><span class="track-dot"></span></div>
                    <div class="track-label">{{ t(node.labelKey) }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div v-if="!rows.length" class="card-empty">{{ t('common.noData') }}</div>
      </div>
      <!-- 分页固定底端 -->
      <div class="pagination">
        <el-pagination background layout="total, sizes, prev, pager, next" :total="total"
                       v-model:current-page="filters.page" v-model:page-size="filters.page_size"
                       :page-sizes="[20, 50, 100]" @current-change="loadData" @size-change="loadData" />
      </div>
    </div>

    <!-- 录入/编辑对话框 -->
    <el-dialog v-model="formVisible" :title="editingId ? t('container.editTitle') : t('container.createTitle')" width="760px" destroy-on-close>
      <el-form :model="form" :label-width="locale === 'enUS' ? '130px' : '100px'" size="default">
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item :label="t('container.sn')"><el-input-number v-model="form.sn" :min="0" style="width:100%" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item :label="t('container.brand')" required>
            <el-select v-model="form.brand" filterable :placeholder="t('common.pleaseSelect')" style="width:100%">
              <el-option v-for="d in dict.brands" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item :label="t('container.warehouse')">
            <el-select v-model="form.wh" filterable clearable :placeholder="t('common.pleaseSelect')" style="width:100%">
              <el-option v-for="d in dict.warehouses" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item></el-col>
          <el-col :span="12"><el-form-item :label="t('container.forwarder')">
            <el-select v-model="form.forwarder" filterable clearable :placeholder="t('common.pleaseSelect')" style="width:100%">
              <el-option v-for="d in dict.forwarders" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item :label="t('container.cargoType')">
            <el-select v-model="form.cargotype" clearable :placeholder="t('common.pleaseSelect')" style="width:100%">
              <el-option v-for="d in dict.cargotypes" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item></el-col>
          <el-col :span="12"><el-form-item :label="t('container.bl')"><el-input v-model="form.bl" :placeholder="t('container.bl')" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item :label="t('container.shipCo')">
            <el-select v-model="form.ship_co" filterable clearable :placeholder="t('common.pleaseSelect')" style="width:100%">
              <el-option v-for="d in dict.shipCompanies" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item></el-col>
          <el-col :span="12"><el-form-item :label="t('container.shipName')"><el-input v-model="form.ship_name" :placeholder="t('container.shipName')" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item :label="t('container.containerNo')" required><el-input v-model="form.container_no" :placeholder="t('container.requiredField')" /></el-form-item></el-col>
          <el-col :span="12"><el-form-item :label="t('container.warehouseBinNo')"><el-input v-model="form.warehousebinno" /></el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item :label="t('container.pol')">
            <el-select v-model="form.pol" filterable clearable :placeholder="t('common.pleaseSelect')" style="width:100%">
              <el-option v-for="d in dict.pols" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item></el-col>
          <el-col :span="12"><el-form-item :label="t('container.pod')">
            <el-select v-model="form.pod" filterable clearable :placeholder="t('common.pleaseSelect')" style="width:100%">
              <el-option v-for="d in dict.pods" :key="d.value" :label="d.label" :value="d.value" />
            </el-select>
          </el-form-item></el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12"><el-form-item :label="t('container.loadDate')">
            <el-date-picker v-model="form.load_date" type="datetime" :placeholder="t('container.selectDate')" style="width:100%" value-format="YYYY-MM-DDTHH:mm:ss" />
          </el-form-item></el-col>
          <el-col :span="12"><el-form-item :label="t('container.etaField')">
            <el-date-picker v-model="form.eta" type="datetime" :placeholder="t('container.selectDate')" style="width:100%" value-format="YYYY-MM-DDTHH:mm:ss" />
          </el-form-item></el-col>
        </el-row>
        <el-form-item :label="t('container.remark')"><el-input v-model="form.remark" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="formVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 导入对话框 -->
    <el-dialog v-model="importVisible" :title="t('container.importTitle')" width="500px">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom:16px">
        {{ t('container.importTemplate') }}
      </el-alert>
      <el-upload ref="uploadRef" class="upload-demo" drag :auto-upload="false" :limit="1" accept=".xlsx,.xls" @change="onFileChange">
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">{{ t('container.importDrag') }}<em>{{ t('container.importClick') }}</em></div>
      </el-upload>
      <template #footer>
        <el-button @click="importVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="importing" @click="submitImport">{{ t('container.importStart') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import Draggable from 'vuedraggable'
import { Setting, Rank, List, Grid, Link, Goods, Box } from '@element-plus/icons-vue'
import api from '../api'
import { STATUS_KEY_MAP } from '../i18n'

const { t, locale } = useI18n()

// 表格列配置：key 唯一标识，labelKey 走 i18n，visible 显隐，顺序可拖拽，持久化到 localStorage
const DEFAULT_COLUMNS = [
  { key: 'sn', prop: 'sn', labelKey: 'container.sn', width: 70, visible: true },
  { key: 'brand', prop: 'brand_name', labelKey: 'container.brandName', width: 100, visible: true, slot: 'brand' },
  { key: 'bl', prop: 'bl', labelKey: 'container.bl', width: 150, visible: true, tooltip: true },
  { key: 'container_no', prop: 'container_no', labelKey: 'container.containerNo', width: 130, visible: true },
  { key: 'ship_name', prop: 'ship_name', labelKey: 'container.shipName', width: 130, visible: true, tooltip: true },
  { key: 'pol', prop: 'pol', labelKey: 'container.pol', width: 90, visible: true },
  { key: 'pod', prop: 'pod', labelKey: 'container.pod', width: 90, visible: true },
  { key: 'eta', prop: 'eta', labelKey: 'container.eta', width: 110, visible: true },
  { key: 'acdate', prop: 'acdate', labelKey: 'container.acdate', width: 110, visible: true },
  { key: 'plan_days', prop: 'plan_days', labelKey: 'container.planDays', width: 90, visible: true, slot: 'days' },
  { key: 'actual_days', prop: 'actual_days', labelKey: 'container.actualDays', width: 90, visible: true, slot: 'days' },
  { key: 'status', prop: 'status', labelKey: 'container.status', width: 100, visible: true, slot: 'status' },
  { key: 'url', prop: 'url', labelKey: 'container.trackLink', width: 100, visible: true, slot: 'url' },
  { key: 'operation', labelKey: 'container.operation', width: 300, visible: true, fixed: 'right', slot: 'operation' },
]
const COLUMNS_KEY = 'container_columns'
const columns = ref(loadColumns())

function loadColumns() {
  try {
    const saved = JSON.parse(localStorage.getItem(COLUMNS_KEY) || 'null')
    if (Array.isArray(saved) && saved.length) {
      // 用已保存的 key 顺序与显隐，合并默认配置（新增列也能出现）
      const map = Object.fromEntries(saved.map(c => [c.key, c]))
      const ordered = saved.map(c => DEFAULT_COLUMNS.find(d => d.key === c.key)).filter(Boolean)
      const missing = DEFAULT_COLUMNS.filter(d => !map[d.key])
      const merged = [...ordered, ...missing]
      merged.forEach(c => { c.visible = map[c.key] ? !!map[c.key].visible : c.visible })
      return merged.map(c => ({ ...c }))
    }
  } catch (e) { /* 忽略损坏的配置 */ }
  return DEFAULT_COLUMNS.map(c => ({ ...c }))
}

function onColumnChange() {
  localStorage.setItem(COLUMNS_KEY, JSON.stringify(
    columns.value.map(c => ({ key: c.key, visible: c.visible }))
  ))
}

function resetColumns() {
  columns.value = DEFAULT_COLUMNS.map(c => ({ ...c }))
  onColumnChange()
}

// 视图模式（表格/卡片），持久化
const VIEW_KEY = 'container_view_mode'
const viewMode = ref(localStorage.getItem(VIEW_KEY) === 'card' ? 'card' : 'table')
function onViewChange() {
  localStorage.setItem(VIEW_KEY, viewMode.value)
}

// 日期格式化：取 YYYY-MM-DD 部分，空返回空串
function fmtDate(v) {
  return v ? String(v).slice(0, 10) : ''
}

// 日期+时间格式化：YYYY-MM-DD HH:mm:ss（兼容后端 ISO 的 T）
function fmtDateTime(v) {
  if (!v) return ''
  return String(v).replace('T', ' ').slice(0, 19)
}

// 商品/非商品：cargotype 0=商品，1=非商品
function goodsTypeText(v) {
  if (v === null || v === undefined || v === '') return '—'
  const code = String(v)
  if (code === '1') return t('container.nonProduct')
  if (code === '0') return t('container.product')
  return '—'
}
// 商品用包裹图标(绿)、非商品用箱子图标(橙)，一眼区分
function goodsTypeIcon(v) {
  return String(v) === '1' ? Box : Goods
}
function goodsTypeClass(v) {
  if (String(v) === '1') return 'non-product'
  if (String(v) === '0') return 'product'
  return ''
}

// 天数展示：后端已按日期计算（计划到达/装船、提柜/装船），空值显示占位符
function dayText(v) {
  if (v === null || v === undefined || v === '') return '—'
  return locale.value === 'enUS' ? `${v} d` : `${v} 天`
}

// 时长格式化：结束 - 开始，输出「X天X小时X分」
function diffText(start, end) {
  if (!start || !end) return '—'
  const t1 = new Date(String(start).replace('T', ' ').replace(/-/g, '/')).getTime()
  const t2 = new Date(String(end).replace('T', ' ').replace(/-/g, '/')).getTime()
  if (isNaN(t1) || isNaN(t2) || t2 < t1) return '—'
  const mins = Math.floor((t2 - t1) / 60000)
  const d = Math.floor(mins / 1440)
  const h = Math.floor((mins % 1440) / 60)
  const m = mins % 60
  if (locale.value === 'enUS') {
    return [d ? d + 'd' : '', h ? h + 'h' : '', (m || (!d && !h)) ? m + 'm' : ''].filter(Boolean).join(' ')
  }
  return [d ? d + '天' : '', h ? h + '小时' : '', (m || (!d && !h)) ? m + '分' : ''].filter(Boolean).join('')
}

// 验收时长 = 关单时间 - 最早（开始）验收时间
function acceptDuration(row) {
  return diffText(row.acceptanceStartTime, row.orderCloseTime)
}

// 上架时长 = 最晚上架时间 - 最早上架时间
function shelfDuration(row) {
  return diffText(row.earliestShelfTime, row.latestShelfTime)
}

// 飞驼 isEsti 映射：Y=计划（未实际发生），N=实际
function estiMap(row) {
  try { return JSON.parse(row.statusEsti || '{}') || {} } catch (e) { return {} }
}

// 当前状态：飞驼 currentStatus JSON，取中文/英文描述 + 时间
function currentStatusText(row) {
  try {
    const s = JSON.parse(row.currentStatus || '{}')
    if (!s || !s.eventCode) return ''
    const desc = locale.value === 'enUS'
      ? (s.descriptionEn || s.descriptionCn || '')
      : (s.descriptionCn || s.descriptionEn || '')
    const time = (s.eventTime || '').slice(0, 16)
    return [desc, time].filter(Boolean).join(' ')
  } catch (e) { return '' }
}

// 飞驼链路六节点（第一组）
// - isEsti=Y 的事件节点（提空柜/装船/提柜/还柜）显示为灰色计划节点
// - 预计到达：只要有 plandate 即为亮色（正常），无值才灰
// - 实际到达：只有真实到达（acdate=delivery.ata）才亮色，否则灰色
function freightNodes(row) {
  const esti = estiMap(row)
  const isPlan = code => String(esti[code] || '').toUpperCase() === 'Y'
  return [
    { key: 'stsp', date: fmtDate(row.stspdate), labelKey: 'container.trackEmptyPickup', estimated: isPlan('STSP') },
    { key: 'load', date: fmtDate(row.loaddate), labelKey: 'container.trackLoaded', estimated: isPlan('LOBD') },
    { key: 'plan', date: fmtDate(row.plandate), labelKey: 'container.trackEta', estimated: !row.plandate },
    { key: 'actual', date: fmtDate(row.acdate), labelKey: 'container.trackAta', estimated: !row.acdate },
    { key: 'stcs', date: fmtDate(row.stcsdate), labelKey: 'container.trackPickup', estimated: isPlan('STCS') },
    { key: 'rcve', date: fmtDate(row.rcvedate), labelKey: 'container.trackReturn', estimated: isPlan('RCVE') },
  ]
}

// 物流链路五节点（第二组），日期+时间全部展示
function logisticsNodes(row) {
  return [
    { key: 'bill', date: fmtDate(row.billdate), fullDate: fmtDate(row.billdate), labelKey: 'container.trackOrderDate' },
    { key: 'accs', date: fmtDate(row.acceptanceStartTime), fullDate: fmtDateTime(row.acceptanceStartTime), labelKey: 'container.trackAcceptStart' },
    { key: 'accc', date: fmtDate(row.acceptanceCompleteTime), fullDate: fmtDateTime(row.acceptanceCompleteTime), labelKey: 'container.trackAcceptComplete' },
    { key: 'close', date: fmtDate(row.orderCloseTime), fullDate: fmtDateTime(row.orderCloseTime), labelKey: 'container.trackOrderClose' },
    { key: 'eshelf', date: fmtDate(row.earliestShelfTime), fullDate: fmtDateTime(row.earliestShelfTime), labelKey: 'container.trackEarliestShelf' },
    { key: 'lshelf', date: fmtDate(row.latestShelfTime), fullDate: fmtDateTime(row.latestShelfTime), labelKey: 'container.trackLatestShelf' },
  ]
}

const loading = ref(false)
const rows = ref([])
const total = ref(0)
const filters = reactive({
  brand: '', forwarder: '', ship_co: '', bl: '', container_no: '', status: '',
  page: 1, page_size: 20,
})
const dict = reactive({ brands: [], forwarders: [], shipCompanies: [], warehouses: [], pols: [], pods: [], cargotypes: [] })

// 状态下拉：value 用中文 code 兼容后端筛选，label 用 i18n
const statusOptions = computed(() => [
  { value: '在途', labelKey: 'container.statusTransit' },
  { value: '延误', labelKey: 'container.statusDelay' },
  { value: '已到港', labelKey: 'container.statusArrived' },
  { value: '待提柜', labelKey: 'container.statusPickup' },
  { value: '已完成', labelKey: 'container.statusCompleted' },
])

function statusText(code) {
  const key = STATUS_KEY_MAP[code]
  return key ? t(key) : code
}

const formVisible = ref(false)
const editingId = ref(null)
const saving = ref(false)
const form = reactive({})

const importVisible = ref(false)
const importing = ref(false)
const importFile = ref(null)
const syncingId = ref(null)
const logisticsingId = ref(null)
const resettingId = ref(null)

// 单条物流跟踪：按柜号+品牌查询 WMS 验收数据，回写三个时间字段后刷新
async function syncLogistics(row) {
  logisticsingId.value = row.id
  try {
    const res = await api.post(`/sync/logistics/${row.id}`)
    if (res.success) {
      ElMessage.success(t('container.logisticsOk', { n: Object.keys(res.fields || {}).length }))
      loadData()
    } else {
      ElMessage.warning(t('container.logisticsFail', { msg: res.message || '' }))
    }
  } catch (e) {
    // 拦截器已提示
  } finally {
    logisticsingId.value = null
  }
}

// 单条调用飞驼：先按提单号，失败按柜号+船公司+起运港，成功后刷新
async function syncRow(row) {
  syncingId.value = row.id
  try {
    const res = await api.post(`/sync/row/${row.id}`)
    if (res.success) {
      const mode = res.mode === 'containerNo' ? t('container.modeContainer') : t('container.modeBill')
      ElMessage.success(t('container.syncOk', { mode, n: Object.keys(res.fields || {}).length }))
      loadData()
    } else {
      ElMessage.warning(t('container.syncFail', { msg: res.message || '' }))
    }
  } catch (e) {
    // 拦截器已提示
  } finally {
    syncingId.value = null
  }
}

// 重置：把 flag 从100改回0，恢复自动同步
async function resetFlag(row) {
  resettingId.value = row.id
  try {
    const res = await api.post(`/containers/${row.id}/reset-flag`)
    if (res.changed) {
      ElMessage.success(t('container.resetOk'))
      loadData()
    } else {
      ElMessage.info(t('container.resetNoop'))
    }
  } catch (e) {
    // 拦截器已提示
  } finally {
    resettingId.value = null
  }
}

onMounted(() => {
  loadDict()
  loadData()
})

// 语言切换后重新加载字典（下拉 label 随语言变化）
watch(locale, () => { loadDict() })

async function loadDict() {
  const [b, f, s, w, pol, pod, c] = await Promise.all([
    api.get('/dict/brands'), api.get('/dict/forwarders'), api.get('/dict/ship-companies'),
    api.get('/dict/warehouses'), api.get('/dict/ports/pol'), api.get('/dict/ports/pod'),
    api.get('/dict/cargotypes'),
  ])
  dict.brands = b; dict.forwarders = f; dict.shipCompanies = s
  dict.warehouses = w; dict.pols = pol; dict.pods = pod; dict.cargotypes = c
}

async function loadData() {
  loading.value = true
  try {
    const params = {}
    Object.keys(filters).forEach(k => {
      if (filters[k] !== '' && filters[k] !== null && filters[k] !== undefined) params[k] = filters[k]
    })
    const res = await api.get('/containers', { params })
    rows.value = res.items
    total.value = res.total
  } finally {
    loading.value = false
  }
}

function resetFilters() {
  Object.assign(filters, {
    brand: '', forwarder: '', ship_co: '', bl: '', container_no: '', status: '', page: 1,
  })
  loadData()
}

function statusType(s) {
  return { '在途': 'primary', '延误': 'danger', '待提柜': 'warning', '已到港': 'success', '已完成': 'info' }[s] || 'info'
}

function openCreate() {
  editingId.value = null
  Object.keys(form).forEach(k => delete form[k])
  Object.assign(form, { cargotype: null })
  formVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, row)
  formVisible.value = true
}

async function submitForm() {
  if (!form.brand) { ElMessage.warning(t('container.needBrand')); return }
  if (!form.container_no) { ElMessage.warning(t('container.needContainerNo')); return }
  saving.value = true
  try {
    const payload = { ...form }
    delete payload.id; delete payload.brand_name; delete payload.status
    delete payload.delay_days; delete payload.createtime; delete payload.period
    delete payload.stspdate; delete payload.loaddate; delete payload.plandate
    delete payload.acdate; delete payload.stcsdate; delete payload.rcvedate
    delete payload.plan_days; delete payload.actual_days
    if (editingId.value) {
      await api.put(`/containers/${editingId.value}`, payload)
      ElMessage.success(t('container.editSuccess'))
    } else {
      await api.post('/containers', payload)
      ElMessage.success(t('container.createSuccess'))
    }
    formVisible.value = false
    loadData()
  } catch (e) {} finally {
    saving.value = false
  }
}

async function handleDelete(row) {
  try {
    await ElMessageBox.confirm(t('container.deleteConfirm', { no: row.container_no }), t('common.tip'), { type: 'warning' })
    await api.delete(`/containers/${row.id}`)
    ElMessage.success(t('container.deleteSuccess'))
    loadData()
  } catch (e) {}
}

function openImport() { importVisible.value = true }
function onFileChange(file) { importFile.value = file.raw }

async function submitImport() {
  if (!importFile.value) { ElMessage.warning(t('container.needFile')); return }
  importing.value = true
  try {
    const fd = new FormData()
    fd.append('file', importFile.value)
    const res = await api.post('/containers/import', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    ElMessage.success(t('container.importResult', {
      imported: res.imported, skipped_duplicate: res.skipped_duplicate, skipped_invalid: res.skipped_invalid,
    }))
    if (res.errors?.length) {
      ElMessageBox.alert(res.errors.slice(0, 20).join('\n'), t('container.importTip'), { type: 'warning' })
    }
    importVisible.value = false
    loadData()
  } finally {
    importing.value = false
  }
}

function downloadTemplate() {
  window.open('/container-template.xlsx', '_blank')
}
</script>

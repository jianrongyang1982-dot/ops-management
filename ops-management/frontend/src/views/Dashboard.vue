<template>
  <div class="dashboard" v-loading="loading">
    <div class="dashboard-title">{{ t('dashboard.title') }}</div>

    <!-- 顶部指标卡 -->
    <div class="stat-cards">
      <div class="stat-card">
        <div class="label">{{ t('dashboard.totalInTransit') }}</div>
        <div class="value">{{ cards.total_in_transit?.value ?? 0 }}</div>
        <div class="sub">{{ t('dashboard.vsYesterday') }} <span :class="(cards.total_in_transit?.change ?? 0) > 0 ? 'up' : 'down'">
          {{ (cards.total_in_transit?.change ?? 0) > 0 ? '+' : '' }}{{ cards.total_in_transit?.change ?? 0 }}
        </span></div>
      </div>
      <div class="stat-card">
        <div class="label">{{ t('dashboard.weekEta') }}</div>
        <div class="value">{{ cards.week_eta?.value ?? 0 }}</div>
        <div class="sub">{{ t('dashboard.arrived', { n: cards.week_eta?.arrived ?? 0 }) }} · {{ t('dashboard.remaining', { n: cards.week_eta?.remaining ?? 0 }) }}</div>
      </div>
      <div class="stat-card">
        <div class="label">{{ t('dashboard.monthEta') }}</div>
        <div class="value">{{ cards.month_eta?.value ?? 0 }}</div>
        <div class="sub">{{ t('dashboard.arrived', { n: cards.month_eta?.arrived ?? 0 }) }} · {{ t('dashboard.completionRate') }} {{ cards.month_eta?.rate ?? 0 }}%</div>
      </div>
      <div class="stat-card">
        <div class="label">{{ t('dashboard.overdue') }}</div>
        <div class="value" style="color:#f56c6c">{{ cards.overdue?.value ?? 0 }}</div>
        <div class="sub">{{ t('dashboard.avgDelay', { n: cards.overdue?.avg_delay ?? 0 }) }}</div>
      </div>
      <div class="stat-card">
        <div class="label">{{ t('dashboard.pendingPickup') }}</div>
        <div class="value" style="color:#e5c07b">{{ cards.pending_pickup?.value ?? 0 }}</div>
        <div class="sub">{{ t('dashboard.picked', { n: cards.pending_pickup?.picked ?? 0 }) }}</div>
      </div>
    </div>

    <!-- 明细表 + 右侧预警 -->
    <div class="dash-row two">
      <div class="dash-panel">
        <h3>{{ t('dashboard.detailTitle') }}</h3>
        <table class="dash-table">
          <thead>
            <tr>
              <th>{{ t('dashboard.colContainerNo') }}</th><th>{{ t('dashboard.colShipName') }}</th><th>{{ t('dashboard.colPol') }}</th><th>{{ t('dashboard.colPod') }}</th>
              <th>{{ t('dashboard.colEta') }}</th><th>{{ t('dashboard.colStatus') }}</th><th>{{ t('dashboard.colDelay') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(r, i) in detail" :key="i">
              <td style="font-family:monospace;color:#79bbff">{{ r.container_no }}</td>
              <td>{{ r.ship_name || '-' }}</td>
              <td>{{ r.pol || '-' }}</td>
              <td>{{ r.pod || '-' }}</td>
              <td>{{ r.eta || '-' }}</td>
              <td><span class="tag" :class="tagClass(r.status)">{{ statusText(r.status) }}</span></td>
              <td>{{ r.delay_days ? t('dashboard.days', { n: r.delay_days }) : '-' }}</td>
            </tr>
            <tr v-if="!detail.length"><td colspan="7" style="text-align:center;color:#8fa3bd">{{ t('common.noData') }}</td></tr>
          </tbody>
        </table>
      </div>
      <div class="dash-panel">
        <h3>{{ t('dashboard.weekDistribution') }}</h3>
        <div ref="weekChart" class="chart-box" style="height:160px"></div>
        <h3 style="margin-top:16px">{{ t('dashboard.alerts') }}</h3>
        <div v-for="(a, i) in alerts" :key="i" class="alert-item">
          <div><span class="no">{{ a.container_no }}</span>
            <span class="tag" :class="tagClass(a.status)" style="margin-left:8px">{{ statusText(a.status) }}</span>
          </div>
          <div class="desc">{{ a.status === '延误' ? t('dashboard.delayDesc', { n: a.delay_days }) : (a.pod || '') + ' ' + t('dashboard.pickupDesc') }}</div>
        </div>
        <div v-if="!alerts.length" style="color:#8fa3bd;font-size:12px">{{ t('dashboard.noAlerts') }}</div>
      </div>
    </div>

    <!-- 底部两图表 -->
    <div class="dash-row two-eq">
      <div class="dash-panel">
        <h3>{{ t('dashboard.trend30') }}</h3>
        <div ref="trendChart" class="chart-box"></div>
      </div>
      <div class="dash-panel">
        <h3>{{ t('dashboard.inTransit7') }}</h3>
        <div ref="inTransitChart" class="chart-box"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'
import api from '../api'
import { STATUS_KEY_MAP } from '../i18n'

const { t, locale } = useI18n()
const loading = ref(false)
const cards = ref({})
const detail = ref([])
const alerts = ref([])
const weekChart = ref()
const trendChart = ref()
const inTransitChart = ref()
let lastRes = null

function statusText(code) {
  const key = STATUS_KEY_MAP[code]
  return key ? t(key) : code
}

function tagClass(s) {
  return { '在途': 'tag-transit', '延误': 'tag-delay', '待提柜': 'tag-pickup', '已到港': 'tag-arrived', '已完成': 'tag-arrived' }[s] || 'tag-transit'
}

const axisStyle = {
  axisLine: { lineStyle: { color: '#3a4a63' } },
  axisLabel: { color: '#8fa3bd', fontSize: 11 },
  splitLine: { lineStyle: { color: '#1c2c44' } },
}

async function loadData() {
  loading.value = true
  try {
    const res = await api.get('/dashboard')
    lastRes = res
    cards.value = res.cards || {}
    detail.value = res.detail || []
    alerts.value = res.alerts || []
    await nextTick()
    renderCharts(res)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  [weekChart, trendChart, inTransitChart].forEach(r => {
    const inst = r.value && echarts.getInstanceByDom(r.value)
    if (inst) inst.resize()
  })
}

// 语言切换后重新渲染图表（周几、图例文案随语言变化）
watch(locale, async () => {
  await nextTick()
  if (lastRes) renderCharts(lastRes)
})

function renderCharts(res) {
  const weekdays = t('dashboard.weekdays')

  // 本周到货分布：后端按周一~周日固定顺序返回，用索引映射当前语言的星期缩写
  if (weekChart.value) {
    const wd = res.week_distribution || []
    echarts.init(weekChart.value, 'dark').setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 30, right: 10, top: 20, bottom: 25 },
      xAxis: { type: 'category', data: wd.map((d, i) => weekdays[i] || d.day), ...axisStyle },
      yAxis: { type: 'value', ...axisStyle },
      series: [{
        type: 'bar', data: wd.map(d => d.count), barWidth: '50%',
        itemStyle: { color: '#409eff', borderRadius: [4,4,0,0] },
      }],
    })
  }

  // 近30天趋势
  if (trendChart.value) {
    const td = res.trend || []
    echarts.init(trendChart.value, 'dark').setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      legend: { data: [t('dashboard.legendPlan'), t('dashboard.legendActual')], textStyle: { color: '#8fa3bd' }, top: 0 },
      grid: { left: 35, right: 15, top: 35, bottom: 25 },
      xAxis: { type: 'category', data: td.map(d => d.date.slice(5)), ...axisStyle },
      yAxis: { type: 'value', ...axisStyle },
      series: [
        { name: t('dashboard.legendPlan'), type: 'line', smooth: true, data: td.map(d => d.plan),
          lineStyle: { color: '#409eff' }, itemStyle: { color: '#409eff' }, showSymbol: false },
        { name: t('dashboard.legendActual'), type: 'line', smooth: true, data: td.map(d => d.actual),
          lineStyle: { color: '#67c23a' }, itemStyle: { color: '#67c23a' }, showSymbol: false },
      ],
    })
  }

  // 近7日在途
  if (inTransitChart.value) {
    const sd = res.in_transit_7days || []
    echarts.init(inTransitChart.value, 'dark').setOption({
      backgroundColor: 'transparent',
      tooltip: { trigger: 'axis' },
      grid: { left: 35, right: 15, top: 20, bottom: 25 },
      xAxis: { type: 'category', data: sd.map(d => d.date.slice(5)), ...axisStyle },
      yAxis: { type: 'value', ...axisStyle, minInterval: 1 },
      series: [{
        type: 'bar', data: sd.map(d => d.count), barWidth: '45%',
        itemStyle: { color: new echarts.graphic.LinearGradient(0,0,0,1,[
          { offset: 0, color: '#409eff' }, { offset: 1, color: '#1a3a5c' },
        ]), borderRadius: [4,4,0,0] },
      }],
    })
  }
}
</script>

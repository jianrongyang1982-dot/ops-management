<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="stat-row">
        <div class="stat-item"><span class="stat-label">{{ t('issue.all') }}</span><b>{{ counts['全部'] || 0 }}</b></div>
        <div class="stat-item"><span class="stat-label">{{ t('issue.pending') }}</span><b class="warn">{{ counts['待处理'] || 0 }}</b></div>
        <div class="stat-item"><span class="stat-label">{{ t('issue.processing') }}</span><b class="primary">{{ counts['处理中'] || 0 }}</b></div>
        <div class="stat-item"><span class="stat-label">{{ t('issue.verify') }}</span><b class="warn">{{ counts['待验证'] || 0 }}</b></div>
        <div class="stat-item"><span class="stat-label">{{ t('issue.closed') }}</span><b class="success">{{ counts['已关闭'] || 0 }}</b></div>
      </div>

      <div class="toolbar">
        <el-input v-model="keyword" :placeholder="t('issue.searchPlaceholder')" clearable style="width:260px" @keyup.enter="loadData" />
        <el-select v-model="status" clearable :placeholder="t('issue.status')" style="width:130px">
          <el-option v-for="s in [1,2,3,4,5,6]" :key="s" :label="statusName(s)" :value="s" />
        </el-select>
        <el-select v-model="issueType" clearable :placeholder="t('issue.type')" style="width:120px">
          <el-option :label="t('issue.requirement')" :value="1" />
          <el-option :label="t('issue.bug')" :value="2" />
        </el-select>
        <el-button type="primary" @click="loadData"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-button @click="reset"><el-icon><RefreshRight /></el-icon> {{ t('common.reset') }}</el-button>
        <el-button type="success" @click="goCreate"><el-icon><Plus /></el-icon> {{ t('issue.newIssue') }}</el-button>
      </div>

      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%" @row-dblclick="(r) => openDetail(r.id)">
          <el-table-column prop="issue_no" :label="t('issue.no')" min-width="150" sortable />
          <el-table-column prop="issue_type_name" :label="t('issue.type')" width="90" align="center">
            <template #default="{ row }">
              <el-tag :type="row.issue_type === 2 ? 'danger' : 'primary'" size="small">{{ row.issue_type_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" :label="t('issue.title')" min-width="220" show-overflow-tooltip />
          <el-table-column prop="module" :label="t('issue.module')" min-width="130" show-overflow-tooltip />
          <el-table-column prop="priority_name" :label="t('issue.priority')" width="90" align="center" sortable>
            <template #default="{ row }">
              <el-tag :type="priorityTag(row.priority)" size="small">{{ row.priority_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status_name" :label="t('issue.status')" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">{{ row.status_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="assignee_name" :label="t('issue.assignee')" min-width="140" show-overflow-tooltip />
          <el-table-column prop="created_time" :label="t('issue.createdTime')" min-width="160" sortable />
          <el-table-column :label="t('issue.action')" width="90" fixed="right" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openDetail(row.id)">{{ t('issue.view') }}</el-button>
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

  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { Search, RefreshRight, Plus } from '@element-plus/icons-vue'
import { useIssueList } from '../composables/useIssueList'

const list = useIssueList('my')
const { t, rows, total, page, pageSize, loading, keyword, status, issueType, priority,
  counts, role, loadData, reset, openDetail, onChanged } = list

const router = useRouter()
function goCreate() { router.push('/issue/create') }

function statusName(s) {
  return { 1: t('issue.pending'), 2: t('issue.assigned'), 3: t('issue.processing'),
    4: t('issue.verify'), 5: t('issue.closed'), 6: t('issue.cancelled') }[s] || ''
}
function priorityTag(p) { return { 1: 'danger', 2: 'warning', 3: 'primary', 4: 'info' }[p] || 'info' }
function statusTag(s) { return { 1: 'warning', 2: 'primary', 3: 'primary', 4: 'warning', 5: 'success', 6: 'info' }[s] || 'info' }
</script>

<style scoped>
.stat-row { display: flex; gap: 12px; margin-bottom: 14px; }
.stat-item { flex: 1; background: #f8fafc; border: 1px solid #ebeef5; border-radius: 8px; padding: 10px 14px; display: flex; flex-direction: column; gap: 4px; }
.stat-label { color: #909399; font-size: 12px; }
.stat-item b { font-size: 20px; font-weight: 500; color: #303133; }
.stat-item b.warn { color: #e6a23c; }
.stat-item b.primary { color: #409eff; }
.stat-item b.success { color: #67c23a; }
</style>

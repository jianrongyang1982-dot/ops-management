<template>
  <div class="list-page">
    <div class="list-page-card">
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
      </div>

      <div class="table-flex">
        <el-table :data="rows" v-loading="loading" border stripe size="small" height="100%" @row-dblclick="(r) => openDetail(r.id)">
          <el-table-column prop="issue_no" :label="t('issue.no')" min-width="150" sortable />
          <el-table-column prop="issue_type_name" :label="t('issue.type')" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="row.issue_type === 2 ? 'danger' : 'primary'" size="small">{{ row.issue_type_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="title" :label="t('issue.title')" min-width="220" show-overflow-tooltip />
          <el-table-column prop="reporter_name" :label="t('issue.reporter')" min-width="130" show-overflow-tooltip />
          <el-table-column prop="priority_name" :label="t('issue.priority')" width="80" align="center">
            <template #default="{ row }">
              <el-tag :type="priorityTag(row.priority)" size="small">{{ row.priority_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status_name" :label="t('issue.status')" width="100" align="center">
            <template #default="{ row }">
              <el-tag :type="statusTag(row.status)" size="small">{{ row.status_name }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="assigned_time" :label="t('issue.assignedTime')" min-width="155" sortable />
          <el-table-column prop="created_time" :label="t('issue.createdTime')" min-width="155" sortable />
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
import { Search, RefreshRight } from '@element-plus/icons-vue'
import { useIssueList } from '../composables/useIssueList'

const { t, rows, total, page, pageSize, loading, keyword, status, issueType,
  role, loadData, reset, openDetail, onChanged } = useIssueList('assigned')

function statusName(s) {
  return { 1: t('issue.pending'), 2: t('issue.assigned'), 3: t('issue.processing'),
    4: t('issue.verify'), 5: t('issue.closed'), 6: t('issue.cancelled') }[s] || ''
}
function priorityTag(p) { return { 1: 'danger', 2: 'warning', 3: 'primary', 4: 'info' }[p] || 'info' }
function statusTag(s) { return { 1: 'warning', 2: 'primary', 3: 'primary', 4: 'warning', 5: 'success', 6: 'info' }[s] || 'info' }
</script>

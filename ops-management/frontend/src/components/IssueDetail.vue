<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('issue.detailTitle')"
    width="860px"
    top="4vh"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-loading="loading" class="detail-wrap">
      <template v-if="detail">
        <!-- 基本信息 -->
        <el-descriptions :column="3" border size="small" class="desc">
          <el-descriptions-item :label="t('issue.no')">{{ detail.issue_no }}</el-descriptions-item>
          <el-descriptions-item :label="t('issue.type')">
            <el-tag :type="detail.issue_type === 2 ? 'danger' : 'primary'" size="small">
              {{ detail.issue_type === 2 ? t('issue.bug') : t('issue.requirement') }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('issue.priority')">
            <el-tag :type="priorityTag(detail.priority)" size="small">{{ detail.priority_name }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('issue.status')">
            <el-tag :type="statusTag(detail.status)" size="small">{{ detail.status_name }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.issue_type === 2" :label="t('issue.module')">{{ detail.module || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('issue.reporter')">{{ detail.reporter_name }} ({{ detail.reporter }})</el-descriptions-item>
          <el-descriptions-item :label="t('issue.assignee')">{{ detail.assignee_name ? detail.assignee_name + ' (' + detail.assignee + ')' : '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('issue.assignedTime')">{{ detail.assigned_time || '-' }}</el-descriptions-item>
          <el-descriptions-item :label="t('issue.createdTime')">{{ detail.created_time }}</el-descriptions-item>
          <el-descriptions-item :label="t('issue.closedTime')">{{ detail.closed_time || '-' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.issue_type === 2" :label="t('issue.title')" :span="3">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.issue_type === 2" :label="t('issue.description')" :span="3">
            <div class="desc-text">{{ detail.description || '-' }}</div>
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.close_remark" :label="t('issue.closeRemark')" :span="3">
            {{ detail.close_remark }}
          </el-descriptions-item>
        </el-descriptions>

        <!-- 需求：标准需求申请单字段 -->
        <template v-if="detail.issue_type === 1 && detail.requirement">
          <div class="section-title">{{ t('issue.businessRequirement') }}</div>
          <el-descriptions :column="1" border size="small" class="desc req-desc">
            <el-descriptions-item :label="t('issue.affectedModules')">{{ detail.module || '-' }}</el-descriptions-item>
            <el-descriptions-item :label="t('issue.requestTitle')">{{ detail.title || '-' }}</el-descriptions-item>
            <el-descriptions-item :label="t('issue.background')">
              <div class="desc-text">{{ detail.requirement.background || '-' }}</div>
            </el-descriptions-item>
            <el-descriptions-item :label="t('issue.painPoints')">
              <div class="desc-text">{{ detail.requirement.pain_points || '-' }}</div>
            </el-descriptions-item>
            <el-descriptions-item :label="t('issue.scenario5w1h')">
              <div class="desc-text">{{ detail.requirement.scenario_5w1h || '-' }}</div>
            </el-descriptions-item>
            <el-descriptions-item :label="t('issue.detailedRequirement')">
              <div class="desc-text">{{ detail.requirement.detailed_description || '-' }}</div>
            </el-descriptions-item>
            <el-descriptions-item :label="t('issue.rolesInvolved')">{{ detail.requirement.roles || '-' }}</el-descriptions-item>
            <el-descriptions-item :label="t('issue.proposedSolution')">
              <div class="desc-text">{{ detail.requirement.proposed_solution || '-' }}</div>
            </el-descriptions-item>
          </el-descriptions>
        </template>

        <!-- 附件 -->
        <div class="section-title">{{ t('issue.attachments') }} ({{ detail.attachments.length }})</div>
        <div v-if="detail.attachments.length" class="attach-list">
          <el-link v-for="a in detail.attachments" :key="a.id" type="primary" @click="download(a.id, a.file_name)">
            <el-icon><Paperclip /></el-icon> {{ a.file_name }}
          </el-link>
        </div>
        <div v-else class="empty-hint">{{ t('issue.noAttachments') }}</div>
        <div class="upload-row">
          <el-upload
            :action="uploadUrl"
            :data="{ issue_id: detail.id }"
            :headers="uploadHeaders"
            :show-file-list="false"
            :on-success="onUploaded"
            :on-error="onUploadError"
          >
            <el-button size="small" plain><el-icon><Upload /></el-icon> {{ t('issue.upload') }}</el-button>
          </el-upload>
          <span class="upload-tip">{{ t('issue.uploadTip') }}</span>
        </div>

        <!-- 流转时间线 -->
        <div class="section-title">{{ t('issue.timeline') }}</div>
        <el-timeline class="timeline">
          <el-timeline-item
            v-for="(l, i) in detail.logs"
            :key="i"
            :timestamp="l.created_time"
            placement="top"
            :type="l.action === 'reject' ? 'danger' : l.action === 'verify' ? 'success' : 'primary'"
          >
            <b>{{ l.action_name }}</b> <span class="op">— {{ l.operator_name || l.operator }}</span>
            <div v-if="l.content" class="log-content">{{ l.content }}</div>
          </el-timeline-item>
        </el-timeline>

        <!-- 操作区 -->
        <div v-if="canOperate" class="op-area">
          <div class="section-title">{{ t('issue.action') }}</div>
          <div v-if="isItAdmin && [1,2,3].includes(detail.status)" class="op-row">
            <el-select v-model="assignee" :placeholder="t('issue.selectHandler')" style="width:260px" filterable clearable>
              <el-option v-for="h in handlers" :key="h.usercode" :label="h.accountname || h.usercode" :value="h.usercode" />
            </el-select>
            <el-button type="primary" :loading="acting" @click="doAction('assign')">{{ t('issue.assign') }}</el-button>
          </div>
          <div v-if="isAssignee && detail.status === 2" class="op-row">
            <el-button type="primary" :loading="acting" @click="doAction('start')">{{ t('issue.start') }}</el-button>
          </div>
          <div v-if="isAssignee && detail.status === 3" class="op-row op-col">
            <el-input v-model="opContent" type="textarea" :rows="2" :placeholder="t('issue.processPlaceholder')" />
            <el-button type="primary" :loading="acting" @click="doAction('process')">{{ t('issue.submitResult') }}</el-button>
          </div>
          <div v-if="isReporter && detail.status === 4" class="op-row op-col">
            <el-input v-model="opContent" type="textarea" :rows="2" :placeholder="t('issue.verifyPlaceholder')" />
            <div class="btn-row">
              <el-button type="success" :loading="acting" @click="doAction('verify', true)">{{ t('issue.pass') }}</el-button>
              <el-button type="danger" plain :loading="acting" @click="doAction('verify', false)">{{ t('issue.reject') }}</el-button>
            </div>
          </div>
          <div v-if="isReporter && [1,2].includes(detail.status)" class="op-row op-col">
            <el-input v-model="opContent" type="textarea" :rows="2" :placeholder="t('issue.cancelPlaceholder')" />
            <el-button type="warning" plain :loading="acting" @click="doAction('cancel')">{{ t('issue.cancel') }}</el-button>
          </div>
          <div v-if="isItAdmin && ![5,6].includes(detail.status)" class="op-row op-col">
            <el-input v-model="opContent" type="textarea" :rows="2" :placeholder="t('issue.forceClosePlaceholder')" />
            <el-button type="danger" :loading="acting" @click="doAction('force-close')">{{ t('issue.forceClose') }}</el-button>
          </div>
        </div>
      </template>
    </div>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Paperclip, Upload } from '@element-plus/icons-vue'
import api from '../api'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  issueId: { type: Number, default: 0 },
  role: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:modelValue', 'changed'])
const { t } = useI18n()

const loading = ref(false)
const acting = ref(false)
const detail = ref(null)
const assignee = ref('')
const opContent = ref('')
const handlers = ref([])

const isItAdmin = computed(() => !!props.role?.is_it_admin)
const isAssignee = computed(() => !!detail.value?.assignee && detail.value.assignee === props.role?.usercode)
const isReporter = computed(() => !!detail.value?.reporter && detail.value.reporter === props.role?.usercode)
const canOperate = computed(() => {
  if (!detail.value) return false
  if ([5, 6].includes(detail.value.status)) return false
  return isItAdmin.value || isAssignee.value || isReporter.value
})

const uploadUrl = computed(() => `/api/issue/upload`)
const uploadHeaders = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('token') || ''}` }))
async function download(id, name) {
  try {
    const res = await fetch(`/api/issue/attachment/${id}/download`, {
      headers: { Authorization: `Bearer ${localStorage.getItem('token') || ''}` },
    })
    if (!res.ok) throw new Error('download failed')
    const blob = await res.blob()
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = name || 'attachment'
    a.click()
    URL.revokeObjectURL(a.href)
  } catch (e) { ElMessage.error(t('issue.downloadFailed')) }
}
function priorityTag(p) { return { 1: 'danger', 2: 'warning', 3: 'primary', 4: 'info' }[p] || 'info' }
function statusTag(s) { return { 1: 'warning', 2: 'primary', 3: 'primary', 4: 'warning', 5: 'success', 6: 'info' }[s] || 'info' }

watch(() => props.modelValue, async (v) => {
  if (v && props.issueId) {
    await load()
  }
})
watch(() => props.issueId, async (v) => {
  if (props.modelValue && v) await load()
})

async function load() {
  loading.value = true
  try {
    detail.value = await api.get(`/issue/${props.issueId}`)
    opContent.value = ''
    assignee.value = detail.value.assignee || ''
    if (props.role?.is_it_admin) await loadHandlers()
  } catch (e) {
    detail.value = null
  } finally {
    loading.value = false
  }
}

async function loadHandlers() {
  if (handlers.value.length) return
  try {
    const res = await api.get('/issue/handlers')
    handlers.value = res.items || []
  } catch (e) { /* ignore */ }
}

async function doAction(action, passed) {
  if (action === 'assign' && !assignee.value) {
    ElMessage.warning(t('issue.selectHandler'))
    return
  }
  if ((action === 'process' || (action === 'verify' && passed === false)) && !opContent.value.trim()) {
    ElMessage.warning(t('issue.contentRequired'))
    return
  }
  acting.value = true
  try {
    const body = { content: opContent.value }
    if (action === 'assign') body.assignee = assignee.value
    if (action === 'verify') { body.passed = passed; body.remark = opContent.value }
    if (action === 'cancel' || action === 'force-close') body.remark = opContent.value

    const pathMap = {
      assign: `/issue/${detail.value.id}/assign`, start: `/issue/${detail.value.id}/start`,
      process: `/issue/${detail.value.id}/process`, verify: `/issue/${detail.value.id}/verify`,
      cancel: `/issue/${detail.value.id}/cancel`, 'force-close': `/issue/${detail.value.id}/force-close`,
    }
    const res = await api.post(pathMap[action], body)
    ElMessage.success(res.message || t('issue.actionDone'))
    emit('changed')
    await load()
  } finally { acting.value = false }
}

async function onUploaded() {
  ElMessage.success(t('issue.uploaded'))
  await load()
  emit('changed')
}
function onUploadError() { ElMessage.error(t('issue.uploadFailed')) }
</script>

<style scoped>
.detail-wrap { max-height: 72vh; overflow-y: auto; padding-right: 4px; }
.desc { margin-bottom: 18px; }
.desc-text { white-space: pre-wrap; line-height: 1.6; }
.req-desc :deep(.el-descriptions__label) { width: 260px; min-width: 260px; vertical-align: top; }
.req-desc :deep(.el-descriptions__content) { white-space: pre-wrap; }
.section-title { font-weight: 500; font-size: 13px; margin: 16px 0 10px; color: #303133; }
.attach-list { display: flex; flex-wrap: wrap; gap: 12px; }
.empty-hint { color: #909399; font-size: 12px; }
.upload-row { display: flex; align-items: center; gap: 12px; margin-top: 10px; }
.upload-tip { color: #909399; font-size: 12px; }
.timeline { padding-left: 4px; max-height: 220px; overflow-y: auto; }
.op { color: #909399; font-size: 12px; }
.log-content { color: #606266; font-size: 12px; margin-top: 4px; white-space: pre-wrap; }
.op-area { border-top: 1px solid #ebeef5; padding-top: 4px; margin-top: 16px; }
.op-row { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
.op-col { flex-direction: column; align-items: stretch; }
.btn-row { display: flex; gap: 10px; }
</style>

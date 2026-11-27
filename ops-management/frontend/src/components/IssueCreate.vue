<template>
  <el-dialog
    :model-value="modelValue"
    :title="t('issue.createTitle')"
    width="820px"
    top="3vh"
    destroy-on-close
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="215px">
      <el-form-item :label="t('issue.type')" prop="issue_type">
        <el-radio-group v-model="form.issue_type">
          <el-radio :value="1">{{ t('issue.requirement') }}</el-radio>
          <el-radio :value="2">{{ t('issue.bug') }}</el-radio>
        </el-radio-group>
      </el-form-item>

      <!-- ============ 需求：按标准需求申请单模板 ============ -->
      <template v-if="form.issue_type === 1">
        <el-form-item :label="t('issue.affectedModules')" prop="module">
          <el-input v-model="form.module" maxlength="200"
            :placeholder="t('issue.modulePlaceholder')" />
        </el-form-item>

        <div class="form-section-title">{{ t('issue.businessRequirement') }}</div>

        <el-form-item :label="t('issue.requestTitle')" prop="title">
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>

        <el-form-item :label="t('issue.background')" prop="requirement.background">
          <el-input v-model="form.requirement.background" type="textarea" :rows="3"
            maxlength="10000" show-word-limit />
        </el-form-item>

        <el-form-item :label="t('issue.painPoints')" prop="requirement.pain_points">
          <el-input v-model="form.requirement.pain_points" type="textarea" :rows="3"
            maxlength="10000" show-word-limit />
        </el-form-item>

        <el-form-item :label="t('issue.scenario5w1h')" prop="requirement.scenario_5w1h">
          <el-input v-model="form.requirement.scenario_5w1h" type="textarea" :rows="3"
            maxlength="10000" show-word-limit />
        </el-form-item>

        <el-form-item :label="t('issue.detailedRequirement')" prop="requirement.detailed_description">
          <el-input v-model="form.requirement.detailed_description" type="textarea" :rows="5"
            maxlength="20000" show-word-limit />
        </el-form-item>

        <el-form-item :label="t('issue.rolesInvolved')" prop="requirement.roles">
          <el-input v-model="form.requirement.roles" maxlength="500"
            :placeholder="t('issue.rolesPlaceholder')" />
        </el-form-item>

        <el-form-item :label="t('issue.proposedSolution')">
          <el-input v-model="form.requirement.proposed_solution" type="textarea" :rows="4"
            maxlength="10000" show-word-limit />
        </el-form-item>
      </template>

      <!-- ============ BUG：保持原有简单表单 ============ -->
      <template v-else>
        <el-form-item :label="t('issue.title')" prop="title">
          <el-input v-model="form.title" maxlength="200" show-word-limit />
        </el-form-item>
        <el-form-item :label="t('issue.module')">
          <el-input v-model="form.module" maxlength="100" :placeholder="t('issue.modulePlaceholder')" />
        </el-form-item>
        <el-form-item :label="t('issue.description')" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="5" maxlength="10000" show-word-limit
            :placeholder="t('issue.descriptionPlaceholder')" />
        </el-form-item>
      </template>

      <el-form-item :label="t('issue.priority')" prop="priority">
        <el-select v-model="form.priority" style="width:100%">
          <el-option v-for="p in [1,2,3,4]" :key="p" :label="priorityName(p)" :value="p" />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('issue.relatedAttachments')">
        <el-upload
          v-model:file-list="fileList"
          :auto-upload="false"
          multiple
          :limit="10"
          :on-exceed="onExceed"
        >
          <el-button size="small" plain><el-icon><Upload /></el-icon> {{ t('issue.chooseFiles') }}</el-button>
          <template #tip><div class="el-upload__tip">{{ t('issue.uploadTip') }}</div></template>
        </el-upload>
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="$emit('update:modelValue', false)">{{ t('common.cancel') }}</el-button>
      <el-button type="primary" :loading="saving" @click="submit">{{ t('common.save') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Upload } from '@element-plus/icons-vue'
import api from '../api'

const emit = defineEmits(['update:modelValue', 'created'])
const { t } = useI18n()

const formRef = ref(null)
const saving = ref(false)
const fileList = ref([])

const emptyRequirement = () => ({
  background: '',
  pain_points: '',
  scenario_5w1h: '',
  detailed_description: '',
  roles: '',
  proposed_solution: '',
})
const form = ref({
  issue_type: 1,
  title: '',
  module: '',
  priority: 3,
  description: '',
  requirement: emptyRequirement(),
})

// 需求必填：涉及模块、需求名称、背景、痛点、5W1H、详细需求、业务场景角色
// BUG 必填：标题、描述（模块沿用原来的非必填）
const rules = computed(() => {
  const r = {
    title: [{ required: true, message: t('issue.titleRequired'), trigger: 'blur' }],
  }
  if (form.value.issue_type === 1) {
    r.module = [{ required: true, message: t('issue.moduleRequired'), trigger: 'blur' }]
    r['requirement.background'] = [{ required: true, message: t('issue.fieldRequired'), trigger: 'blur' }]
    r['requirement.pain_points'] = [{ required: true, message: t('issue.fieldRequired'), trigger: 'blur' }]
    r['requirement.scenario_5w1h'] = [{ required: true, message: t('issue.fieldRequired'), trigger: 'blur' }]
    r['requirement.detailed_description'] = [{ required: true, message: t('issue.fieldRequired'), trigger: 'blur' }]
    r['requirement.roles'] = [{ required: true, message: t('issue.fieldRequired'), trigger: 'blur' }]
  } else {
    r.description = [{ required: true, message: t('issue.descRequired'), trigger: 'blur' }]
  }
  return r
})

// 切换类型时清掉上一套表单的校验提示
watch(() => form.value.issue_type, () => formRef.value?.clearValidate())

function priorityName(p) { return t(`issue.p${p}`) }
function onExceed() { ElMessage.warning(t('issue.fileLimit')) }

function reset() {
  form.value = { issue_type: 1, title: '', module: '', priority: 3, description: '', requirement: emptyRequirement() }
  fileList.value = []
  formRef.value?.clearValidate()
}

async function submit() {
  const ok = await formRef.value.validate().catch(() => false)
  if (!ok) return

  // 前端先校验附件类型与大小，减少无效请求
  const allowed = /\.(png|jpe?g|gif|pdf|docx?|xlsx?|txt|zip)$/i
  for (const f of fileList.value) {
    const raw = f.raw || f
    if (!allowed.test(raw.name || '')) {
      ElMessage.warning(t('issue.badFileType', { name: raw.name }))
      return
    }
    if (raw.size > 10 * 1024 * 1024) {
      ElMessage.warning(t('issue.fileTooLarge', { name: raw.name }))
      return
    }
  }

  saving.value = true
  try {
    const fd = new FormData()
    fd.append('title', form.value.title)
    fd.append('description', form.value.description || '')
    fd.append('issue_type', String(form.value.issue_type))
    fd.append('module', form.value.module || '')
    fd.append('priority', String(form.value.priority))
    if (form.value.issue_type === 1) {
      fd.append('requirement_json', JSON.stringify(form.value.requirement))
    }
    for (const f of fileList.value) {
      const raw = f.raw || f
      fd.append('files', raw, raw.name)
    }
    const res = await api.post('/issue/create-with-files', fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    ElMessage.success(t('issue.created', { no: res.issue_no }))
    emit('created')
    emit('update:modelValue', false)
    reset()
  } finally { saving.value = false }
}
</script>

<style scoped>
.form-section-title {
  font-weight: 600;
  font-size: 14px;
  color: #303133;
  border-left: 3px solid #409eff;
  padding-left: 8px;
  margin: 6px 0 14px 0;
}
</style>

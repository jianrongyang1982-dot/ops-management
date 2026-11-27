<template>
  <div class="list-page">
    <div class="list-page-card">
      <div class="toolbar">
        <el-input v-model="keyword" :placeholder="t('issue.postSearch')" clearable style="width:240px" @keyup.enter="loadPosts" />
        <el-button type="primary" @click="loadPosts"><el-icon><Search /></el-icon> {{ t('common.search') }}</el-button>
        <el-alert :title="t('issue.roleTip')" type="info" :closable="false" class="role-tip" />
      </div>

      <div class="roles-grid">
        <div class="role-col">
          <div class="col-title">{{ t('issue.erpPosts') }}</div>
          <el-table :data="posts" v-loading="postsLoading" border size="small" height="100%">
            <el-table-column prop="postcode" :label="t('issue.postcode')" width="100" />
            <el-table-column prop="postname" :label="t('issue.postname')" min-width="150" show-overflow-tooltip />
            <el-table-column prop="user_count" :label="t('issue.userCount')" width="80" align="center" />
            <el-table-column :label="t('issue.action')" width="180" align="center">
              <template #default="{ row }">
                <el-button link type="primary" size="small" @click="addCfg(row, 'IT_ADMIN')">{{ t('issue.setItAdmin') }}</el-button>
                <el-button link type="success" size="small" @click="addCfg(row, 'HANDLER')">{{ t('issue.setHandler') }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="role-col">
          <div class="col-title">{{ t('issue.configuredRoles') }}</div>
          <el-table :data="configs" v-loading="cfgLoading" border size="small" height="100%">
            <el-table-column prop="postcode" :label="t('issue.postcode')" width="90" />
            <el-table-column prop="postname" :label="t('issue.postname')" min-width="130" show-overflow-tooltip />
            <el-table-column :label="t('issue.role')" width="120" align="center">
              <template #default="{ row }">
                <el-tag :type="row.role === 'IT_ADMIN' ? 'warning' : 'success'" size="small">
                  {{ row.role === 'IT_ADMIN' ? t('issue.itAdmin') : t('issue.handler') }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('issue.action')" width="80" align="center">
              <template #default="{ row }">
                <el-button link type="danger" size="small" @click="delCfg(row)">{{ t('common.delete') }}</el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
import api from '../api'

const { t } = useI18n()
const keyword = ref('')
const posts = ref([])
const configs = ref([])
const postsLoading = ref(false)
const cfgLoading = ref(false)

async function loadPosts() {
  postsLoading.value = true
  try {
    const res = await api.get('/issue/roles/erp-posts', { params: { keyword: keyword.value || undefined } })
    posts.value = res.items || []
  } catch (e) { posts.value = [] } finally { postsLoading.value = false }
}

async function loadConfigs() {
  cfgLoading.value = true
  try {
    const res = await api.get('/issue/roles')
    configs.value = res.items || []
  } catch (e) { configs.value = [] } finally { cfgLoading.value = false }
}

async function addCfg(row, role) {
  try {
    await api.post('/issue/roles', { postcode: row.postcode, postname: row.postname, role })
    ElMessage.success(t('issue.roleAdded'))
    await loadConfigs()
  } catch (e) { /* 拦截器已提示 */ }
}

async function delCfg(row) {
  await ElMessageBox.confirm(t('issue.roleDeleteConfirm', { post: row.postcode }), t('common.tip'), { type: 'warning' })
  await api.delete(`/issue/roles/${row.id}`)
  ElMessage.success(t('issue.roleDeleted'))
  await loadConfigs()
}

onMounted(() => { loadPosts(); loadConfigs() })
</script>

<style scoped>
.role-tip { flex: 1; margin-left: 12px; }
.roles-grid { display: flex; gap: 16px; flex: 1; min-height: 0; }
.role-col { flex: 1; display: flex; flex-direction: column; min-height: 0; }
.col-title { font-weight: 500; font-size: 13px; margin-bottom: 10px; color: #303133; }
</style>

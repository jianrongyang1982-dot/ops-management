<template>
  <div class="perm-page" v-loading="loading">
    <el-tabs v-model="tab">
      <el-tab-pane :label="t('perm.roleTab')" name="role">
        <div class="toolbar">
          <el-button type="primary" size="small" @click="openRole()">{{ t('perm.addRole') }}</el-button>
        </div>
        <el-table :data="roles" size="small" border stripe>
          <el-table-column prop="role_code" :label="t('perm.roleCode')" width="150" />
          <el-table-column :label="t('perm.roleName')" min-width="180">
            <template #default="{ row }">{{ locale === 'zhCN' ? row.role_name : (row.role_name_en || row.role_name) }}</template>
          </el-table-column>
          <el-table-column prop="remark" :label="t('perm.remark')" min-width="200" />
          <el-table-column :label="t('perm.admin')" width="100" align="center">
            <template #default="{ row }"><el-tag v-if="row.is_admin" type="warning" size="small">{{ t('common.yes') }}</el-tag><span v-else>-</span></template>
          </el-table-column>
          <el-table-column prop="menu_count" :label="t('perm.menuCount')" width="100" align="center" />
          <el-table-column prop="user_count" :label="t('perm.userCount')" width="100" align="center" />
          <el-table-column :label="t('common.action')" width="230" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openRoleMenus(row)">{{ t('perm.configMenu') }}</el-button>
              <el-button link type="primary" size="small" @click="openRole(row)">{{ t('common.edit') }}</el-button>
              <el-button link type="danger" size="small" @click="delRole(row)">{{ t('common.delete') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane :label="t('perm.userTab')" name="user">
        <div class="toolbar">
          <el-input v-model="userKw" size="small" :placeholder="t('perm.userSearch')" style="width:260px" clearable @keyup.enter="loadUsers" />
          <el-button size="small" @click="loadUsers">{{ t('common.search') }}</el-button>
          <el-button size="small" type="primary" @click="openUser()">{{ t('perm.assignRole') }}</el-button>
        </div>
        <el-table :data="users" size="small" border stripe>
          <el-table-column prop="usercode" :label="t('perm.usercode')" width="180" />
          <el-table-column prop="accountname" :label="t('perm.username')" min-width="200" />
          <el-table-column :label="t('perm.roles')" min-width="260">
            <template #default="{ row }">
              <el-tag v-for="r in row.roles" :key="r" size="small" class="role-tag">{{ roleName(r) }}</el-tag>
              <span v-if="!row.roles.length">-</span>
            </template>
          </el-table-column>
          <el-table-column :label="t('common.action')" width="120" align="center">
            <template #default="{ row }">
              <el-button link type="primary" size="small" @click="openUser(row)">{{ t('perm.assignRole') }}</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-pagination class="pager" small layout="total, prev, pager, next" :total="userTotal" v-model:current-page="userPage" :page-size="20" @current-change="loadUsers" />
      </el-tab-pane>
    </el-tabs>

    <!-- 角色编辑 -->
    <el-dialog v-model="roleVisible" :title="roleForm.id ? t('perm.editRole') : t('perm.addRole')" width="520px" destroy-on-close>
      <el-form :model="roleForm" label-width="120px" size="small">
        <el-form-item :label="t('perm.roleCode')" required><el-input v-model="roleForm.role_code" :disabled="!!roleForm.id" /></el-form-item>
        <el-form-item :label="t('perm.roleName')" required><el-input v-model="roleForm.role_name" /></el-form-item>
        <el-form-item :label="t('perm.roleNameEn')"><el-input v-model="roleForm.role_name_en" /></el-form-item>
        <el-form-item :label="t('perm.remark')"><el-input v-model="roleForm.remark" type="textarea" :rows="2" /></el-form-item>
        <el-form-item :label="t('perm.admin')"><el-switch v-model="roleForm.is_admin" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveRole">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 角色菜单授权 -->
    <el-dialog v-model="menuVisible" :title="t('perm.configMenuFor') + ' ' + currentRoleName" width="760px" top="8vh" destroy-on-close>
      <div v-loading="menuLoading" class="menu-tree">
        <div v-for="g in menuGroups" :key="g.code" class="menu-group">
          <div class="menu-group-title">{{ locale === 'zhCN' ? g.name : (g.name_en || g.name) }}</div>
          <div class="menu-items">
            <el-checkbox v-for="m in g.menus" :key="m.code" v-model="menuChecked[m.code]" class="menu-check">
              {{ locale === 'zhCN' ? m.name : (m.name_en || m.name) }}
            </el-checkbox>
          </div>
        </div>
      </div>
      <template #footer>
        <el-button @click="menuVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveRoleMenus">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>

    <!-- 员工角色分配 -->
    <el-dialog v-model="userVisible" :title="t('perm.assignRoleFor') + ' ' + userForm.usercode" width="480px" destroy-on-close>
      <el-form label-width="100px" size="small">
        <el-form-item :label="t('perm.usercode')" required><el-input v-model="userForm.usercode" :disabled="!!userForm._edit" /></el-form-item>
        <el-form-item :label="t('perm.roles')">
          <el-checkbox-group v-model="userForm.role_codes">
            <el-checkbox v-for="r in roles" :key="r.role_code" :value="r.role_code">{{ roleName(r) }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="userVisible=false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="saving" @click="saveUserRoles">{{ t('common.save') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import api from '../api'

const { t, locale } = useI18n()
const loading = ref(false)
const saving = ref(false)
const tab = ref('role')
const roles = ref([])

const roleVisible = ref(false)
const roleForm = ref({ id: null, role_code: '', role_name: '', role_name_en: '', remark: '', is_admin: false, status: 1 })

const menuVisible = ref(false)
const menuLoading = ref(false)
const menuGroups = ref([])
const menuChecked = ref({})
const currentRole = ref('')

const users = ref([])
const userTotal = ref(0)
const userPage = ref(1)
const userKw = ref('')
const userVisible = ref(false)
const userForm = ref({ usercode: '', role_codes: [], _edit: false })

const currentRoleName = computed(() => {
  const r = roles.value.find((x) => x.role_code === currentRole.value)
  return r ? (locale.value === 'zhCN' ? r.role_name : (r.role_name_en || r.role_name)) : currentRole.value
})

function roleName(code) {
  const r = roles.value.find((x) => x.role_code === code)
  return r ? (locale.value === 'zhCN' ? r.role_name : (r.role_name_en || r.role_name)) : code
}

async function loadRoles() {
  loading.value = true
  try {
    const res = await api.get('/menu/roles')
    roles.value = res.items || []
  } finally { loading.value = false }
}

async function loadUsers() {
  loading.value = true
  try {
    const res = await api.get('/menu/users', { params: { keyword: userKw.value, page: userPage.value, page_size: 20 } })
    users.value = res.items || []
    userTotal.value = res.total || 0
  } finally { loading.value = false }
}

function openRole(row) {
  roleForm.value = row
    ? { ...row }
    : { id: null, role_code: '', role_name: '', role_name_en: '', remark: '', is_admin: false, status: 1 }
  roleVisible.value = true
}

async function saveRole() {
  saving.value = true
  try {
    const f = roleForm.value
    if (f.id) {
      await api.put(`/menu/roles/${f.id}`, f)
    } else {
      await api.post('/menu/roles', f)
    }
    ElMessage.success(t('common.saved'))
    roleVisible.value = false
    await loadRoles()
  } finally { saving.value = false }
}

async function delRole(row) {
  await ElMessageBox.confirm(t('perm.deleteConfirm', { name: row.role_name }), t('common.tip'), { type: 'warning' })
  await api.delete(`/menu/roles/${row.id}`)
  ElMessage.success(t('common.deleted'))
  await loadRoles()
}

async function openRoleMenus(row) {
  currentRole.value = row.role_code
  menuVisible.value = true
  menuLoading.value = true
  try {
    const [menuRes, checkedRes] = await Promise.all([
      api.get('/menu/my-menus'),
      api.get('/menu/role-menus', { params: { role_code: row.role_code } }),
    ])
    menuGroups.value = menuRes.groups || []
    const set = new Set(checkedRes.items || [])
    menuChecked.value = {}
    menuGroups.value.forEach((g) => g.menus.forEach((m) => { menuChecked.value[m.code] = set.has(m.code) }))
  } catch (e) {
    menuGroups.value = []
  } finally { menuLoading.value = false }
}

async function saveRoleMenus() {
  saving.value = true
  try {
    const codes = Object.keys(menuChecked.value).filter((c) => menuChecked.value[c])
    await api.post('/menu/role-menus', { role_code: currentRole.value, menu_codes: codes })
    ElMessage.success(t('common.saved'))
    menuVisible.value = false
    await loadRoles()
  } finally { saving.value = false }
}

function openUser(row) {
  userForm.value = row
    ? { usercode: row.usercode, role_codes: [...(row.roles || [])], _edit: true }
    : { usercode: '', role_codes: [], _edit: false }
  userVisible.value = true
}

async function saveUserRoles() {
  saving.value = true
  try {
    await api.post('/menu/user-roles', userForm.value)
    ElMessage.success(t('common.saved'))
    userVisible.value = false
    await loadUsers()
  } finally { saving.value = false }
}

onMounted(async () => { await loadRoles(); await loadUsers() })
</script>

<style scoped>
.toolbar { display: flex; gap: 10px; margin-bottom: 12px; }
.pager { margin-top: 12px; justify-content: flex-end; }
.role-tag { margin-right: 6px; }
.menu-tree { max-height: 55vh; overflow: auto; }
.menu-group { border-bottom: 1px solid #f0f2f5; padding: 10px 0; }
.menu-group-title { font-weight: 600; color: #303133; font-size: 13px; margin-bottom: 8px; }
.menu-items { display: flex; flex-wrap: wrap; gap: 6px 18px; }
.menu-check { margin-right: 0; }
</style>

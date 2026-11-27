import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import api from '../api'

/**
 * 工单列表页共用逻辑。
 * scope: my / monitor / assigned
 */
export function useIssueList(scope) {
  const { t } = useI18n()
  const rows = ref([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(50)
  const loading = ref(false)
  const keyword = ref('')
  const status = ref(null)
  const issueType = ref(null)
  const priority = ref(null)
  const role = ref({})
  const counts = ref({})

  async function loadRole() {
    try { role.value = await api.get('/issue/my-role') } catch (e) { role.value = {} }
  }

  async function loadCounts() {
    try {
      counts.value = await api.get('/issue/dashboard', { params: { scope } })
    } catch (e) { counts.value = {} }
  }

  async function loadData() {
    loading.value = true
    try {
      const res = await api.get('/issue/list', {
        params: {
          scope, keyword: keyword.value || undefined, status: status.value,
          issue_type: issueType.value, priority: priority.value,
          page: page.value, page_size: pageSize.value,
        },
      })
      rows.value = res.items || []
      total.value = res.total || 0
    } finally { loading.value = false }
  }

  function reset() {
    keyword.value = ''
    status.value = null
    issueType.value = null
    priority.value = null
    page.value = 1
    loadData()
  }

  const router = useRouter()
  function openDetail(id) {
    router.push(`/issue/detail/${id}`)
  }

  function onChanged() {
    loadData()
    loadCounts()
  }

  onMounted(async () => {
    await loadRole()
    await Promise.all([loadData(), loadCounts()])
  })

  return {
    t, rows, total, page, pageSize, loading, keyword, status, issueType, priority,
    role, counts,
    loadData, loadCounts, reset, openDetail, onChanged,
  }
}

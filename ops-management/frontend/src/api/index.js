import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'
import i18n, { currentLocale } from '../i18n'

const api = axios.create({
  baseURL: '/api',
  timeout: 60000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  // 告知后端当前语言，便于返回对应语言的文案（状态/星期等）
  config.headers['Accept-Language'] = currentLocale() === 'enUS' ? 'en-US' : 'zh-CN'

  // GET/DELETE 统一以 JSON 打包传参：params -> ?q={"a":1,"b":"x"}
  // 浏览器 GET 请求无法携带 body，故以 query 中的 JSON 字符串作为载体，
  // 由后端中间件展开为标准 query 参数（接口签名零改动）。
  const method = String(config.method || 'get').toLowerCase()
  if ((method === 'get' || method === 'delete') && config.params) {
    const params = config.params
    let packed = null
    const strip = (obj) => {
      const out = {}
      Object.keys(obj || {}).forEach((k) => {
        const v = obj[k]
        // 仅过滤无意义值，空字符串保留（部分接口用 '' 表示显式清空）
        if (v !== undefined && v !== null) out[k] = v
      })
      return out
    }
    if (Array.isArray(params)) {
      // 数组形式交给 axios 原有逻辑处理
      packed = null
    } else if (typeof params === 'object') {
      const clean = strip(params)
      if (Object.keys(clean).length) packed = clean
    }
    if (packed) {
      config.params = { q: JSON.stringify(packed) }
      // 自定义序列化，避免默认参数编码把 JSON 拆散
      config.paramsSerializer = (p) => {
        const search = new URLSearchParams()
        Object.keys(p).forEach((k) => search.append(k, p[k]))
        return search.toString()
      }
    } else {
      config.params = undefined
    }
  }
  return config
})

api.interceptors.response.use(
  (res) => res.data,
  (err) => {
    const status = err.response?.status
    const detail = err.response?.data?.detail
    if (status === 401) {
      localStorage.removeItem('token')
      router.push('/login')
      ElMessage.error(i18n.global.t('home.sessionExpired'))
    } else {
      ElMessage.error(typeof detail === 'string' ? detail : (err.message || i18n.global.t('common.tip')))
    }
    return Promise.reject(err)
  }
)

export default api

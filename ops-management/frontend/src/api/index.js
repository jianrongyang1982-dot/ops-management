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

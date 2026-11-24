/**
 * 公共字典加载模块：货主(owners) + 品牌(brands)
 *
 * 跨页面共用同一份缓存，后续新页面直接 useCommonDicts() 即可，
 * 不需要各自重复请求 /dict/owners 和 /dict/brands。
 */
import { ref } from 'vue'
import api from '../api'
import { currentLocale } from '../i18n'

const dictCache = new Map()
const pending = new Map()

async function fetchCommonDicts(lang) {
  if (pending.has(lang)) return pending.get(lang)
  const task = api.get('/dict/common').then((data) => {
    const normalized = {
      owners: data?.owners || [],
      brands: data?.brands || [],
    }
    dictCache.set(lang, normalized)
    return normalized
  })
  pending.set(lang, task)
  try {
    return await task
  } finally {
    pending.delete(lang)
  }
}

export function useCommonDicts() {
  const owners = ref([])
  const brands = ref([])
  const loading = ref(false)

  async function load(force = false) {
    const lang = currentLocale()
    if (!force && dictCache.has(lang)) {
      const cached = dictCache.get(lang)
      owners.value = cached.owners
      brands.value = cached.brands
      return cached
    }
    loading.value = true
    try {
      const data = await fetchCommonDicts(lang)
      owners.value = data.owners
      brands.value = data.brands
      return data
    } finally {
      loading.value = false
    }
  }

  return { owners, brands, loading, load }
}

export async function loadCommonDicts(force = false) {
  const lang = currentLocale()
  if (!force && dictCache.has(lang)) return dictCache.get(lang)
  return fetchCommonDicts(lang)
}

export function clearCommonDictsCache() {
  dictCache.clear()
}

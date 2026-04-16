import axios from 'axios'
import { appMode, APP_MODES } from '../runtime/appMode'

// 创建axios实例
const service = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001',
  timeout: 300000, // 5分钟超时（本体生成可能需要较长时间）
  headers: {
    'Content-Type': 'application/json'
  }
})

// HTTP methods that mutate server state. We reject any of these when the
// app is running in demo mode — demo is explicitly read-only, and silently
// letting writes through would (a) corrupt the real backend with demo
// test data and (b) give the user a false "write succeeded" experience
// that disappears on refresh. The rejection looks identical to a normal
// API error, so existing error-handling paths surface it cleanly.
const MUTATING_METHODS = new Set(['post', 'put', 'patch', 'delete'])

// 请求拦截器
service.interceptors.request.use(
  config => {
    const method = String(config.method || 'get').toLowerCase()
    if (appMode.value === APP_MODES.DEMO && MUTATING_METHODS.has(method)) {
      const path = config.url || 'request'
      const err = new Error(`Demo 模式为只读，已阻止 ${method.toUpperCase()} ${path}`)
      err.isDemoReadonlyBlock = true
      return Promise.reject(err)
    }
    return config
  },
  error => {
    console.error('Request error:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器（容错重试机制）
service.interceptors.response.use(
  response => {
    const res = response.data
    
    // 如果返回的状态码不是success，则抛出错误
    if (!res.success && res.success !== undefined) {
      console.error('API Error:', res.error || res.message || 'Unknown error')
      return Promise.reject(new Error(res.error || res.message || 'Error'))
    }
    
    return res
  },
  error => {
    // 处理超时
    if (error.code === 'ECONNABORTED' && error.message && error.message.includes('timeout')) {
      error.message = '请求超时：后端响应太慢或未启动。可切换到 Demo 模式查看示例数据。'
      error.isNetworkDown = true
    }

    // 处理网络错误
    //
    // Browser's `new Error('Network Error')` leaks through to every page's
    // catch block as a raw English string, which reads as "something broke"
    // rather than "the backend isn't up". Rewrite it once here so every
    // page (Overview, Registry, Themes, Relations, Auto, Workspace…) gets
    // a consistent, actionable Chinese message AND a machine-readable
    // `isNetworkDown` flag pages can use to offer a Demo-mode CTA.
    if (error.message === 'Network Error') {
      error.message = '后端未连接：无法加载数据。可切换到 Demo 模式查看示例数据，或先启动后端服务。'
      error.isNetworkDown = true
    }

    // Console logging policy:
    //   - Demo read-only blocks are intentional, not bugs — silent.
    //   - Network-down is already surfaced in every page's UI via the
    //     friendly message we just rewrote. Logging the raw axios object
    //     ("Response error: AxiosError" / "[object Object]") for every
    //     page on every failed request is pure noise — drop it down to
    //     a single concise warn so the devtools console stays usable
    //     while the backend is offline.
    //   - Anything else (HTTP 4xx/5xx, parse errors) still goes through
    //     console.error with a useful, stringified payload.
    if (error?.isDemoReadonlyBlock) {
      // silent
    } else if (error?.isNetworkDown) {
      console.warn('[api]', error.message)
    } else {
      const detail = error?.response
        ? `${error.response.status} ${error.config?.method?.toUpperCase() || 'REQ'} ${error.config?.url || ''}`
        : error?.message || String(error)
      console.error('[api] response error:', detail)
    }

    return Promise.reject(error)
  }
)

// 带重试的请求函数
export const requestWithRetry = async (requestFn, maxRetries = 3, delay = 1000) => {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await requestFn()
    } catch (error) {
      if (i === maxRetries - 1) throw error
      
      console.warn(`Request failed, retrying (${i + 1}/${maxRetries})...`)
      await new Promise(resolve => setTimeout(resolve, delay * Math.pow(2, i)))
    }
  }
}

export default service

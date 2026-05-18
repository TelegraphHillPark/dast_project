import axios from 'axios'
import { useAuthStore } from '../store/auth'

export const api = axios.create({ baseURL: '/api' })

// Single in-flight refresh promise — prevents multiple simultaneous refresh requests
let refreshPromise: Promise<string> | null = null

api.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      const refreshToken = useAuthStore.getState().refreshToken
      if (refreshToken) {
        try {
          if (!refreshPromise) {
            refreshPromise = axios
              .post('/api/auth/refresh', { refresh_token: refreshToken })
              .then(({ data }) => {
                useAuthStore.getState().setTokens(data.access_token, data.refresh_token)
                return data.access_token
              })
              .finally(() => { refreshPromise = null })
          }
          const newToken = await refreshPromise
          original.headers.Authorization = `Bearer ${newToken}`
          return api(original)
        } catch {
          useAuthStore.getState().logout()
        }
      } else {
        useAuthStore.getState().logout()
      }
    }
    return Promise.reject(error)
  },
)

/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, { AxiosResponse } from 'axios'
import { getRestApiUrl } from './config'
import ElectronStore from 'electron-store'

const Store = (ElectronStore as any).default || ElectronStore

const store = new Store()

export const objectToQueryString = (params: Record<string, any> = {}): any => {
  const esc = encodeURIComponent
  return Object.keys(params)
    .map((k) => esc(k) + '=' + esc(params[k]))
    .join('&')
}

interface ApiError {
  code: string
  message: string
  status: number
  data: Record<string, any>
}

interface OptimisticUpdateParams<T> {
  updatedFields: T
  currentFields: T
  setLocalData: (data: T) => void
}

type ApiVariables = Record<string, any>

const defaults = {
  baseURL: getRestApiUrl,
  error: {
    code: 'INTERNAL_ERROR',
    message: 'Something went wrong. Please check your internet connection or contact our support.',
    status: 503,
    data: {}
  } as ApiError
}

const getStoredTokens = async (): Promise<{ token?: string } | null> => {
  try {
    const stored = await store.get('accessToken')
    if (stored && typeof stored === 'string') {
      return JSON.parse(stored)
    }
    return stored as { token?: string } | null
  } catch (error) {
    console.error('Error parsing stored tokens:', error)
    return null
  }
}

const clearStorage = async (): Promise<void> => {
  await store.clear()
}

const getHeaders = async (contentType?: string): Promise<Record<string, string | undefined>> => {
  let accessToken: string | null = null

  const tokens = await getStoredTokens()
  if (tokens?.token) {
    accessToken = tokens.token
  }

  return {
    'Content-Type': contentType || 'application/json',
    Authorization: accessToken ? `Bearer ${accessToken}` : undefined
  }
}

const api = async <T>(
  method: 'get' | 'post' | 'put' | 'patch' | 'delete',
  url: string,
  options?: {
    params?: ApiVariables
    data?: ApiVariables
    contentType?: string
  },
  baseURL?: string
): Promise<T> => {
  const headers = await getHeaders(options?.contentType)
  try {
    const params = options?.params || {}
    Object.keys(params).forEach((key) => params[key] === undefined && delete params[key])
    const response: AxiosResponse<T> = await axios({
      url: `${baseURL || defaults.baseURL}${url}`,
      method,
      headers,
      params,
      data: options?.data,
      paramsSerializer: objectToQueryString
    })
    return response.data
  } catch (error: any) {
    console.error('🚀 ~ api ~ error:', error?.response)
    if (axios.isAxiosError(error) && error?.response) {
      if (error.response.status === 401) {
        clearStorage()
        throw {
          message: error?.response?.data?.message,
          error: error?.response?.data?.error,
          status: error?.response?.status
        }
      }
      if (
        error?.response?.data?.error &&
        error?.response?.status !== 503 &&
        error?.response?.status !== 401
      ) {
        throw {
          message: error?.response?.data?.message,
          error: error?.response?.data?.error,
          status: error?.response?.status
        }
      }
    }
    throw defaults.error
  }
}

export default {
  get: <T>(
    url: string,
    options?: { params?: ApiVariables; contentType?: string },
    baseURL?: string
  ): Promise<T> => api<T>('get', url, options, baseURL),
  post: <T>(
    url: string,
    options?: {
      data?: ApiVariables
      params?: ApiVariables
      contentType?: string
    },
    baseURL?: string
  ): Promise<T> => api<T>('post', url, options, baseURL),
  put: <T>(
    url: string,
    options?: { data?: ApiVariables; contentType?: string },
    baseURL?: string
  ): Promise<T> => api<T>('put', url, options, baseURL),
  patch: <T>(
    url: string,
    options?: { data?: ApiVariables; contentType?: string },
    baseURL?: string
  ): Promise<T> => api<T>('patch', url, options, baseURL),
  delete: <T>(
    url: string,
    options?: { params?: ApiVariables; contentType?: string },
    baseURL?: string
  ): Promise<T> => api<T>('delete', url, options, baseURL),
  optimisticUpdate: async <T extends ApiVariables>(
    url: string,
    { updatedFields, currentFields, setLocalData }: OptimisticUpdateParams<T>,
    baseURL?: string
  ): Promise<void> => {
    try {
      setLocalData(updatedFields)
      await api<T>('put', url, { data: updatedFields }, baseURL)
    } catch (error) {
      setLocalData(currentFields)
      console.error((error as ApiError).message)
    }
  }
}

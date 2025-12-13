/* eslint-disable @typescript-eslint/no-explicit-any */
const REST_API_URL = 'http://localhost:3000'
const BACKEND_VERSION = '1.0.0'

if (!REST_API_URL) {
  console.error('Missing required environment variable: REST_API_URL')
  console.error('Please check your .env.local file and ensure the authentication API URL is set.')
}

export const config = {
  restApiUrl: REST_API_URL,
  backendVersion: BACKEND_VERSION,

  auth: {
    tokenExpiryBuffer: 5 * 60 * 1000,
    localStorageKeys: {
      tokens: 'tokens'
    }
  }
} as const

export const getRestApiUrl: string = config.restApiUrl

export const getBackendVersion: string = config.backendVersion

export default config

export type QueryConfig<T extends (...args: any[]) => any> = Omit<
  ReturnType<T>,
  'queryKey' | 'queryFn'
>

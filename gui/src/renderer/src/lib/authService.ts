/* eslint-disable @typescript-eslint/no-explicit-any */
import { User } from '@renderer/types/user.type'

export interface LoginResponse {
  success: boolean
  code: number
  message: string
  data: {
    user: User
    token: string
    expiresAt: number
  }
}

export interface AuthTokens {
  token: string
  expiresAt: number
}

class AuthService {
  async login(email: string, password: string): Promise<LoginResponse> {
    return window.api.auth.login(email, password)
  }

  storeTokens(tokens: AuthTokens): void {
    if (typeof window !== 'undefined') {
      window.api.store.set('accessToken', JSON.stringify(tokens))
    }
  }

  async getTokens(): Promise<AuthTokens | null> {
    if (typeof window !== 'undefined') {
      const stored = await window.api.store.get('accessToken')

      if (stored) {
        try {
          return JSON.parse(stored)
        } catch (error) {
          console.error('Failed to parse stored tokens:', error)
          this.clearTokens()
        }
      }
    }
    return null
  }

  clearTokens(): void {
    if (typeof window !== 'undefined') {
      window.api.store.clear()
    }
  }

  async isAuthenticated(): Promise<boolean> {
    const tokens = await this.getTokens()

    if (!tokens) return false

    const now = Date.now()
    const expiresAt = tokens.expiresAt - Math.floor(5 * 60 * 1000)

    return now < expiresAt
  }

  async getAccessToken(): Promise<string | null> {
    const tokens = await this.getTokens()
    return tokens?.token || null
  }

  storeUser(user: User): void {
    if (typeof window !== 'undefined') {
      window.api.store.set('user', JSON.stringify(user))
    }
  }

  async getUser(): Promise<User | null> {
    if (typeof window !== 'undefined') {
      const stored = await window.api.store.get('user')
      if (stored) {
        try {
          return JSON.parse(stored)
        } catch (error) {
          console.error('Failed to parse stored user:', error)
          return null
        }
      }
    }
    return null
  }

  logout(): void {
    this.clearTokens()
    if (typeof window !== 'undefined') {
      window.location.href = '/signin'
    }
  }

  parseJWT(token: string): any {
    try {
      const base64Url = token.split('.')[1]
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
      const jsonPayload = decodeURIComponent(
        atob(base64)
          .split('')
          .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
          .join('')
      )
      return JSON.parse(jsonPayload)
    } catch (error) {
      console.error('Failed to parse JWT:', error)
      return null
    }
  }

  handleAuthSuccess(response: LoginResponse): void {
    const { data } = response

    if (response.code === 200 && data.token) {
      const tokens: AuthTokens = {
        token: data.token,
        expiresAt: data.expiresAt
      }

      this.storeTokens(tokens)

      if (data.user) {
        this.storeUser(data.user)
      }
    }
  }
}

export const authService = new AuthService()

export { AuthService }

export default authService

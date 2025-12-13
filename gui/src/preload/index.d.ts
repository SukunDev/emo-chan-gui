/* eslint-disable @typescript-eslint/no-explicit-any */
import { ElectronAPI } from '@electron-toolkit/preload'

declare global {
  interface Window {
    electron: ElectronAPI
    api: {
      window: {
        minimize: () => Promise<void>
        maximize: () => Promise<void>
        close: () => Promise<void>
      }
      store: {
        set: (name: string, value: any) => Promise<void>
        get: (name: string) => Promise<any>
        clear: () => Promise<boolean>
      }
      todos: {
        fetch: () => Promise<any>
      }
      auth: {
        login: (username: string, password: string) => Promise<any>
      }
    }
  }
}

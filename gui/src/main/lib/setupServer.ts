/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable no-empty */
import { app } from 'electron'
import { spawn, exec  } from 'child_process'
import path from 'path'
import { is } from '@electron-toolkit/utils'

let backendProcess: ReturnType<typeof spawn> | null = null

export function startBackend():void {
  if (is.dev) return
  if (backendProcess) return
  const exePath = path.join(
    process.resourcesPath,
    'ble_bridge',
    'ble_bridge.exe'
  )

  backendProcess = spawn(exePath, [], {
    stdio: 'ignore',
    windowsHide: true
  })
}

app.on('before-quit', () => {
  if (backendProcess && process.platform === 'win32') {
    console.log('🛑 Stopping backend (taskkill)...')

    exec(`taskkill /pid ${backendProcess.pid} /T /F`, (err) => {
      if (err) console.error('taskkill failed:', err)
    })
  }
})
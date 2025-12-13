/* eslint-disable @typescript-eslint/no-explicit-any */
import { app, shell, BrowserWindow, ipcMain, nativeTheme, Tray, Menu, Notification } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import icon from '../../resources/icon.png?asset'
import axios from 'axios'
import api from './lib/api'
import apiEndpoints from './lib/apiEndpoints'
import ElectronStore from 'electron-store'
import { getRestApiUrl } from './lib/config'
import { startBackend } from './lib/setupServer'

const Store = (ElectronStore as any).default || ElectronStore

let mainWindow: BrowserWindow | null = null
let tray: Tray | null = null
let isQuitting = false
let firstMinimize = true

function createWindow(): void {
  startBackend()

  mainWindow = new BrowserWindow({
    width: 420,
    height: 730,
    show: false,
    frame: false,
    autoHideMenuBar: true,
    resizable: false,
    maximizable: false,
    minimizable: true,
    ...(process.platform === 'linux' ? { icon } : {}),
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false
    }
  })

  nativeTheme.themeSource = 'dark'

  mainWindow.on('ready-to-show', () => {
    mainWindow?.show()
  })

  mainWindow.on('close', (e) => {
    if (!isQuitting) {
      e.preventDefault()
      mainWindow?.hide()

      if (firstMinimize) {
        new Notification({
          title: 'ESP32-PET',
          body: 'Aplikasi tetap berjalan di system tray'
        }).show()
        firstMinimize = false
      }
    }
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

function createTray(): void {
  if (tray) return

  tray = new Tray(join(process.resourcesPath, 'resources', 'icon.ico'))

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Show App',
      click: () => {
        if (!mainWindow) createWindow()
        mainWindow?.show()
      }
    },
    { type: 'separator' },
    {
      label: 'Exit',
      click: () => {
        isQuitting = true
        tray?.destroy()
        app.quit()
      }
    }
  ])

  tray.setToolTip('ESP32-PET')
  tray.setContextMenu(contextMenu)

  tray.on('double-click', () => {
    if (!mainWindow) createWindow()
    mainWindow?.show()
  })
}

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.electron')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  const store = new Store()

  ipcMain.on('ping', () => console.log('pong'))

  ipcMain.on('window:minimize', (e) => {
    BrowserWindow.fromWebContents(e.sender)?.minimize()
  })

  ipcMain.on('window:maximize', (e) => {
    const win = BrowserWindow.fromWebContents(e.sender)
    if (win?.isMaximized()) win.unmaximize()
    else win?.maximize()
  })

  ipcMain.on('window:close', (e) => {
    BrowserWindow.fromWebContents(e.sender)?.close()
  })

  ipcMain.handle('todos:fetch', async () => {
    const response = await axios.get('https://jsonplaceholder.typicode.com/todos')
    return response.data
  })

  ipcMain.handle('auth:login', async (_event, username: string, password: string) => {
    try {
      const payload = { username, password }
      return await api.post(apiEndpoints.login, { data: payload }, getRestApiUrl)
    } catch (error: any) {
      throw new Error(error.message || 'Login failed')
    }
  })

  ipcMain.handle('store:set', (_event, name: string, value: any) => {
    store.set(name, value)
  })

  ipcMain.handle('store:get', (_event, name: string) => {
    return store.get(name)
  })

  ipcMain.handle('store:clear', () => {
    store.clear()
    return true
  })

  createWindow()
  createTray()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

import { app, BrowserWindow, shell } from 'electron'
import { join } from 'path'

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1320,
    height: 840,
    minWidth: 960,
    minHeight: 600,
    show: false,
    autoHideMenuBar: true,
    backgroundColor: '#0B0F14',
    title: 'RMM Console',
    webPreferences: {
      preload: join(__dirname, '../preload/index.mjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false
    }
  })

  win.on('ready-to-show', () => win.show())

  // Open any external links in the system browser, never in-app.
  win.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  // electron-vite injects ELECTRON_RENDERER_URL during `dev`.
  const devUrl = process.env['ELECTRON_RENDERER_URL']
  if (devUrl) {
    win.loadURL(devUrl)
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// Trust the RMM server's self-signed TLS certificate.
// Only the RMM server host is allowed; everything else stays strict.
const TRUSTED_HOSTS = new Set(['156.67.25.167'])
app.on('certificate-error', (event, _webContents, url, _error, _certificate, callback) => {
  try {
    const host = new URL(url).hostname
    if (TRUSTED_HOSTS.has(host)) {
      event.preventDefault()
      callback(true) // trust it
      return
    }
  } catch {
    // fall through to reject
  }
  callback(false) // reject everything else
})

app.whenReady().then(() => {
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})
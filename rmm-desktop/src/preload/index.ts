import { contextBridge } from 'electron'

// Keep the bridge tiny: the renderer talks to the RMM server directly over
// HTTP/WSS (Chromium has fetch + WebSocket), so we only expose host info.
const api = {
  platform: process.platform,
  versions: process.versions
}

contextBridge.exposeInMainWorld('desktop', api)

export type DesktopApi = typeof api

import { Button } from '@renderer/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@renderer/components/ui/card'
import { useWebSocket } from '@renderer/contexts/WebSocketProvider'
import { createFileRoute } from '@tanstack/react-router'
import { Loader, Pause, Play, Unlink, Wifi } from 'lucide-react'
import React, { useEffect, useState } from 'react'
import Marquee from 'react-fast-marquee'

export const Route = createFileRoute('/_main/')({
  component: RouteComponent
})

interface Devices {
  name: string
  address: string | null
  rssi?: string
  connected?: boolean
}

interface MediaPayload {
  title: string
  artist: string
  status: string
  is_playing: boolean
  audio_amplitude?: {
    amplitude: number
    peak: number
    rms: number
  }
}

interface MediaHistoryItem {
  title: string
  artist: string
}

function RouteComponent(): React.JSX.Element {
  const { send, lastMessage } = useWebSocket()

  const [isScanning, setIsScanning] = useState(false)
  const [isConnecting, setIsConnecting] = useState<string | null>(null)
  const [device, setDevice] = useState<Devices | null>(null)
  const [devices, setDevices] = useState<Devices[]>([])
  const [media, setMedia] = useState<MediaPayload | null>(null)
  const [mediaHistory, setMediaHistory] = useState<MediaHistoryItem[]>([])

  const handleScanButton = (): void => {
    setIsScanning(true)
    send({ event: 'ble-scan' })
  }

  const handleConnectButton = (device: Devices): void => {
    setIsConnecting(device.address)
    send({ event: 'ble-connect', address: device.address })
  }

  const handleDisconnectButton = (): void => {
    send({ event: 'ble-disconnect' })
  }

  useEffect(() => {
    try {
      if (!lastMessage) return

      if (lastMessage.event === 'ble-scan-result') {
        setIsScanning(false)
        setDevices(lastMessage.data)
      }

      if (lastMessage.event === 'ble-status-result') {
        setDevice({
          connected: lastMessage.connected,
          name: lastMessage.name,
          address: lastMessage.address
        })
      }

      if (lastMessage.event === 'ble-connect-result') {
        setIsConnecting(null)
        setDevice({
          connected: lastMessage.connected,
          name: lastMessage.name,
          address: lastMessage.address
        })
      }

      if (lastMessage.event === 'ble-disconnect-result') {
        setDevice({
          connected: false,
          name: 'Unknown',
          address: null
        })
      }

      if (lastMessage.type === 'media') {
        const newMedia: MediaPayload = {
          title: lastMessage.title,
          artist: lastMessage.artist,
          status: lastMessage.status,
          is_playing: lastMessage.is_playing,
          audio_amplitude: lastMessage.audio_amplitude
        }

        setMedia(newMedia)

        setMediaHistory((prev) => {
          if (newMedia.title === 'Unknown' || newMedia.title === '') return prev
          const exists = prev.some(
            (item) => item.title === newMedia.title && item.artist === newMedia.artist
          )

          if (exists) return prev

          return [{ title: newMedia.title, artist: newMedia.artist }, ...prev].slice(0, 20)
        })
      }
    } catch (error) {
      console.error(error)
    }
  }, [lastMessage])

  return (
    <>
      {device && device.address && (
        <>
          {/* CONNECTED DEVICE */}
          <Card className="p-4 mb-6">
            <CardHeader className="flex flex-row items-center justify-between">
              <h2 className="text-lg font-semibold">Connected Device</h2>
              <Button className="w-fit" onClick={handleDisconnectButton}>
                <Unlink />
              </Button>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="flex flex-col">
                  <p className="text-sm text-muted-foreground">{device.name}</p>
                  <p className="text-xs text-muted-foreground">{device.address}</p>
                </div>
                {device.connected ? (
                  <div className="text-green-500 font-semibold">CONNECTED</div>
                ) : (
                  <div className="text-red-500 font-semibold">DISCONNECTED</div>
                )}
              </div>
            </CardContent>
          </Card>

          {/* CURRENT MEDIA */}
          {media && media.title !== 'Unknown' && (
            <Card className="mb-4">
              <CardHeader className="space-y-2">
                <Marquee pauseOnHover speed={50}>
                  {media.title}
                </Marquee>
                <p className="text-center text-sm text-muted-foreground">{media.artist}</p>
                <div className="mx-auto">{media.is_playing ? <Pause /> : <Play />}</div>
              </CardHeader>
            </Card>
          )}

          {/* MEDIA HISTORY (SCROLLABLE) */}
          {mediaHistory.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-sm">Media History</CardTitle>
              </CardHeader>
              <CardContent className="max-h-48 overflow-y-auto space-y-2 neo-scrollbar">
                {mediaHistory.map((item, index) => (
                  <div
                    key={`${item.title}-${index}`}
                    className="border rounded-md p-2 text-sm"
                  >
                    <p className="font-medium truncate">{item.title}</p>
                    <p className="text-xs text-muted-foreground truncate">{item.artist}</p>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* DISCONNECTED STATE */}
      {(!device ||
        (device && !device.connected && device.name === 'Unknown' && !device.address)) && (
        <>
          <div className="flex justify-center mb-6">
            <Button
              onClick={handleScanButton}
              className="mx-auto h-24 w-24 rounded-full text-lg"
              disabled={isScanning}
            >
              SCAN
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Available Devices</CardTitle>
            </CardHeader>

            <CardContent className="space-y-3">
              {!isScanning && devices.length === 0 && (
                <p className="text-center text-sm text-muted-foreground">
                  Klik tombol scan untuk mencari perangkat BLE.
                </p>
              )}

              {isScanning && (
                <div className="flex justify-center py-4 text-sm text-muted-foreground">
                  <Loader className="animate-spin mr-2" /> Scanning...
                </div>
              )}

              {devices.map((item) => (
                <div
                  key={item.address}
                  onClick={() => {
                    if (isConnecting) return
                    handleConnectButton(item)
                  }}
                  className="flex flex-col rounded-lg border p-3 shadow-sm transition hover:bg-accent cursor-pointer"
                >
                  <div className="flex items-center justify-between">
                    <div className="font-semibold">{item.name || 'Unknown Device'}</div>
                    <div className="flex flex-row gap-2 items-center">
                      <span className="text-xs text-muted-foreground">{item.address}</span>
                      {isConnecting && <Loader className="animate-spin" />}
                    </div>
                  </div>

                  {item.rssi && (
                    <div className="mt-1 flex items-center gap-1 text-xs text-muted-foreground">
                      <Wifi size={12} /> {item.rssi} dBm
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        </>
      )}
    </>
  )
}

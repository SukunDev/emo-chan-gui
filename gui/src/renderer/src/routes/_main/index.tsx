import { AudioVisualizer } from '@renderer/components/AudioVisualizer'
import { Button } from '@renderer/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@renderer/components/ui/card'
import { useWebSocket } from '@renderer/contexts/WebSocketProvider'
import { createFileRoute } from '@tanstack/react-router'
import { Loader, Unlink, Wifi } from 'lucide-react'
import React, { useEffect, useState } from 'react'

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

function RouteComponent(): React.JSX.Element {
  const { send, lastMessage } = useWebSocket()
  const [isScanning, setIsScanning] = useState<boolean>(false)
  const [isConnecting, setIsConnecting] = useState<string | null>(null)
  const [device, setDevice] = useState<Devices | null>(null)
  const [devices, setDevices] = useState<Devices[]>([])
  const [media, setMedia] = useState<MediaPayload | null>(null)

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
        setMedia({
          title: lastMessage.title,
          artist: lastMessage.artist,
          status: lastMessage.status,
          is_playing: lastMessage.is_playing,
          audio_amplitude: lastMessage.audio_amplitude
        })
      }
    } catch (error) {
      console.log(error)
    }
    console.log(`lastMessage`, lastMessage)
  }, [lastMessage])

  return (
    <>
      {device && device.address && (
        <>
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
          {media && (
            <div className="mt-4 space-y-3">
              <div>
                <p className="text-sm font-semibold">{media.title}</p>
                <p className="text-xs text-muted-foreground">{media.artist}</p>
                <p className="text-xs">{media.is_playing ? '▶ Playing' : '⏸ Paused'}</p>
              </div>

              {media.audio_amplitude && (
                <AudioVisualizer
                  amplitude={media.audio_amplitude.amplitude}
                  peak={media.audio_amplitude.peak}
                  rms={media.audio_amplitude.rms}
                />
              )}
            </div>
          )}
        </>
      )}
      {(!device ||
        (device && !device.connected && device.name === 'Unknown' && !device.address)) && (
        <>
          <div className="flex justify-center mb-6">
            <Button
              onClick={handleScanButton}
              className="mx-auto h-24 w-24 rounded-full text-lg"
              disabled={isScanning}
            >
              SCAN {isScanning && <Loader className="animate-spin" />}
            </Button>
          </div>
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Available Devices</CardTitle>
            </CardHeader>

            <CardContent className="space-y-3">
              {/* Empty State */}
              {!isScanning && devices.length === 0 && (
                <p className="text-center text-sm text-muted-foreground">
                  Klik tombol scan untuk mencari perangkat BLE.
                </p>
              )}

              {/* Loading State */}
              {isScanning && (
                <div className="flex justify-center py-4 text-sm text-muted-foreground">
                  <Loader className="animate-spin mr-2" /> Scanning...
                </div>
              )}

              {/* Device List */}
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

                  {/* Meta */}
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

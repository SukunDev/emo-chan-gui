import { AppHeader } from '@renderer/components/AppHeader'
import { WebSocketProvider } from '@renderer/contexts/WebSocketProvider'
import { createFileRoute, Outlet } from '@tanstack/react-router'
import React from 'react'

export const Route = createFileRoute('/_main')({
  component: RouteComponent
})

function RouteComponent(): React.JSX.Element {
  return (
    <WebSocketProvider url="ws://127.0.0.1:8765">
      <div className="flex flex-col h-screen">
        <AppHeader />
        <main className="flex-1 overflow-y-auto bg-[linear-gradient(to_right,#80808033_1px,transparent_1px),linear-gradient(to_bottom,#80808033_1px,transparent_1px)] bg-[size:70px_70px]">
          <div className="max-w-7xl mx-auto p-6">
            <Outlet />
          </div>
        </main>
      </div>
    </WebSocketProvider>
  )
}

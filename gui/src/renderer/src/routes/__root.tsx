import React, { useEffect } from 'react'

import { Outlet, createRootRoute } from '@tanstack/react-router'
import { QueryProvider } from '@renderer/contexts/QueryProvider'
import { ToastContainer } from 'react-toastify'

export const Route = createRootRoute({
  component: RootComponent
})

function RootComponent(): React.JSX.Element {
  useEffect(() => {
    // manual set dark mode
    // document.documentElement.classList.add('dark')
  }, [])

  return (
    <>
      <QueryProvider>
        <Outlet />
      </QueryProvider>
      <ToastContainer
        position="top-right"
        autoClose={5000}
        hideProgressBar={false}
        newestOnTop={false}
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable
        pauseOnHover
        theme="colored"
      />
    </>
  )
}

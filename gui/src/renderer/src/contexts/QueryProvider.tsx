import React from 'react'
import { TanStackRouterDevtoolsPanel } from '@tanstack/react-router-devtools'
import { QueryClientProvider } from '@tanstack/react-query'
import { TanStackDevtools } from '@tanstack/react-devtools'
import { queryClient } from '@renderer/lib/react-query'
import TanStackQueryDevtools from '@renderer/integrations/tanstack-query/devtools'

type QueryProviderProps = {
  children: React.ReactNode
}

export function QueryProvider({ children }: QueryProviderProps): React.JSX.Element {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <TanStackDevtools
        config={{
          position: 'bottom-right'
        }}
        plugins={[
          {
            name: 'Tanstack Router',
            render: <TanStackRouterDevtoolsPanel />
          },
          TanStackQueryDevtools
        ]}
      />
    </QueryClientProvider>
  )
}

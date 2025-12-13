import { Button } from '@renderer/components/ui/button'
import { Separator } from '@renderer/components/ui/separator'
import { Minus, Square, X } from 'lucide-react'

export function AppHeader(): React.JSX.Element {
  return (
    <header
      className="flex h-16 shrink-0 items-center gap-2 bg-main border-b-3 px-4 py-4"
      style={{ WebkitAppRegion: 'drag' } as React.CSSProperties}
    >
        <h1>ESP Robot Pet</h1>
      <div className="flex flex-1 items-center justify-end space-x-4">
        <Separator orientation="vertical" className="h-4 bg-neutral-700" />
        <div className="flex space-x-2">
          <Button
            // variant="ghost"
            size="icon"
            className="relative text-foreground bg-white"
            onClick={() => window.api.window.minimize()}
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
          >
            <Minus />
          </Button>
          <Button
            size="icon"
            className="relative text-foreground bg-white"
            // onClick={() => window.api.window.maximize()}
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
            disabled
          >
            <Square />
          </Button>
          <Button
            size="icon"
            className="relative text-foreground bg-white"
            onClick={() => window.api.window.close()}
            style={{ WebkitAppRegion: 'no-drag' } as React.CSSProperties}
          >
            <X />
          </Button>
        </div>
      </div>
    </header>
  )
}

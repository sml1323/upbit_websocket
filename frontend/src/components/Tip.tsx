import type { ReactElement, ReactNode } from 'react'
import { Tooltip } from '@base-ui/react/tooltip'

/** base-ui 툴팁. 처음 하나는 지연 후, 이어지는 툴팁은 즉시(data-instant) 뜬다. */
export function Tip({ content, children }: { content: ReactNode; children: ReactElement }) {
  return (
    <Tooltip.Root>
      <Tooltip.Trigger render={children} />
      <Tooltip.Portal>
        <Tooltip.Positioner sideOffset={6}>
          <Tooltip.Popup className="tip">{content}</Tooltip.Popup>
        </Tooltip.Positioner>
      </Tooltip.Portal>
    </Tooltip.Root>
  )
}

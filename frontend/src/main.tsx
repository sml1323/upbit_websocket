import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Tooltip } from '@base-ui/react/tooltip'
import { MotionConfig } from 'motion/react'
import { Toaster } from 'sonner'
import App from './App'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: true, retry: 1 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* OS 의 '동작 줄이기' 설정을 따른다: 이동은 빼고 opacity 만 */}
      <MotionConfig reducedMotion="user">
        <Tooltip.Provider delay={400}>
          <App />
        </Tooltip.Provider>
      </MotionConfig>
      <Toaster theme="dark" position="bottom-right" closeButton toastOptions={{ className: 'toast' }} />
    </QueryClientProvider>
  </StrictMode>,
)

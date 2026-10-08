import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// 빌드 결과는 FastAPI 가 /app 에서 서빙한다 (src/api/main.py).
// 개발 중엔 /api 요청을 로컬 API 로 넘긴다: API_TARGET=http://localhost:8000 pnpm dev
export default defineConfig({
  base: '/app/',
  plugins: [react()],
  server: {
    proxy: {
      '/api': process.env.API_TARGET ?? 'http://localhost:8010',
    },
  },
})

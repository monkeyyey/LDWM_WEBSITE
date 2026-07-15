import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const allowedHosts = ['ldwm.anyhow.sbs', ...(process.env.VITE_ALLOWED_HOSTS?.split(',') ?? [])].filter(Boolean)

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    allowedHosts,
  },
})

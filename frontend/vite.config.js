import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteStaticCopy } from 'vite-plugin-static-copy'

// https://vite.dev/config/
export default defineConfig({
  base: '/',
  plugins: [
    react(),
    viteStaticCopy({
      targets: [
        {
          src: 'node_modules/@ibm/plex/IBM-Plex-*/fonts/split/woff2/*.woff2',
          dest: 'fonts'
        }
      ]
    })
  ],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `
          @use '@carbon/react/scss/spacing' as *;
          @use '@carbon/react/scss/theme' as *;
          @use '@carbon/react/scss/colors' as *;
          @use '@carbon/react/scss/type' as *;
          @use '@carbon/react/scss/breakpoint' as *;
          @use '@carbon/react/scss/grid' as *;
          @use '@carbon/react/scss/layout' as *;
          @use '@carbon/react/scss/motion' as *;
          @use '@carbon/react/scss/utilities' as *;
          @use '@carbon/react/scss/utilities/convert' as *;
          @use '@carbon/react/scss/utilities/focus-outline' as *;
        `
      }
    }
  }
})

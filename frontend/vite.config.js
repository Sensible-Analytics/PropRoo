import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { writeFileSync } from 'fs'
import { resolve } from 'path'

// Generate a unique version based on timestamp
const BUILD_VERSION = Date.now().toString(36)

// Inject version into the app before build
const injectVersionPlugin = () => ({
  name: 'inject-version',
  closeBundle() {
    const versionPath = resolve(__dirname, 'public', 'version.js')
    writeFileSync(versionPath, `window.APP_VERSION = '${BUILD_VERSION}';`)
  }
})

export default defineConfig({
  plugins: [
    react(),
    injectVersionPlugin(),
  ],
  esbuild: {
    keepNames: true,
  },
  build: {
    commonjsOptions: {
      include: [/node_modules/],
    },
    rollupOptions: {
      output: {
        chunkFileNames: '[name]-[hash].js',
      },
    },
  },
  optimizeDeps: {
    include: ['@deck.gl/geo-layers', '@deck.gl/aggregation-layers', '@deck.gl/layers', '@deck.gl/react', '@deck.gl/core'],
    exclude: ['@duckdb/duckdb-wasm'],
  },
  assetsInclude: ['**/*.geojson'],
  json: {
    namedExports: true,
  },
})

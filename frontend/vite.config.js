import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
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

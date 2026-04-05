import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'
import boundaries from 'eslint-plugin-boundaries'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
      'max-lines': ['warn', { 'max': 200, 'skipBlankLines': true, 'skipComments': true }],
      'max-lines-per-function': ['warn', { 'max': 30, 'skipBlankLines': true, 'skipComments': true }],
      'complexity': ['warn', { 'max': 8 }],
      'max-depth': ['warn', 4],
      'max-params': ['warn', 3],
    },
  },
  // Architecture boundaries
  {
    files: ['src/**/*.{js,jsx,ts,tsx}'],
    plugins: { boundaries },
    settings: {
      'boundaries/elements': [
        { type: 'component', pattern: 'src/components/**' },
        { type: 'page', pattern: 'src/pages/**' },
        { type: 'hook', pattern: 'src/hooks/**' },
        { type: 'service', pattern: 'src/services/**' },
        { type: 'util', pattern: 'src/utils/**' },
        { type: 'store', pattern: 'src/store/**' },
        { type: 'api', pattern: 'src/api/**' },
      ],
    },
    rules: {
      'boundaries/element-types': ['error', {
        default: 'disallow',
        rules: [
          { from: { type: 'page' }, allow: ['component', 'hook', 'service', 'store', 'util', 'api'] },
          { from: { type: 'component' }, allow: ['hook', 'service', 'util', 'api'] },
          { from: { type: 'hook' }, allow: ['service', 'util', 'api'] },
          { from: { type: 'service' }, allow: ['service', 'util', 'api'] },
        ],
      }],
    },
  },
])

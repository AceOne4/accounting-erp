import { defineConfig } from '@hey-api/openapi-ts'

// Types only. We deliberately do not use the generated HTTP client; src/api/client.ts
// handles cookies and CSRF. Regenerate with `npm run api:types` after backend changes.
export default defineConfig({
  input: '../backend/schema.yml',
  output: 'src/api/generated',
  plugins: ['@hey-api/typescript'],
})

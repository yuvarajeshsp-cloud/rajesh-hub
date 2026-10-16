import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://example.com', // set to the real domain before the first deploy
  integrations: [sitemap()],
});

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined;
          if (id.includes('victory-vendor')) return 'charts-victory';
          if (id.includes('recharts-scale')) return 'charts-scale';
          if (id.includes('recharts')) return 'charts-recharts';
          if (id.includes('lodash')) return 'charts-lodash';
          if (id.includes('react-smooth')) return 'charts-animation';
          if (id.includes('react') || id.includes('scheduler')) return 'react-vendor';
          return 'vendor';
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
  },
});

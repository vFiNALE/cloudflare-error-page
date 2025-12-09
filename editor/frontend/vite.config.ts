import { defineConfig } from 'vite';
import { minify as htmlMinify } from 'html-minifier-terser';

export default defineConfig({
  appType: 'mpa',
  base: '/editor/',
  build: {
    minify: true,
    sourcemap: true,
  },
  server: {
    port: 3000,
    proxy: {
      '/s': {
        target: 'http://localhost:5000',
      },
    },
  },

  plugins: [
    {
      name: 'html-minifier',
      transformIndexHtml: {
        order: 'post',
        handler(html) {
          return htmlMinify(html, {
            collapseWhitespace: true,
            removeComments: true,
            minifyCSS: true,
            minifyJS: true,
          });
        },
      },
    },
  ],
});

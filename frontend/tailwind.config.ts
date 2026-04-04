import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        status: {
          resolved: '#22c55e',
          pending: '#eab308',
          failed: '#ef4444',
          escalated: '#ef4444',
          analyzing: '#3b82f6',
        },
      },
    },
  },
  plugins: [],
};

export default config;

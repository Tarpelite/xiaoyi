import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          900: '#0a0a0f',
          800: '#12121a',
          700: '#1a1a24',
          600: '#22222e',
          500: '#2a2a38',
          400: '#3a3a4a',
        },
        accent: {
          purple: '#8b5cf6',
          blue: '#3b82f6',
          cyan: '#06b6d4',
          green: '#10b981',
          orange: '#f59e0b',
          red: '#ef4444',
        }
      },
      fontSize: {
        // 新的字体比例体系（基于 1.25 公比，最小18px）
        'xs': ['18px', { lineHeight: '1.6' }],      // 最小字号 - 辅助信息
        'sm': ['20px', { lineHeight: '1.6' }],      // 小字号 - 次要内容
        'base': ['20px', { lineHeight: '1.6' }],    // 基准字号 - 正文
        'lg': ['24px', { lineHeight: '1.5' }],      // 大字号 - 小标题
        'xl': ['30px', { lineHeight: '1.4' }],      // 标题级别
        '2xl': ['36px', { lineHeight: '1.3' }],     // 大标题
        '3xl': ['48px', { lineHeight: '1.2' }],     // 特大标题
      },
      fontFamily: {
        sans: [
          '-apple-system',
          'BlinkMacSystemFont',
          '"Segoe UI"',
          '"PingFang SC"',
          '"Hiragino Sans GB"',
          '"Microsoft YaHei"',
          '"Noto Sans SC"',
          'sans-serif',
        ],
        mono: [
          '"SF Mono"',
          '"Fira Code"',
          '"JetBrains Mono"',
          'Consolas',
          'monospace',
        ],
      },
      animation: {
        'pulse-soft': 'pulse-soft 2s infinite',
        'slide-up': 'slide-up 0.3s ease-out',
      },
      keyframes: {
        'pulse-soft': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
        'slide-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
}

export default config

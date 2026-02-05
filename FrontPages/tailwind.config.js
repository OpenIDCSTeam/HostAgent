/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      // 自定义颜色
      colors: {
        // 浅色主题色
        'light-primary': '#ffffff',
        'light-secondary': '#f8f9fa',
        'light-accent': '#0ea5e9',
        'light-accent-secondary': '#10b981',
        
        // 深色主题色
        'dark-primary': '#0f1419',
        'dark-secondary': '#1a1f2e',
        'dark-tertiary': '#252b3b',
        'dark-accent': '#00d4ff',
        'dark-accent-secondary': '#00ff88',
        
        // 状态色
        'status-success': '#10b981',
        'status-warning': '#f59e0b',
        'status-error': '#ef4444',
        'status-info': '#3b82f6',
      },
      
      // 自定义圆角
      borderRadius: {
        'card': '16px',
        'button': '12px',
        'input': '8px',
        'badge': '6px',
      },
      
      // 自定义阴影
      boxShadow: {
        'glass': '0 8px 32px rgba(0, 0, 0, 0.1)',
        'glass-dark': '0 8px 32px rgba(0, 0, 0, 0.3)',
        'glow': '0 0 20px rgba(14, 165, 233, 0.3)',
        'glow-dark': '0 0 20px rgba(0, 212, 255, 0.3)',
        'card': '0 4px 6px rgba(0, 0, 0, 0.07)',
        'card-hover': '0 10px 15px rgba(0, 0, 0, 0.1)',
      },
      
      // 自定义动画
      animation: {
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in': 'fadeIn 0.5s ease-out',
        'slide-in': 'slideIn 0.4s ease-out',
      },
      
      // 自定义关键帧
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0', transform: 'translateY(10px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideIn: {
          '0%': { opacity: '0', transform: 'translateX(-20px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
      },
      
      // 自定义过渡
      transitionProperty: {
        'height': 'height',
        'spacing': 'margin, padding',
      },
      
      // 自定义背景模糊
      backdropBlur: {
        'glass': '20px',
      },
    },
  },
  plugins: [
    require('daisyui'),
  ],
  // DaisyUI配置
  daisyui: {
    themes: [
      {
        light: {
          ...require("daisyui/src/theming/themes")["light"],
          primary: "#0ea5e9",
          secondary: "#10b981",
          accent: "#3b82f6",
          neutral: "#374151",
          "base-100": "#ffffff",
          info: "#0ea5e9",
          success: "#22c55e",
          warning: "#f59e0b",
          error: "#ef4444",
        },
      },
    ],
    darkTheme: false, // 禁用DaisyUI暗色主题（使用自定义主题系统）
    base: true,
    styled: true,
    utils: true,
    logs: false,
  },
}

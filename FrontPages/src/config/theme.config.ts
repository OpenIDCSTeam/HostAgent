import { ThemeConfig } from 'antd';
import { theme } from 'antd';

// 亮色主题配置
export const lightTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    // 主色调
    colorPrimary: '#0ea5e9',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorInfo: '#3b82f6',
    
    // 文本颜色
    colorText: '#1e293b',
    colorTextSecondary: '#64748b',
    colorTextTertiary: '#94a3b8',
    colorTextQuaternary: '#cbd5e1',
    
    // 背景颜色
    colorBgContainer: 'rgba(255, 255, 255, 0.8)',
    colorBgElevated: 'rgba(255, 255, 255, 0.9)',
    colorBgLayout: '#f8fafc',
    
    // 边框
    colorBorder: '#e2e8f0',
    colorBorderSecondary: '#f1f5f9',
    
    // 圆角
    borderRadius: 16,
    borderRadiusLG: 20,
    borderRadiusSM: 12,
    borderRadiusXS: 8,
    
    // 字体
    fontSize: 14,
    fontSizeHeading1: 38,
    fontSizeHeading2: 30,
    fontSizeHeading3: 24,
    fontSizeHeading4: 20,
    fontSizeHeading5: 16,
    
    // 阴影
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
    boxShadowSecondary: '0 2px 8px rgba(0, 0, 0, 0.06)',
  },
  components: {
    // Card组件
    Card: {
      colorBgContainer: 'rgba(255, 255, 255, 0.5)',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
    },
    // Button组件
    Button: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
      fontWeight: 500,
    },
    // Input组件
    Input: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    // Select组件
    Select: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    // Menu组件
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(14, 165, 233, 0.1)',
      itemHoverBg: 'rgba(14, 165, 233, 0.05)',
    },
    // Table组件
    Table: {
      headerBg: 'rgba(248, 250, 252, 0.8)',
      rowHoverBg: 'rgba(14, 165, 233, 0.05)',
    },
    // Modal组件
    Modal: {
      contentBg: 'rgba(255, 255, 255, 0.95)',
      headerBg: 'rgba(255, 255, 255, 0.95)',
    },
    // Drawer组件
    Drawer: {
      colorBgElevated: 'rgba(255, 255, 255, 0.95)',
    },
    // Message组件
    Message: {
      contentBg: 'rgba(255, 255, 255, 0.95)',
    },
    // Notification组件
    Notification: {
      colorBgElevated: 'rgba(255, 255, 255, 0.95)',
    },
  },
};

// 暗色主题配置
export const darkTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    // 主色调
    colorPrimary: '#64b5f6',
    colorSuccess: '#81c784',
    colorWarning: '#ffb74d',
    colorError: '#e57373',
    colorInfo: '#64b5f6',
    
    // 文本颜色
    colorText: '#e2e8f0',
    colorTextSecondary: '#94a3b8',
    colorTextTertiary: '#64748b',
    colorTextQuaternary: '#475569',
    
    // 背景颜色
    colorBgContainer: 'rgba(46, 52, 66, 0.8)',
    colorBgElevated: 'rgba(46, 52, 66, 0.9)',
    colorBgLayout: '#0f172a',
    
    // 边框
    colorBorder: '#334155',
    colorBorderSecondary: '#1e293b',
    
    // 圆角
    borderRadius: 16,
    borderRadiusLG: 20,
    borderRadiusSM: 12,
    borderRadiusXS: 8,
    
    // 字体
    fontSize: 14,
    fontSizeHeading1: 38,
    fontSizeHeading2: 30,
    fontSizeHeading3: 24,
    fontSizeHeading4: 20,
    fontSizeHeading5: 16,
    
    // 阴影
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
    boxShadowSecondary: '0 2px 8px rgba(0, 0, 0, 0.2)',
  },
  components: {
    // Card组件
    Card: {
      colorBgContainer: 'rgba(46, 52, 66, 0.5)',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    },
    // Button组件
    Button: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
      fontWeight: 500,
    },
    // Input组件
    Input: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    // Select组件
    Select: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    // Menu组件
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(100, 181, 246, 0.15)',
      itemHoverBg: 'rgba(100, 181, 246, 0.08)',
    },
    // Table组件
    Table: {
      headerBg: 'rgba(30, 41, 59, 0.8)',
      rowHoverBg: 'rgba(100, 181, 246, 0.08)',
    },
    // Modal组件
    Modal: {
      contentBg: 'rgba(46, 52, 66, 0.95)',
      headerBg: 'rgba(46, 52, 66, 0.95)',
    },
    // Drawer组件
    Drawer: {
      colorBgElevated: 'rgba(46, 52, 66, 0.95)',
    },
    // Message组件
    Message: {
      contentBg: 'rgba(46, 52, 66, 0.95)',
    },
    // Notification组件
    Notification: {
      colorBgElevated: 'rgba(46, 52, 66, 0.95)',
    },
  },
};

// 透明模式 - 亮色主题配置
export const lightTransparentTheme: ThemeConfig = {
  algorithm: theme.defaultAlgorithm,
  token: {
    // 主色调
    colorPrimary: '#0ea5e9',
    colorSuccess: '#10b981',
    colorWarning: '#f59e0b',
    colorError: '#ef4444',
    colorInfo: '#3b82f6',
    
    // 文本颜色
    colorText: '#1e293b',
    colorTextSecondary: '#64748b',
    colorTextTertiary: '#94a3b8',
    colorTextQuaternary: '#cbd5e1',
    
    // 背景颜色 - 透明
    colorBgContainer: 'transparent',
    colorBgElevated: 'rgba(255, 255, 255, 0.3)',
    colorBgLayout: 'transparent',
    
    // 边框
    colorBorder: 'rgba(0, 0, 0, 0.1)',
    colorBorderSecondary: 'rgba(0, 0, 0, 0.05)',
    
    // 圆角
    borderRadius: 16,
    borderRadiusLG: 20,
    borderRadiusSM: 12,
    borderRadiusXS: 8,
    
    // 字体
    fontSize: 14,
    fontSizeHeading1: 38,
    fontSizeHeading2: 30,
    fontSizeHeading3: 24,
    fontSizeHeading4: 20,
    fontSizeHeading5: 16,
    
    // 阴影
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.08)',
    boxShadowSecondary: '0 2px 8px rgba(0, 0, 0, 0.06)',
  },
  components: {
    // Card组件 - 透明
    Card: {
      colorBgContainer: 'transparent',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)',
    },
    // Button组件
    Button: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
      fontWeight: 500,
    },
    // Input组件
    Input: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    // Select组件
    Select: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    // Menu组件
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(14, 165, 233, 0.1)',
      itemHoverBg: 'rgba(14, 165, 233, 0.05)',
    },
    // Table组件
    Table: {
      headerBg: 'rgba(248, 250, 252, 0.3)',
      rowHoverBg: 'rgba(14, 165, 233, 0.05)',
    },
    // Modal组件
    Modal: {
      contentBg: 'rgba(255, 255, 255, 0.5)',
      headerBg: 'rgba(255, 255, 255, 0.5)',
    },
    // Drawer组件
    Drawer: {
      colorBgElevated: 'rgba(255, 255, 255, 0.5)',
    },
    // Message组件
    Message: {
      contentBg: 'rgba(255, 255, 255, 0.5)',
    },
    // Notification组件
    Notification: {
      colorBgElevated: 'rgba(255, 255, 255, 0.5)',
    },
  },
};

// 透明模式 - 暗色主题配置
export const darkTransparentTheme: ThemeConfig = {
  algorithm: theme.darkAlgorithm,
  token: {
    // 主色调
    colorPrimary: '#64b5f6',
    colorSuccess: '#81c784',
    colorWarning: '#ffb74d',
    colorError: '#e57373',
    colorInfo: '#64b5f6',
    
    // 文本颜色
    colorText: '#e2e8f0',
    colorTextSecondary: '#94a3b8',
    colorTextTertiary: '#64748b',
    colorTextQuaternary: '#475569',
    
    // 背景颜色 - 透明
    colorBgContainer: 'transparent',
    colorBgElevated: 'rgba(46, 52, 66, 0.3)',
    colorBgLayout: 'transparent',
    
    // 边框
    colorBorder: 'rgba(255, 255, 255, 0.1)',
    colorBorderSecondary: 'rgba(255, 255, 255, 0.05)',
    
    // 圆角
    borderRadius: 16,
    borderRadiusLG: 20,
    borderRadiusSM: 12,
    borderRadiusXS: 8,
    
    // 字体
    fontSize: 14,
    fontSizeHeading1: 38,
    fontSizeHeading2: 30,
    fontSizeHeading3: 24,
    fontSizeHeading4: 20,
    fontSizeHeading5: 16,
    
    // 阴影
    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.3)',
    boxShadowSecondary: '0 2px 8px rgba(0, 0, 0, 0.2)',
  },
  components: {
    // Card组件 - 透明
    Card: {
      colorBgContainer: 'transparent',
      boxShadow: '0 8px 32px rgba(0, 0, 0, 0.3)',
    },
    // Button组件
    Button: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
      fontWeight: 500,
    },
    // Input组件
    Input: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    // Select组件
    Select: {
      controlHeight: 40,
      controlHeightLG: 48,
      controlHeightSM: 32,
    },
    // Menu组件
    Menu: {
      itemBg: 'transparent',
      itemSelectedBg: 'rgba(100, 181, 246, 0.15)',
      itemHoverBg: 'rgba(100, 181, 246, 0.08)',
    },
    // Table组件
    Table: {
      headerBg: 'rgba(30, 41, 59, 0.3)',
      rowHoverBg: 'rgba(100, 181, 246, 0.08)',
    },
    // Modal组件
    Modal: {
      contentBg: 'rgba(46, 52, 66, 0.5)',
      headerBg: 'rgba(46, 52, 66, 0.5)',
    },
    // Drawer组件
    Drawer: {
      colorBgElevated: 'rgba(46, 52, 66, 0.5)',
    },
    // Message组件
    Message: {
      contentBg: 'rgba(46, 52, 66, 0.5)',
    },
    // Notification组件
    Notification: {
      colorBgElevated: 'rgba(46, 52, 66, 0.5)',
    },
  },
};

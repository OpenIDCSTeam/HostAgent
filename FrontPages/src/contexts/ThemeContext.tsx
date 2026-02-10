import React, { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { ThemeConfig, ConfigProvider } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import { lightTheme, darkTheme, Theme, lightTransparentTheme, darkTransparentTheme } from '../config/theme.config';

type Theme = 'light' | 'dark';

interface ThemeContextType {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
  transparentMode: boolean;
  toggleTransparentMode: () => void;
  getThemeConfig: () => ThemeConfig;
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

export const useTheme = () => {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
};

interface ThemeProviderProps {
  children: ReactNode;
}

export const ThemeProvider: React.FC<ThemeProviderProps> = ({ children }) => {
  // 从 localStorage 读取保存的主题，默认为浅色
  const [theme, setThemeState] = useState<Theme>(() => {
    const savedTheme = localStorage.getItem('theme') as Theme;
    return savedTheme || 'light';
  });

  // 从 localStorage 读取透明模式状态，默认为关闭
  const [transparentMode, setTransparentMode] = useState<boolean>(() => {
    const savedMode = localStorage.getItem('transparentMode');
    return savedMode === 'true';
  });

  // 当主题变化时，更新 DOM 和 localStorage
  useEffect(() => {
    const root = document.documentElement;
    root.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  // 当透明模式变化时，更新 DOM 和 localStorage
  useEffect(() => {
    const root = document.documentElement;
    const body = document.body;
    if (transparentMode) {
      root.setAttribute('data-transparent', 'true');
      // 将背景图片设置在body上，避免被其他样式遮挡
      body.style.backgroundImage = 'url(https://images.524228.xyz/)';
      body.style.backgroundSize = 'cover';
      body.style.backgroundPosition = 'center';
      body.style.backgroundAttachment = 'fixed';
      body.style.backgroundColor = 'transparent';
    } else {
      root.removeAttribute('data-transparent');
      body.style.backgroundImage = '';
      body.style.backgroundColor = '';
    }
    localStorage.setItem('transparentMode', String(transparentMode));
  }, [transparentMode]);

  const toggleTheme = () => {
    setThemeState(prevTheme => prevTheme === 'light' ? 'dark' : 'light');
  };

  const setTheme = (newTheme: Theme) => {
    setThemeState(newTheme);
  };

  const toggleTransparentMode = () => {
    setTransparentMode(prev => !prev);
  };

  const getThemeConfig = (): ThemeConfig => {
    if (transparentMode) {
      return theme === 'light' ? lightTransparentTheme : darkTransparentTheme;
    }
    return theme === 'light' ? lightTheme : darkTheme;
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme, transparentMode, toggleTransparentMode, getThemeConfig }}>
      <ConfigProvider 
        theme={getThemeConfig()}
        locale={zhCN}
        getPopupContainer={(node) => node?.parentElement || document.body}
        modal={{
          mask: false
        }}
      >
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
};

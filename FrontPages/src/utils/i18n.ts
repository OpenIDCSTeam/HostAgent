/**
 * OpenIDCS 国际化/翻译系统
 * 提供非侵入式的页面翻译功能
 */

// ============================================================================
// 类型定义
// ============================================================================
interface Language {
  code: string;
  native: string;
  name?: string;
}

interface I18nState {
  currentLanguage: string;
  translations: Record<string, string>;
  availableLanguages: Language[];
  initialized: boolean;
  observers: MutationObserver[];
}

// ============================================================================
// 全局翻译对象
// ============================================================================
const i18nState: I18nState = {
  currentLanguage: 'zh-cn',
  translations: {},
  availableLanguages: [],
  initialized: false,
  observers: []
};

// 不需要翻译的元素标签
const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'OBJECT', 'EMBED']);

// 不需要翻译的元素类名
const SKIP_CLASSES = new Set(['no-translate', 'notranslate']);

// 存储原始文本的映射
const originalTexts = new WeakMap<Node, string>();

// ============================================================================
// 语言检测与存储
// ============================================================================

/**
 * 获取浏览器语言
 */
function getBrowserLanguage(): string {
  const lang = navigator.language;
  if (lang.startsWith('zh')) {
    return 'zh-cn';
  } else if (lang.startsWith('en')) {
    return 'en-us';
  }
  return 'zh-cn';
}

/**
 * 从localStorage获取保存的语言设置
 */
function getSavedLanguage(): string {
  return localStorage.getItem('language') || getBrowserLanguage();
}

/**
 * 保存语言设置到localStorage
 */
function saveLanguage(lang: string): void {
  localStorage.setItem('language', lang);
}

// ============================================================================
// API 交互
// ============================================================================

/**
 * 加载可用语言列表
 */
async function loadAvailableLanguages(): Promise<boolean> {
  try {
    const response = await fetch('/api/i18n/languages');
    const result = await response.json();
    if (result.code === 200) {
      i18nState.availableLanguages = result.data;
      renderLanguageDropdown();
      // 触发语言列表加载完成事件，通知前端组件更新
      window.dispatchEvent(new CustomEvent('languagesLoaded', {
        detail: { languages: result.data }
      }));
      return true;
    }
    return false;
  } catch (error) {
    console.error('加载语言列表失败:', error);
    return false;
  }
}

/**
 * 加载翻译数据
 */
async function loadTranslations(lang: string): Promise<boolean> {
  try {
    const response = await fetch(`/api/i18n/translations/${lang}`);
    const result = await response.json();
    if (result.code === 200) {
      i18nState.translations = result.data;
      i18nState.currentLanguage = lang;
      saveLanguage(lang);
      applyTranslations(document.body, true);
      updateLanguageDisplay();
      return true;
    }
    return false;
  } catch (error) {
    console.error('加载翻译数据失败:', error);
    return false;
  }
}

// ============================================================================
// 翻译应用
// ============================================================================

/**
 * 判断元素是否应该跳过翻译
 */
function shouldSkipElement(element: Element): boolean {
  if (SKIP_TAGS.has(element.tagName)) {
    return true;
  }

  if (element.classList) {
    for (const className of SKIP_CLASSES) {
      if (element.classList.contains(className)) {
        return true;
      }
    }
  }

  if (element.getAttribute('translate') === 'no') {
    return true;
  }

  if ((element as HTMLElement).isContentEditable) {
    return true;
  }

  return false;
}

/**
 * 查找并应用部分匹配翻译
 */
function findPartialTranslation(text: string): string | null {
  const translationKeys = Object.keys(i18nState.translations)
    .filter(key => key.length > 2)
    .sort((a, b) => b.length - a.length);

  let result = text;
  let hasTranslation = false;
  const maxIterations = 10;

  for (let iteration = 0; iteration < maxIterations; iteration++) {
    let iterationHasTranslation = false;
    const previousResult = result;
    const translatedRanges: Array<{ start: number; end: number }> = [];

    for (const key of translationKeys) {
      const translation = i18nState.translations[key];

      if (!translation || translation === key) {
        continue;
      }

      let index = 0;
      while ((index = result.indexOf(key, index)) !== -1) {
        const isOverlapping = translatedRanges.some(range =>
          (index >= range.start && index < range.end) ||
          (index + key.length > range.start && index + key.length <= range.end) ||
          (index <= range.start && index + key.length >= range.end)
        );

        if (!isOverlapping) {
          result = result.substring(0, index) + translation + result.substring(index + key.length);

          translatedRanges.push({
            start: index,
            end: index + translation.length
          });

          iterationHasTranslation = true;
          hasTranslation = true;
          index += translation.length;
        } else {
          index += key.length;
        }
      }
    }

    if (!iterationHasTranslation || result === previousResult) {
      break;
    }
  }

  return hasTranslation ? result : null;
}

/**
 * 翻译文本节点
 */
function translateTextNode(textNode: Node, forceRetranslate = false): void {
  if (!originalTexts.has(textNode)) {
    originalTexts.set(textNode, textNode.nodeValue || '');
  }

  const sourceText = forceRetranslate ? originalTexts.get(textNode)! : textNode.nodeValue || '';
  const text = sourceText.trim();

  if (!text) {
    return;
  }

  if (/^[\d\s\-_.,;:!?()[\]{}]+$/.test(text)) {
    return;
  }

  const exactTranslation = i18nState.translations[text];
  if (exactTranslation && exactTranslation !== text) {
    const leadingSpace = sourceText.match(/^\s*/)?.[0] || '';
    const trailingSpace = sourceText.match(/\s*$/)?.[0] || '';
    textNode.nodeValue = leadingSpace + exactTranslation + trailingSpace;
    return;
  }

  const partialTranslation = findPartialTranslation(text);
  if (partialTranslation) {
    const leadingSpace = sourceText.match(/^\s*/)?.[0] || '';
    const trailingSpace = sourceText.match(/\s*$/)?.[0] || '';
    textNode.nodeValue = leadingSpace + partialTranslation + trailingSpace;
  } else if (forceRetranslate) {
    textNode.nodeValue = sourceText;
  }
}

/**
 * 翻译元素的属性
 */
function translateAttributes(element: Element, forceRetranslate = false): void {
  const el = element as HTMLElement & { _originalAttrs?: Record<string, string> };

  if (!el._originalAttrs && !forceRetranslate) {
    el._originalAttrs = {};
  }

  // 翻译 placeholder
  if ((el as HTMLInputElement).placeholder) {
    const inputEl = el as HTMLInputElement;
    if (!el._originalAttrs!.placeholder) {
      el._originalAttrs!.placeholder = inputEl.placeholder;
    }
    const text = (forceRetranslate ? el._originalAttrs!.placeholder : inputEl.placeholder).trim();
    const translation = i18nState.translations[text];
    if (translation) {
      inputEl.placeholder = translation;
    } else if (forceRetranslate) {
      inputEl.placeholder = el._originalAttrs!.placeholder;
    }
  }

  // 翻译 title
  if (el.title) {
    if (!el._originalAttrs!.title) {
      el._originalAttrs!.title = el.title;
    }
    const text = (forceRetranslate ? el._originalAttrs!.title : el.title).trim();
    const translation = i18nState.translations[text];
    if (translation) {
      el.title = translation;
    } else if (forceRetranslate) {
      el.title = el._originalAttrs!.title;
    }
  }

  // 翻译 value
  if ((el as HTMLInputElement).value && (el.tagName === 'INPUT' || el.tagName === 'BUTTON')) {
    const inputEl = el as HTMLInputElement;
    if (!el._originalAttrs!.value) {
      el._originalAttrs!.value = inputEl.value;
    }
    const text = (forceRetranslate ? el._originalAttrs!.value : inputEl.value).trim();
    const translation = i18nState.translations[text];
    if (translation) {
      inputEl.value = translation;
    } else if (forceRetranslate) {
      inputEl.value = el._originalAttrs!.value;
    }
  }

  // 翻译 aria-label
  const ariaLabel = el.getAttribute('aria-label');
  if (ariaLabel) {
    if (!el._originalAttrs!.ariaLabel) {
      el._originalAttrs!.ariaLabel = ariaLabel;
    }
    const text = (forceRetranslate ? el._originalAttrs!.ariaLabel : ariaLabel).trim();
    const translation = i18nState.translations[text];
    if (translation) {
      el.setAttribute('aria-label', translation);
    } else if (forceRetranslate) {
      el.setAttribute('aria-label', el._originalAttrs!.ariaLabel);
    }
  }

  // 翻译 alt
  if ((el as HTMLImageElement).alt) {
    const imgEl = el as HTMLImageElement;
    if (!el._originalAttrs!.alt) {
      el._originalAttrs!.alt = imgEl.alt;
    }
    const text = (forceRetranslate ? el._originalAttrs!.alt : imgEl.alt).trim();
    const translation = i18nState.translations[text];
    if (translation) {
      imgEl.alt = translation;
    } else if (forceRetranslate) {
      imgEl.alt = el._originalAttrs!.alt;
    }
  }
}

/**
 * 递归翻译元素及其子元素
 */
function translateElement(element: Element, forceRetranslate = false): void {
  if (shouldSkipElement(element)) {
    return;
  }

  translateAttributes(element, forceRetranslate);

  const walker = document.createTreeWalker(
    element,
    NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
    {
      acceptNode: function (node: Node) {
        if (node.nodeType === Node.ELEMENT_NODE) {
          return shouldSkipElement(node as Element) ?
            NodeFilter.FILTER_REJECT :
            NodeFilter.FILTER_SKIP;
        }
        return NodeFilter.FILTER_ACCEPT;
      }
    }
  );

  const textNodes: Node[] = [];
  let node: Node | null;
  while ((node = walker.nextNode())) {
    if (node.nodeType === Node.TEXT_NODE) {
      textNodes.push(node);
    }
  }

  textNodes.forEach(textNode => translateTextNode(textNode, forceRetranslate));
}

/**
 * 应用翻译到页面元素
 */
function applyTranslations(root: Element | Document = document.body, forceRetranslate = false): void {
  if (!root) return;

  let targetRoot: Element = root as Element;
  if (root === document) {
    targetRoot = document.body;
  }

  if (targetRoot.nodeType === Node.ELEMENT_NODE) {
    translateElement(targetRoot, forceRetranslate);
  }
}

// ============================================================================
// DOM 监听
// ============================================================================

/**
 * 设置 MutationObserver 监听 DOM 变化
 */
function setupDOMObserver(): void {
  i18nState.observers.forEach(observer => observer.disconnect());
  i18nState.observers = [];

  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === Node.ELEMENT_NODE) {
          translateElement(node as Element);
        } else if (node.nodeType === Node.TEXT_NODE) {
          translateTextNode(node);
        }
      });

      if (mutation.type === 'characterData') {
        translateTextNode(mutation.target);
      }
    });
  });

  observer.observe(document.body, {
    childList: true,
    subtree: true,
    characterData: true
  });

  i18nState.observers.push(observer);
}

// ============================================================================
// UI 更新
// ============================================================================

/**
 * 渲染语言下拉菜单
 */
function renderLanguageDropdown(): void {
  const dropdown = document.getElementById('languageDropdown');
  if (!dropdown) return;

  dropdown.innerHTML = i18nState.availableLanguages.map(lang => `
    <button onclick="window.i18n.changeLanguage('${lang.code}')" 
            class="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2 ${lang.code === i18nState.currentLanguage ? 'bg-blue-50 text-blue-600' : ''}">
        <span class="iconify" data-icon="${lang.code === i18nState.currentLanguage ? 'mdi:check' : 'mdi:translate'}" data-width="16"></span>
        <span>${lang.native}</span>
    </button>
  `).join('');
}

/**
 * 更新语言显示
 */
function updateLanguageDisplay(): void {
  const currentLangName = document.getElementById('currentLanguageName');
  if (currentLangName) {
    const lang = i18nState.availableLanguages.find(l => l.code === i18nState.currentLanguage);
    if (lang) {
      currentLangName.textContent = lang.native;
    }
  }
  renderLanguageDropdown();
}

/**
 * 设置语言选择器事件
 */
function setupLanguageSelector(): void {
  const languageButton = document.getElementById('languageButton');
  const languageDropdown = document.getElementById('languageDropdown');

  if (languageButton && languageDropdown) {
    languageButton.addEventListener('click', (e) => {
      e.stopPropagation();
      languageDropdown.classList.toggle('hidden');
    });

    document.addEventListener('click', () => {
      languageDropdown.classList.add('hidden');
    });

    languageDropdown.addEventListener('click', (e) => {
      e.stopPropagation();
    });
  }
}

// ============================================================================
// 公共 API
// ============================================================================

/**
 * 翻译函数
 */
export function t(key: string, defaultValue: string | null = null, enablePartialMatch = true): string {
  const exactTranslation = i18nState.translations[key];
  if (exactTranslation) {
    return exactTranslation;
  }

  if (enablePartialMatch) {
    const partialTranslation = findPartialTranslation(key);
    if (partialTranslation) {
      return partialTranslation;
    }
  }

  return defaultValue || key;
}

/**
 * 切换语言
 */
export async function changeLanguage(lang: string): Promise<void> {
  const success = await loadTranslations(lang);
  if (success) {
    const dropdown = document.getElementById('languageDropdown');
    if (dropdown) {
      dropdown.classList.add('hidden');
    }

    window.dispatchEvent(new CustomEvent('languageChanged', {
      detail: { language: lang }
    }));
  }
}

/**
 * 重新翻译整个页面
 */
export function retranslate(): void {
  applyTranslations(document.body, true);
}

/**
 * 获取当前语言
 */
export function getCurrentLanguage(): string {
  return i18nState.currentLanguage;
}

/**
 * 获取可用语言列表
 */
export function getAvailableLanguages(): Language[] {
  return i18nState.availableLanguages;
}

/**
 * 初始化国际化系统
 */
export async function initI18n(): Promise<void> {
  if (i18nState.initialized) {
    console.warn('i18n 已经初始化');
    return;
  }

  await loadAvailableLanguages();

  const savedLang = getSavedLanguage();
  await loadTranslations(savedLang);

  setupDOMObserver();
  setupLanguageSelector();

  i18nState.initialized = true;

  console.log(`i18n 初始化完成，当前语言: ${i18nState.currentLanguage}`);
}

// ============================================================================
// 挂载到全局对象（兼容旧代码）
// ============================================================================
declare global {
  interface Window {
    i18n: {
      currentLanguage: string;
      translations: Record<string, string>;
      availableLanguages: Language[];
      initialized: boolean;
      observers: MutationObserver[];
      changeLanguage: typeof changeLanguage;
      retranslate: typeof retranslate;
      getCurrentLanguage: typeof getCurrentLanguage;
      init: typeof initI18n;
    };
    t: typeof t;
  }
}

// 挂载到 window 对象
window.i18n = {
  ...i18nState,
  changeLanguage,
  retranslate,
  getCurrentLanguage,
  init: initI18n
};
window.t = t;

// 默认导出
export default {
  t,
  changeLanguage,
  retranslate,
  getCurrentLanguage,
  getAvailableLanguages,
  initI18n
};

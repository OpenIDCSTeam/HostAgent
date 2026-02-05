/**
 * OpenIDCS 国际化/翻译系统
 * 提供非侵入式的页面翻译功能
 */

(function() {
    'use strict';
    
    // ============================================================================
    // 全局翻译对象
    // ============================================================================
    window.i18n = {
        currentLanguage: 'zh-cn',
        translations: {},
        availableLanguages: [],
        initialized: false,
        observers: [] // MutationObserver 实例数组
    };
    
    // ============================================================================
    // 语言检测与存储
    // ============================================================================
    
    /**
     * 获取浏览器语言
     */
    function getBrowserLanguage() {
        const lang = navigator.language || navigator.userLanguage;
        // 将浏览器语言代码转换为我们的格式
        if (lang.startsWith('zh')) {
            return 'zh-cn';
        } else if (lang.startsWith('en')) {
            return 'en-us';
        }
        return 'zh-cn'; // 默认中文
    }
    
    /**
     * 从localStorage获取保存的语言设置
     */
    function getSavedLanguage() {
        return localStorage.getItem('language') || getBrowserLanguage();
    }
    
    /**
     * 保存语言设置到localStorage
     */
    function saveLanguage(lang) {
        localStorage.setItem('language', lang);
    }
    
    // ============================================================================
    // API 交互
    // ============================================================================
    
    /**
     * 加载可用语言列表
     */
    async function loadAvailableLanguages() {
        try {
            const response = await fetch('/api/i18n/languages');
            const result = await response.json();
            if (result.code === 200) {
                window.i18n.availableLanguages = result.data;
                renderLanguageDropdown();
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
    async function loadTranslations(lang) {
        try {
            const response = await fetch(`/api/i18n/translations/${lang}`);
            const result = await response.json();
            if (result.code === 200) {
                window.i18n.translations = result.data;
                window.i18n.currentLanguage = lang;
                saveLanguage(lang);
                // 强制重新翻译整个页面
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
    
    // 不需要翻译的元素标签（通常是脚本、样式等）
    const SKIP_TAGS = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'IFRAME', 'OBJECT', 'EMBED']);
    
    // 不需要翻译的元素类名或ID（可根据需要扩展）
    const SKIP_CLASSES = new Set(['no-translate', 'notranslate']);
    
    // 存储原始文本的映射（用于语言切换）
    const originalTexts = new WeakMap();
    
    /**
     * 判断元素是否应该跳过翻译
     */
    function shouldSkipElement(element) {
        // 跳过特定标签
        if (SKIP_TAGS.has(element.tagName)) {
            return true;
        }
        
        // 跳过带有特定类名的元素
        if (element.classList) {
            for (const className of SKIP_CLASSES) {
                if (element.classList.contains(className)) {
                    return true;
                }
            }
        }
        
        // 跳过带有 translate="no" 属性的元素
        if (element.getAttribute('translate') === 'no') {
            return true;
        }
        
        // 跳过 contenteditable 的元素（用户可编辑内容）
        if (element.isContentEditable) {
            return true;
        }
        
        return false;
    }
    
    /**
     * 翻译文本节点
     */
    function translateTextNode(textNode, forceRetranslate = false) {
        // 保存原始文本（如果还没保存）
        if (!originalTexts.has(textNode)) {
            originalTexts.set(textNode, textNode.nodeValue);
        }
        
        // 如果是强制重新翻译，使用原始文本
        const sourceText = forceRetranslate ? originalTexts.get(textNode) : textNode.nodeValue;
        const text = sourceText.trim();
        
        // 跳过空文本或纯空白
        if (!text) {
            return;
        }
        
        // 跳过纯数字、纯符号等
        if (/^[\d\s\-_.,;:!?()[\]{}]+$/.test(text)) {
            return;
        }
        
        // 1. 优先尝试完全匹配
        const exactTranslation = window.i18n.translations[text];
        if (exactTranslation && exactTranslation !== text) {
            // 应用翻译（保持原有的空白格式）
            const leadingSpace = sourceText.match(/^\s*/)[0];
            const trailingSpace = sourceText.match(/\s*$/)[0];
            textNode.nodeValue = leadingSpace + exactTranslation + trailingSpace;
            return;
        }
        
        // 2. 尝试部分匹配翻译
        const partialTranslation = findPartialTranslation(text);
        if (partialTranslation) {
            const leadingSpace = sourceText.match(/^\s*/)[0];
            const trailingSpace = sourceText.match(/\s*$/)[0];
            textNode.nodeValue = leadingSpace + partialTranslation + trailingSpace;
        } else if (forceRetranslate) {
            // 如果是强制重新翻译但没有找到翻译，恢复原始文本
            textNode.nodeValue = sourceText;
        }
    }
    
    /**
     * 查找并应用部分匹配翻译
     * @param {string} text - 原始文本
     * @returns {string|null} 翻译后的文本，如果没有匹配则返回null
     */
    function findPartialTranslation(text) {
        // 获取所有翻译键，按长度降序排序（优先匹配长的短语）
        const translationKeys = Object.keys(window.i18n.translations)
            .filter(key => key.length > 2) // 过滤太短的键，避免误匹配
            .sort((a, b) => b.length - a.length);
        
        let result = text;
        let hasTranslation = false;
        const maxIterations = 10; // 最多迭代10次
        
        // 多次迭代翻译，确保嵌套的翻译内容也能被替换
        for (let iteration = 0; iteration < maxIterations; iteration++) {
            let iterationHasTranslation = false;
            const previousResult = result;
            
            // 记录已翻译的位置，避免重复翻译
            const translatedRanges = [];
            
            for (const key of translationKeys) {
                const translation = window.i18n.translations[key];
                
                // 跳过无效翻译
                if (!translation || translation === key) {
                    continue;
                }
                
                // 查找所有匹配位置
                let index = 0;
                while ((index = result.indexOf(key, index)) !== -1) {
                    // 检查是否与已翻译的范围重叠
                    const isOverlapping = translatedRanges.some(range => 
                        (index >= range.start && index < range.end) ||
                        (index + key.length > range.start && index + key.length <= range.end) ||
                        (index <= range.start && index + key.length >= range.end)
                    );
                    
                    if (!isOverlapping) {
                        // 执行替换
                        result = result.substring(0, index) + translation + result.substring(index + key.length);
                        
                        // 记录翻译范围
                        translatedRanges.push({
                            start: index,
                            end: index + translation.length
                        });
                        
                        iterationHasTranslation = true;
                        hasTranslation = true;
                        
                        // 更新索引，继续查找下一个匹配
                        index += translation.length;
                    } else {
                        index += key.length;
                    }
                }
            }
            
            // 如果本次迭代没有进行任何翻译，或结果没有变化，则提前退出
            if (!iterationHasTranslation || result === previousResult) {
                break;
            }
        }
        
        return hasTranslation ? result : null;
    }
    
    /**
     * 递归翻译元素及其子元素
     */
    function translateElement(element, forceRetranslate = false) {
        // 跳过不需要翻译的元素
        if (shouldSkipElement(element)) {
            return;
        }
        
        // 翻译元素的属性
        translateAttributes(element, forceRetranslate);
        
        // 遍历所有子节点
        const walker = document.createTreeWalker(
            element,
            NodeFilter.SHOW_TEXT | NodeFilter.SHOW_ELEMENT,
            {
                acceptNode: function(node) {
                    // 如果是元素节点，检查是否应该跳过
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        return shouldSkipElement(node) ? 
                            NodeFilter.FILTER_REJECT : 
                            NodeFilter.FILTER_SKIP;
                    }
                    // 文本节点接受
                    return NodeFilter.FILTER_ACCEPT;
                }
            },
            false
        );
        
        const textNodes = [];
        let node;
        while (node = walker.nextNode()) {
            if (node.nodeType === Node.TEXT_NODE) {
                textNodes.push(node);
            }
        }
        
        // 翻译所有文本节点
        textNodes.forEach(textNode => translateTextNode(textNode, forceRetranslate));
    }
    
    /**
     * 翻译元素的属性（placeholder, title, value, aria-label 等）
     */
    function translateAttributes(element, forceRetranslate = false) {
        // 存储原始属性值
        if (!element._originalAttrs && !forceRetranslate) {
            element._originalAttrs = {};
        }
        // 翻译 placeholder
        if (element.placeholder) {
            if (!element._originalAttrs.placeholder) {
                element._originalAttrs.placeholder = element.placeholder;
            }
            const text = (forceRetranslate ? element._originalAttrs.placeholder : element.placeholder).trim();
            const translation = window.i18n.translations[text];
            if (translation) {
                element.placeholder = translation;
            } else if (forceRetranslate) {
                element.placeholder = element._originalAttrs.placeholder;
            }
        }
        
        // 翻译 title
        if (element.title) {
            if (!element._originalAttrs.title) {
                element._originalAttrs.title = element.title;
            }
            const text = (forceRetranslate ? element._originalAttrs.title : element.title).trim();
            const translation = window.i18n.translations[text];
            if (translation) {
                element.title = translation;
            } else if (forceRetranslate) {
                element.title = element._originalAttrs.title;
            }
        }
        
        // 翻译 value (用于按钮等)
        if (element.value && (element.tagName === 'INPUT' || element.tagName === 'BUTTON')) {
            if (!element._originalAttrs.value) {
                element._originalAttrs.value = element.value;
            }
            const text = (forceRetranslate ? element._originalAttrs.value : element.value).trim();
            const translation = window.i18n.translations[text];
            if (translation) {
                element.value = translation;
            } else if (forceRetranslate) {
                element.value = element._originalAttrs.value;
            }
        }
        
        // 翻译 aria-label
        const ariaLabel = element.getAttribute('aria-label');
        if (ariaLabel) {
            if (!element._originalAttrs.ariaLabel) {
                element._originalAttrs.ariaLabel = ariaLabel;
            }
            const text = (forceRetranslate ? element._originalAttrs.ariaLabel : ariaLabel).trim();
            const translation = window.i18n.translations[text];
            if (translation) {
                element.setAttribute('aria-label', translation);
            } else if (forceRetranslate) {
                element.setAttribute('aria-label', element._originalAttrs.ariaLabel);
            }
        }
        
        // 翻译 alt (图片替代文本)
        if (element.alt) {
            if (!element._originalAttrs.alt) {
                element._originalAttrs.alt = element.alt;
            }
            const text = (forceRetranslate ? element._originalAttrs.alt : element.alt).trim();
            const translation = window.i18n.translations[text];
            if (translation) {
                element.alt = translation;
            } else if (forceRetranslate) {
                element.alt = element._originalAttrs.alt;
            }
        }
    }
    
    /**
     * 应用翻译到页面元素
     * @param {Element} root - 根元素，默认为document.body
     * @param {boolean} forceRetranslate - 是否强制重新翻译（用于语言切换）
     */
    function applyTranslations(root = document.body, forceRetranslate = false) {
        if (!root) return;
        
        // 如果是文档对象，从 body 开始
        if (root === document) {
            root = document.body;
        }
        
        // 翻译根元素
        if (root.nodeType === Node.ELEMENT_NODE) {
            translateElement(root, forceRetranslate);
        }
    }
    
    /**
     * 翻译函数（供JavaScript使用）
     * @param {string} key - 翻译键
     * @param {string} defaultValue - 默认值
     * @param {boolean} enablePartialMatch - 是否启用部分匹配，默认true
     * @returns {string} 翻译后的文本
     */
    window.t = function(key, defaultValue = null, enablePartialMatch = true) {
        // 优先完全匹配
        const exactTranslation = window.i18n.translations[key];
        if (exactTranslation) {
            return exactTranslation;
        }
        
        // 如果启用部分匹配，尝试部分翻译
        if (enablePartialMatch) {
            const partialTranslation = findPartialTranslation(key);
            if (partialTranslation) {
                return partialTranslation;
            }
        }
        
        // 返回默认值或原始键
        return defaultValue || key;
    };
    
    // ============================================================================
    // DOM 监听（非侵入式翻译）
    // ============================================================================
    
    /**
     * 设置 MutationObserver 监听 DOM 变化
     * 当页面动态添加新元素时自动翻译
     */
    function setupDOMObserver() {
        // 清理旧的观察器
        window.i18n.observers.forEach(observer => observer.disconnect());
        window.i18n.observers = [];
        
        // 创建观察器
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                // 处理新增的节点
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        translateElement(node);
                    } else if (node.nodeType === Node.TEXT_NODE) {
                        translateTextNode(node);
                    }
                });
                
                // 处理文本内容变化
                if (mutation.type === 'characterData') {
                    translateTextNode(mutation.target);
                }
            });
        });
        
        // 开始观察
        observer.observe(document.body, {
            childList: true,
            subtree: true,
            characterData: true
        });
        
        window.i18n.observers.push(observer);
    }
    
    // ============================================================================
    // UI 更新
    // ============================================================================
    
    /**
     * 渲染语言下拉菜单
     */
    function renderLanguageDropdown() {
        const dropdown = document.getElementById('languageDropdown');
        if (!dropdown) return;
        
        dropdown.innerHTML = window.i18n.availableLanguages.map(lang => `
            <button onclick="i18n.changeLanguage('${lang.code}')" 
                    class="w-full text-left px-4 py-2 hover:bg-gray-100 flex items-center gap-2 ${lang.code === window.i18n.currentLanguage ? 'bg-blue-50 text-blue-600' : 'text-gray-700'}">
                <span class="iconify" data-icon="${lang.code === window.i18n.currentLanguage ? 'mdi:check' : 'mdi:translate'}" data-width="16"></span>
                <span>${lang.native}</span>
            </button>
        `).join('');
    }
    
    /**
     * 更新语言显示
     */
    function updateLanguageDisplay() {
        const currentLangName = document.getElementById('currentLanguageName');
        if (currentLangName) {
            const lang = window.i18n.availableLanguages.find(l => l.code === window.i18n.currentLanguage);
            if (lang) {
                currentLangName.textContent = lang.native;
            }
        }
        renderLanguageDropdown();
    }
    
    // ============================================================================
    // 公共 API
    // ============================================================================
    
    /**
     * 切换语言
     * @param {string} lang - 语言代码
     */
    window.i18n.changeLanguage = async function(lang) {
        const success = await loadTranslations(lang);
        if (success) {
            // 关闭下拉菜单
            const dropdown = document.getElementById('languageDropdown');
            if (dropdown) {
                dropdown.classList.add('hidden');
            }
            
            // 触发自定义事件，通知其他组件语言已更改
            window.dispatchEvent(new CustomEvent('languageChanged', { 
                detail: { language: lang } 
            }));
        }
    };
    
    /**
     * 重新翻译整个页面
     */
    window.i18n.retranslate = function() {
        applyTranslations(document.body, true);
    };
    
    /**
     * 获取当前语言
     */
    window.i18n.getCurrentLanguage = function() {
        return window.i18n.currentLanguage;
    };
    
    /**
     * 初始化国际化系统
     */
    window.i18n.init = async function() {
        if (window.i18n.initialized) {
            console.warn('i18n 已经初始化');
            return;
        }
        
        // 加载可用语言列表
        await loadAvailableLanguages();
        
        // 加载保存的或浏览器默认语言
        const savedLang = getSavedLanguage();
        await loadTranslations(savedLang);
        
        // 设置 DOM 观察器（非侵入式翻译）
        setupDOMObserver();
        
        // 设置语言选择器事件
        setupLanguageSelector();
        
        window.i18n.initialized = true;
        
        console.log(`i18n 初始化完成，当前语言: ${window.i18n.currentLanguage}`);
    };
    
    /**
     * 设置语言选择器事件
     */
    function setupLanguageSelector() {
        const languageButton = document.getElementById('languageButton');
        const languageDropdown = document.getElementById('languageDropdown');
        
        if (languageButton && languageDropdown) {
            // 点击按钮切换下拉菜单
            languageButton.addEventListener('click', (e) => {
                e.stopPropagation();
                languageDropdown.classList.toggle('hidden');
            });
            
            // 点击页面其他地方关闭下拉菜单
            document.addEventListener('click', () => {
                languageDropdown.classList.add('hidden');
            });
            
            // 阻止下拉菜单内的点击事件冒泡
            languageDropdown.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        }
    }
    
    // ============================================================================
    // 自动初始化
    // ============================================================================
    
    // 当 DOM 加载完成后自动初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            window.i18n.init();
        });
    } else {
        // DOM 已经加载完成
        window.i18n.init();
    }
    
})();

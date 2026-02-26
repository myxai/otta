/**
 * i18n module for MyxAI Desk frontend
 * 
 * Provides translation services for the web UI.
 */

class I18N {
    constructor() {
        this.locale = 'zh';
        this.messages = {};
        this.fallbackLocale = 'zh';
    }

    /**
     * Initialize i18n with locale detection
     */
    async init() {
        // Detect locale from browser or user settings
        this.locale = this.detectLocale();
        
        // Load messages
        await this.loadMessages(this.locale);
        
        return this;
    }

    /**
     * Detect user locale
     */
    detectLocale() {
        // 1. Check localStorage (user preference)
        const saved = localStorage.getItem('myxai_locale');
        if (saved) return saved;

        // 2. Check browser language
        const browserLang = navigator.language || navigator.userLanguage;
        if (browserLang.startsWith('zh')) return 'zh';
        if (browserLang.startsWith('en')) return 'en';

        // 3. Default to Chinese
        return 'zh';
    }

    /**
     * Load language messages from backend
     */
    async loadMessages(locale) {
        try {
            const response = await fetch(`/api/i18n/messages?locale=${locale}`);
            if (response.ok) {
                this.messages = await response.json();
            } else {
                // Fallback to embedded messages
                this.messages = this.getEmbeddedMessages(locale);
            }
        } catch (error) {
            console.warn('Failed to load i18n messages, using embedded:', error);
            this.messages = this.getEmbeddedMessages(locale);
        }
    }

    /**
     * Get embedded messages (fallback)
     */
    getEmbeddedMessages(locale) {
        const messages = {
            zh: {
                "security.mode.Observer": "观察模式",
                "security.mode.Assistant": "协作模式",
                "security.mode.Operator": "操作模式",
                "security.mode.Developer": "开发模式",
                "security.desc.Observer": "可智能安全新增",
                "security.desc.Assistant": "可智能安全修改",
                "security.desc.Operator": "可智能安全删除/恢复",
                "security.desc.Developer": "可执行所有操作（高风险）",
                "security.full.Observer": "观察模式 — 可智能安全新增",
                "security.full.Assistant": "协作模式 — 可智能安全修改",
                "security.full.Operator": "操作模式 — 可智能安全删除/恢复",
                "security.full.Developer": "开发模式 — 可执行所有操作（高风险）",
            },
            en: {
                "security.mode.Observer": "Observer Mode",
                "security.mode.Assistant": "Assistant Mode",
                "security.mode.Operator": "Operator Mode",
                "security.mode.Developer": "Developer Mode",
                "security.desc.Observer": "Smart & Safe Create",
                "security.desc.Assistant": "Smart & Safe Modify",
                "security.desc.Operator": "Smart & Safe Delete/Restore",
                "security.desc.Developer": "Full Access (High Risk)",
                "security.full.Observer": "Observer Mode — Smart & Safe Create",
                "security.full.Assistant": "Assistant Mode — Smart & Safe Modify",
                "security.full.Operator": "Operator Mode — Smart & Safe Delete/Restore",
                "security.full.Developer": "Developer Mode — Full Access (High Risk)",
            }
        };
        return messages[locale] || messages.zh;
    }

    /**
     * Translate a key
     * @param {string} key - Translation key
     * @param {object} params - Parameters for interpolation
     * @returns {string} Translated string
     */
    t(key, params = {}) {
        let text = this.messages[key] || key;

        // String interpolation
        if (params && Object.keys(params).length > 0) {
            Object.keys(params).forEach(k => {
                text = text.replace(`{${k}}`, params[k]);
            });
        }

        return text;
    }

    /**
     * Switch to a different locale
     * @param {string} locale - New locale code
     */
    async setLocale(locale) {
        this.locale = locale;
        localStorage.setItem('myxai_locale', locale);
        await this.loadMessages(locale);
        
        // Trigger UI update (dispatch event)
        window.dispatchEvent(new CustomEvent('localeChanged', { detail: { locale } }));
    }

    /**
     * Get current locale
     */
    getLocale() {
        return this.locale;
    }
}

// Global instance
let i18nInstance = null;

/**
 * Initialize i18n (call once at app startup)
 */
async function initI18n() {
    if (!i18nInstance) {
        i18nInstance = new I18N();
        await i18nInstance.init();
    }
    return i18nInstance;
}

/**
 * Get i18n instance
 */
function getI18n() {
    if (!i18nInstance) {
        throw new Error('i18n not initialized. Call initI18n() first.');
    }
    return i18nInstance;
}

/**
 * Shorthand for translation
 */
function t(key, params) {
    return getI18n().t(key, params);
}

// Export for use in app.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { initI18n, getI18n, t };
}

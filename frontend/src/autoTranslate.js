const GOOGLE_WIDGET_SCRIPT_ID = 'google-translate-widget-script'
const GOOGLE_WIDGET_CONTAINER_ID = 'google_translate_element'

const GOOGLE_LANGUAGE_MAP = {
  'zh-CN': 'zh-CN',
  en: 'en',
  th: 'th',
  es: 'es',
  fr: 'fr',
  ru: 'ru',
  ar: 'ar',
}

let scriptLoading = false
let scriptLoaded = false
let pendingLanguage = null
let restoreRequested = false

function ensureContainer() {
  if (typeof document === 'undefined') return null
  let container = document.getElementById(GOOGLE_WIDGET_CONTAINER_ID)
  if (!container) {
    container = document.createElement('div')
    container.id = GOOGLE_WIDGET_CONTAINER_ID
    container.setAttribute('aria-hidden', 'true')
    container.style.position = 'fixed'
    container.style.left = '-9999px'
    container.style.top = '-9999px'
    container.style.width = '1px'
    container.style.height = '1px'
    container.style.overflow = 'hidden'
    document.body.appendChild(container)
  }
  return container
}

function hideGoogleChrome() {
  if (typeof document === 'undefined') return
  const styleId = 'google-translate-widget-hide-style'
  if (document.getElementById(styleId)) return
  const style = document.createElement('style')
  style.id = styleId
  style.textContent = `
    .goog-te-banner-frame,
    .goog-te-balloon-frame,
    #goog-gt-tt,
    .skiptranslate,
    .skiptranslate iframe,
    body > .skiptranslate,
    #${GOOGLE_WIDGET_CONTAINER_ID} { display: none !important; }
    body { top: 0 !important; }
    .goog-text-highlight { background: inherit !important; box-shadow: none !important; }
  `
  document.head.appendChild(style)
}

function initGoogleWidget() {
  if (typeof window === 'undefined') return
  ensureContainer()
  hideGoogleChrome()
  if (!window.google?.translate?.TranslateElement) return
  try {
    new window.google.translate.TranslateElement({
      pageLanguage: 'zh-CN',
      includedLanguages: Object.values(GOOGLE_LANGUAGE_MAP).filter(code => code !== 'zh-CN').join(','),
      autoDisplay: false,
    }, GOOGLE_WIDGET_CONTAINER_ID)
    scriptLoaded = true
    if (pendingLanguage) {
      const next = pendingLanguage
      pendingLanguage = null
      setTimeout(() => applyGoogleLanguage(next), 250)
    }
  } catch (error) {
    console.warn('[i18n] Google Translate widget init failed', error)
  }
}

function ensureScript() {
  if (typeof document === 'undefined' || typeof window === 'undefined') return
  if (scriptLoaded || scriptLoading || document.getElementById(GOOGLE_WIDGET_SCRIPT_ID)) return
  window.googleTranslateElementInit = initGoogleWidget
  scriptLoading = true
  const script = document.createElement('script')
  script.id = GOOGLE_WIDGET_SCRIPT_ID
  script.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit'
  script.async = true
  script.onerror = () => {
    scriptLoading = false
    console.warn('[i18n] Google Translate widget script failed to load')
  }
  document.head.appendChild(script)
}

function getCombo() {
  if (typeof document === 'undefined') return null
  return document.querySelector('.goog-te-combo')
}

function applyGoogleLanguage(language) {
  const combo = getCombo()
  if (!combo) {
    pendingLanguage = language
    ensureScript()
    return
  }
  if (combo.value === language) return
  combo.value = language
  combo.dispatchEvent(new Event('change'))
}

function clearGoogleCookie() {
  if (typeof document === 'undefined') return
  const expires = 'expires=Thu, 01 Jan 1970 00:00:00 GMT'
  document.cookie = `googtrans=; ${expires}; path=/`
  document.cookie = `googtrans=; ${expires}; path=/; domain=${window.location.hostname}`
}

function restoreOriginalLanguage() {
  clearGoogleCookie()
  const combo = getCombo()
  if (combo && combo.value) {
    combo.value = ''
    combo.dispatchEvent(new Event('change'))
  } else if (!restoreRequested && typeof window !== 'undefined' && document.documentElement.classList.contains('translated-ltr')) {
    restoreRequested = true
    window.location.reload()
  }
}

export function setPageAutoTranslateLanguage(code) {
  if (typeof window === 'undefined') return
  const googleLanguage = GOOGLE_LANGUAGE_MAP[code]
  if (!googleLanguage || googleLanguage === 'zh-CN') {
    pendingLanguage = null
    restoreOriginalLanguage()
    return
  }
  pendingLanguage = googleLanguage
  ensureContainer()
  hideGoogleChrome()
  ensureScript()
  setTimeout(() => applyGoogleLanguage(googleLanguage), scriptLoaded ? 50 : 600)
  setTimeout(() => applyGoogleLanguage(googleLanguage), 1500)
}

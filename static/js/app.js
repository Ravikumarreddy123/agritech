// AgriTech Global App Utilities

const AgriApp = {
  currentLang: localStorage.getItem('agritech_lang') || 'en',
  
  setLanguage(lang) {
    this.currentLang = lang;
    localStorage.setItem('agritech_lang', lang);
    // Update all elements with data-i18n attribute
    this.applyTranslations();
  },
  
  applyTranslations() {
    // Translations are applied per-page via detect.js
    // This is a placeholder for global UI strings
    const langSelect = document.getElementById('global-lang-select');
    if (langSelect) langSelect.value = this.currentLang;
  },
  
  formatDiseaseName(raw) {
    return raw
      .replace(/___/g, ' - ')
      .replace(/__/g, ' ')
      .replace(/_/g, ' ')
      .trim();
  },
  
  getRiskColor(level) {
    const colors = {
      'LOW': '#2e7d32',
      'MEDIUM': '#ff8f00',
      'HIGH': '#c62828',
      'GENERAL': '#1565c0'
    };
    return colors[level] || '#555';
  },
  
  showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
      toast.classList.remove('show');
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }
};

document.addEventListener('DOMContentLoaded', () => {
  AgriApp.applyTranslations();
  // Set language selector to stored preference
  const sel = document.getElementById('global-lang-select');
  if (sel) {
    sel.value = AgriApp.currentLang;
    sel.addEventListener('change', (e) => {
      AgriApp.setLanguage(e.target.value);
    });
  }
});

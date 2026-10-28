// AgriTech Voice Advisory Module
// Uses browser's built-in Web Speech API (offline capable)
// No external TTS service required

const VoiceAdvisory = {
  synthesis: window.speechSynthesis || null,
  currentUtterance: null,
  isAvailable: false,
  
  init() {
    this.isAvailable = !!(window.speechSynthesis);
    if (this.isAvailable) {
      // Eagerly load voices (async in some browsers)
      window.speechSynthesis.getVoices();
      if (window.speechSynthesis.onvoiceschanged !== undefined) {
        window.speechSynthesis.onvoiceschanged = () => window.speechSynthesis.getVoices();
      }
    }
    return this.isAvailable;
  },
  
  getLangCode(lang) {
    const map = { en: 'en-US', hi: 'hi-IN', te: 'te-IN' };
    return map[lang] || 'en-US';
  },
  
  speak(text, lang = 'en', onStart, onEnd, onError) {
    if (!this.isAvailable) {
      if (onError) onError('Voice output is not available on this device.');
      return;
    }
    
    this.stop();
    
    const langCode = this.getLangCode(lang);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = langCode;
    utterance.rate = 0.9;
    
    // Explicitly find and assign a voice for the requested language
    const voices = window.speechSynthesis.getVoices();
    
    // Some browsers use underscore instead of hyphen
    const searchLang1 = langCode.toLowerCase().replace('_', '-');
    const searchLang2 = lang.toLowerCase();
    
    const matchingVoice = voices.find(v => {
      const vLang = v.lang.toLowerCase().replace('_', '-');
      return vLang.startsWith(searchLang1) || vLang.startsWith(searchLang2);
    });
    
    if (matchingVoice) {
      utterance.voice = matchingVoice;
    } else if (lang !== 'en') {
      // Important: If we can't find a voice for Hindi/Telugu, the English voice will try to read it 
      // and it will sound like gibberish or be totally silent.
      if (onError) {
        let langName = lang === 'hi' ? 'Hindi' : 'Telugu';
        onError(`No ${langName} voice found on this device. Please install it in your OS settings or use Google Chrome.`);
      }
      return; // Stop playback
    }

    utterance.onstart = onStart || null;
    utterance.onend = onEnd || null;
    utterance.onerror = (e) => {
      if (onError) onError('Voice playback failed: ' + e.error);
    };
    
    this.currentUtterance = utterance;
    this.synthesis.speak(utterance);
  },
  
  stop() {
    if (this.synthesis) {
      this.synthesis.cancel();
    }
    this.currentUtterance = null;
  },
  
  isSpeaking() {
    return this.synthesis ? this.synthesis.speaking : false;
  }
};

// Initialize on load
document.addEventListener('DOMContentLoaded', () => {
  VoiceAdvisory.init();
});

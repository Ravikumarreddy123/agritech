let currentDisease = null;
let currentAdvisoryText = '';

document.addEventListener('DOMContentLoaded', () => {
  initDetectPage();
});

function initDetectPage() {
  const fileInput = document.getElementById('image-input');
  const uploadZone = document.getElementById('upload-zone');
  const analyzeBtn = document.getElementById('analyze-btn');
  const langSelect = document.getElementById('global-lang-select');
  const modeToggle = document.getElementById('mode-toggle');
  const voiceBtn = document.getElementById('voice-btn');
  const tabBtns = document.querySelectorAll('.tab-btn');

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) {
        previewImage(e.target.files[0]);
      }
    });
  }

  if (uploadZone && fileInput) {
    uploadZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      uploadZone.classList.add('dragover');
    });

    uploadZone.addEventListener('dragleave', () => {
      uploadZone.classList.remove('dragover');
    });

    uploadZone.addEventListener('drop', (e) => {
      e.preventDefault();
      uploadZone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) {
        fileInput.files = e.dataTransfer.files;
        previewImage(e.dataTransfer.files[0]);
      }
    });

    uploadZone.addEventListener('click', () => {
      fileInput.click();
    });
  }

  if (analyzeBtn) {
    analyzeBtn.addEventListener('click', analyzeImage);
  }

  if (langSelect) {
    langSelect.addEventListener('change', (e) => {
      switchLanguage(e.target.value);
    });
  }

  if (voiceBtn) {
    voiceBtn.addEventListener('click', () => {
      if (VoiceAdvisory.isSpeaking()) {
        VoiceAdvisory.stop();
        voiceBtn.innerHTML = '<i class="fas fa-volume-up"></i> Listen to Advisory';
      } else {
        const lang = getSelectedLanguage();
        VoiceAdvisory.speak(currentAdvisoryText, lang, 
          () => { voiceBtn.innerHTML = '<i class="fas fa-stop"></i> Stop Listening'; },
          () => { voiceBtn.innerHTML = '<i class="fas fa-volume-up"></i> Listen to Advisory'; },
          (err) => { AgriApp.showToast(err, 'error'); }
        );
      }
    });
  }

  tabBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      const tabName = e.target.getAttribute('data-tab');
      if (tabName) showTab(tabName);
    });
  });
}

function previewImage(file) {
  const preview = document.getElementById('image-preview');
  const uploadIcon = document.getElementById('upload-icon');
  const uploadText = document.getElementById('upload-text');

  if (!file.type.match('image.*')) {
    showError("Please select a valid image file.");
    return;
  }

  const reader = new FileReader();
  reader.onload = (e) => {
    preview.src = e.target.result;
    preview.style.display = 'block';
    if(uploadIcon) uploadIcon.style.display = 'none';
    if(uploadText) uploadText.textContent = file.name;
    clearError();
  };
  reader.readAsDataURL(file);
}

async function analyzeImage() {
  const fileInput = document.getElementById('image-input');
  const file = fileInput && fileInput.files[0];
  
  if (!file) {
    showError("Please select or drop an image first.");
    return;
  }

  const envData = getEnvData();
  if (envData === null) return; // Validation failed

  showLoading("Analyzing crop image...");
  clearError();

  const formData = new FormData();
  formData.append('file', file);
  
  const mode = getMode();
  formData.append('mode', mode);
  
  const lang = getSelectedLanguage();
  formData.append('lang', lang);

  if (envData && Object.keys(envData).length > 0) {
    formData.append('env', JSON.stringify(envData));
  }

  try {
    const response = await fetch('/predict', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      const errText = await response.text();
      throw new Error(`Server Error: ${response.status} - ${errText}`);
    }

    const data = await response.json();
    if (data.error) {
      throw new Error(data.error);
    }
    
    currentDisease = data.disease;
    displayResults(data);
  } catch (error) {
    console.error("Analysis Error:", error);
    showError(error.message || "An error occurred during analysis. Please try again.");
  } finally {
    hideLoading();
  }
}

function displayResults(data) {
  const resultSection = document.getElementById('result-section');
  if (!resultSection) return;

  // Disease Name & Confidence
  const diseaseNameEl = document.getElementById('disease-name');
  if (diseaseNameEl) diseaseNameEl.textContent = AgriApp.formatDiseaseName(data.disease);

  const confFill = document.getElementById('confidence-fill');
  const confText = document.getElementById('confidence-text');
  if (confFill && data.confidence) {
    setTimeout(() => { confFill.style.width = `${(data.confidence * 100).toFixed(1)}%`; }, 100);
  }
  if (confText && data.confidence) {
    confText.textContent = `${(data.confidence * 100).toFixed(1)}% Confidence`;
  }

  // Low Confidence Warning
  const lowConfWarn = document.getElementById('low-confidence-warning');
  if (lowConfWarn) {
    lowConfWarn.style.display = data.low_confidence ? 'block' : 'none';
  }

  // Validation Error
  const valErr = document.getElementById('validation-error');
  if (valErr) {
    valErr.style.display = data.validation_error ? 'block' : 'none';
    if(data.validation_error) valErr.textContent = data.validation_error;
  }

  // Risk Badge
  const riskBadge = document.getElementById('risk-badge');
  if (riskBadge && data.risk) {
    riskBadge.textContent = `${data.risk.level} RISK`;
    riskBadge.className = `risk-badge ${data.risk.level}`;
    riskBadge.style.backgroundColor = ''; // Clear inline styles
  }

  // Risk Reasons
  const riskReasonsList = document.getElementById('risk-reasons-list');
  if (riskReasonsList && data.risk && data.risk.reasons) {
    riskReasonsList.innerHTML = '';
    data.risk.reasons.forEach(reason => {
      const li = document.createElement('li');
      li.textContent = reason;
      riskReasonsList.appendChild(li);
    });
  }

  // Mode Badge
  const modeBadge = document.getElementById('mode-badge');
  if (modeBadge) {
    modeBadge.textContent = data.mode === 'offline' ? 'OFFLINE MODE' : 'ONLINE MODE';
  }

  // Advisory Tabs Content
  if (data.advisory) {
    updateAdvisoryDOM(data.advisory);
  }

  const placeholder = document.getElementById('no-result-placeholder');
  if (placeholder) {
    placeholder.style.display = 'none';
  }

  resultSection.style.display = 'block';
  resultSection.classList.add('show');
  resultSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function updateAdvisoryDOM(advisory) {
  const ids = ['symptoms', 'cause', 'treatment', 'prevention'];
  let combinedText = '';

  ids.forEach(id => {
    const el = document.getElementById(`tab-${id}`);
    if (el) {
      if (Array.isArray(advisory[id])) {
        el.innerHTML = `<ul>${advisory[id].map(item => `<li>${item}</li>`).join('')}</ul>`;
        combinedText += `${id.toUpperCase()}: ${advisory[id].join('. ')}. `;
      } else {
        el.innerHTML = `<p>${advisory[id] || 'Information not available.'}</p>`;
        if (advisory[id]) combinedText += `${id.toUpperCase()}: ${advisory[id]}. `;
      }
    }
  });

  currentAdvisoryText = combinedText;

  const transNotice = document.getElementById('translation-notice');
  if (transNotice) {
    transNotice.style.display = advisory.fallback ? 'block' : 'none';
  }
}

async function switchLanguage(lang) {
  if (!currentDisease) return;

  showLoading("Translating advisory...");
  try {
    const response = await fetch(`/api/advisory/${encodeURIComponent(currentDisease)}?lang=${lang}`);
    if (!response.ok) throw new Error("Translation failed");
    
    const data = await response.json();
    updateAdvisoryDOM(data);
  } catch (err) {
    console.error(err);
    AgriApp.showToast("Could not translate advisory.", "error");
  } finally {
    hideLoading();
  }
}

function getEnvData() {
  const envFields = ['temperature', 'humidity', 'soil_moisture', 'leaf_wetness'];
  const envData = {};
  let hasData = false;
  let isValid = true;

  envFields.forEach(field => {
    const el = document.getElementById(`env-${field}`);
    if (el && el.value.trim() !== '') {
      hasData = true;
      const val = parseFloat(el.value);
      if (isNaN(val)) {
        showError(`Invalid value for ${field}`);
        isValid = false;
      } else {
        if (field === 'temperature' && (val < 0 || val > 60)) {
          showError("Temperature must be between 0 and 60 °C");
          isValid = false;
        }
        if (field !== 'temperature' && (val < 0 || val > 100)) {
          showError(`${field.replace('_', ' ')} must be between 0 and 100 %`);
          isValid = false;
        }
        envData[field] = val;
      }
    }
  });

  if (!isValid) return null;
  return hasData ? envData : {};
}

function showTab(tabName) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

  const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabName}"]`);
  const activeContent = document.getElementById(`tab-${tabName}`);

  if (activeBtn) activeBtn.classList.add('active');
  if (activeContent) activeContent.classList.add('active');
}

function showLoading(message) {
  const overlay = document.getElementById('loading-overlay');
  const text = document.getElementById('loading-text');
  if (overlay) overlay.classList.add('active');
  if (text && message) text.textContent = message;
}

function hideLoading() {
  const overlay = document.getElementById('loading-overlay');
  if (overlay) overlay.classList.remove('active');
}

function showError(message) {
  const errEl = document.getElementById('form-error');
  if (errEl) {
    errEl.textContent = message;
    errEl.style.display = 'block';
  } else {
    AgriApp.showToast(message, 'error');
  }
}

function clearError() {
  const errEl = document.getElementById('form-error');
  if (errEl) {
    errEl.textContent = '';
    errEl.style.display = 'none';
  }
}

function getSelectedLanguage() {
  const sel = document.getElementById('advisory-lang-select');
  return sel ? sel.value : 'en';
}

function getMode() {
  const toggle = document.getElementById('mode-switch-input');
  return toggle && toggle.checked ? 'online' : 'offline';
}

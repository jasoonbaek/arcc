/* ARCC - CSV Upload */

(function() {
  const csvInput = document.getElementById('csvInput');
  const uploadArea = document.getElementById('uploadArea');
  const uploadLoading = document.getElementById('uploadLoading');

  // Global reset helper (called by router when leaving upload screen)
  window.Upload = {
    isAnalyzing: false,
    reset() {
      window.Upload.isAnalyzing = false;
      uploadArea.style.display = '';
      uploadLoading.style.display = '';
      document.getElementById('uploadStatus').textContent = '파일 분석 중...';
      csvInput.value = '';
    },
    async checkProfile() {
      try {
        const res = await Api.get('/api/profile');
        return !!(res.profile && res.profile.age && res.profile.weight);
      } catch { return false; }
    }
  };

  // File input change (Bug #1: expanded accept for mobile)
  csvInput.addEventListener('change', function(e) {
    const file = e.target.files[0];
    if (file) handleFile(file);
  });

  // Drag & drop
  uploadArea.addEventListener('dragover', function(e) {
    e.preventDefault();
    uploadArea.classList.add('dragover');
  });

  uploadArea.addEventListener('dragleave', function() {
    uploadArea.classList.remove('dragover');
  });

  uploadArea.addEventListener('drop', function(e) {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  });

  async function handleFile(file) {
    // Prevent concurrent uploads (infinite-loop guard)
    if (window.Upload.isAnalyzing) {
      showToast('이미 분석이 진행 중입니다', true);
      return;
    }
    // Validate file
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['csv', 'txt'].includes(ext)) {
      showToast('CSV 파일만 업로드할 수 있습니다', true);
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      showToast('파일 크기가 10MB를 초과합니다', true);
      return;
    }

    // Profile guidance (optional but recommended)
    const hasProfile = await window.Upload.checkProfile();
    if (!hasProfile) {
      showToast('💡 정확한 분석을 위해 마이 > 신체정보를 입력해주세요', false);
    }

    // Show loading + timeout safeguard (max 60s)
    window.Upload.isAnalyzing = true;
    uploadArea.style.display = 'none';
    uploadLoading.style.display = 'block';
    document.getElementById('uploadStatus').textContent = '파일 분석 중...';

    const statusTimer = setTimeout(() => {
      document.getElementById('uploadStatus').textContent = 'AI 코칭 생성 중... 잠시만 기다려주세요';
    }, 5000);

    // Hard timeout to prevent stuck loading state
    const hardTimeout = setTimeout(() => {
      if (window.Upload.isAnalyzing) {
        window.Upload.isAnalyzing = false;
        window.Upload.reset();
        showToast('분석 시간이 너무 오래 걸립니다. 다시 시도해주세요', true);
      }
    }, 60000);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const result = await Api.upload('/api/upload', formData);

      clearTimeout(statusTimer);
      clearTimeout(hardTimeout);
      window.Upload.isAnalyzing = false;
      // Reset UI for next visit BEFORE navigating away
      window.Upload.reset();
      App.navigate('analysis', result);
      showToast('분석이 완료되었습니다!');
    } catch (e) {
      clearTimeout(statusTimer);
      clearTimeout(hardTimeout);
      window.Upload.isAnalyzing = false;
      window.Upload.reset();
      showToast(e.message || '업로드에 실패했습니다', true);
    }
  }
})();

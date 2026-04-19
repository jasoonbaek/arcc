/* ARCC - Authentication */

const Auth = {
  async login() {
    const email = document.getElementById('loginEmail').value.trim();
    const password = document.getElementById('loginPassword').value.trim();
    const errorEl = document.getElementById('loginError');
    errorEl.textContent = '';

    if (!email || !password) {
      errorEl.textContent = '이메일과 비밀번호를 입력해주세요';
      return;
    }

    try {
      document.getElementById('loginBtn').disabled = true;
      const res = await Api.post('/api/auth/login', { email, password });
      App.user = res.user;

      if (!res.has_disclaimer) {
        App.navigate('disclaimer');
      } else {
        App.navigate('dashboard');
      }
    } catch (e) {
      errorEl.textContent = e.message;
    } finally {
      document.getElementById('loginBtn').disabled = false;
    }
  },

  async signup() {
    const name = document.getElementById('signupName').value.trim();
    const email = document.getElementById('signupEmail').value.trim();
    const password = document.getElementById('signupPassword').value.trim();
    const errorEl = document.getElementById('signupError');
    errorEl.textContent = '';

    if (!name || !email || !password) {
      errorEl.textContent = '모든 필드를 입력해주세요';
      return;
    }
    if (password.length < 6) {
      errorEl.textContent = '비밀번호는 6자 이상이어야 합니다';
      return;
    }

    try {
      document.getElementById('signupBtn').disabled = true;
      const res = await Api.post('/api/auth/signup', { name, email, password });
      App.user = res.user;
      App.navigate('disclaimer');
    } catch (e) {
      errorEl.textContent = e.message;
    } finally {
      document.getElementById('signupBtn').disabled = false;
    }
  },

  async logout() {
    try {
      await Api.post('/api/auth/logout', {});
    } catch {}

    // Clear ALL client-side state to prevent data leak between accounts
    App.user = null;
    try { localStorage.clear(); } catch {}
    try { sessionStorage.clear(); } catch {}

    // Reset forms
    if (window.Profile && Profile.resetForm) Profile.resetForm();
    if (window.Goals && Goals.resetForm) Goals.resetForm();
    if (window.Upload && Upload.reset) Upload.reset();

    // Reset auth forms
    ['loginForm', 'signupForm'].forEach(id => {
      const f = document.getElementById(id);
      if (f) f.reset();
    });
    ['loginError', 'signupError'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.textContent = '';
    });

    // Reset transient containers
    const ac = document.getElementById('analysisContent');
    if (ac) ac.innerHTML = '';
    const hl = document.getElementById('historyList');
    if (hl) hl.innerHTML = '';

    App.navigate('login');
    showToast('로그아웃되었습니다');
  }
};

/* Onboarding */
const Onboarding = {
  async agreeDisclaimer() {
    const checked = document.getElementById('disclaimerCheck').checked;
    if (!checked) {
      showToast('동의에 체크해주세요', true);
      return;
    }
    try {
      await Api.post('/api/disclaimer', {});
      App.navigate('experience');
    } catch (e) {
      showToast(e.message, true);
    }
  }
};

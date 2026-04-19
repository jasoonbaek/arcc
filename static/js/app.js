/* ARCC Phase 2 - SPA Router & Common Utilities */

const App = {
  currentScreen: null,
  user: null,

  async init() {
    // Prevent horizontal scroll (Bug #2)
    document.addEventListener('wheel', function(e) {
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        e.preventDefault();
      }
    }, { passive: false });

    // Check auth status
    try {
      const res = await Api.get('/api/auth/me');
      if (res.user) {
        App.user = res.user;
        App.navigate('dashboard');
      } else {
        App.navigate('login');
      }
    } catch {
      App.navigate('login');
    }
  },

  navigate(screen, data) {
    // Hide all screens
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));

    // Reset forms when leaving auth screens (Bug #3)
    if (App.currentScreen === 'login' || App.currentScreen === 'signup') {
      const form = document.getElementById(App.currentScreen === 'login' ? 'loginForm' : 'signupForm');
      if (form) form.reset();
      const errorEl = document.getElementById(App.currentScreen === 'login' ? 'loginError' : 'signupError');
      if (errorEl) errorEl.textContent = '';
    }

    // Reset upload screen state when leaving (prevents stuck "파일 분석 중..." on return)
    if (App.currentScreen === 'upload' && screen !== 'upload' && window.Upload) {
      // Only reset if not currently analyzing — otherwise the in-flight handler will finish
      if (!window.Upload.isAnalyzing) window.Upload.reset();
    }

    // Show target screen
    const el = document.getElementById('screen-' + screen);
    if (el) {
      el.classList.add('active');
      window.scrollTo(0, 0);
    }

    // Tab bar visibility
    const authScreens = ['login', 'signup', 'disclaimer', 'experience'];
    const tabBar = document.getElementById('tabBar');
    if (authScreens.includes(screen)) {
      tabBar.classList.remove('visible');
    } else {
      tabBar.classList.add('visible');
      // Update active tab
      document.querySelectorAll('.tab-item').forEach(t => t.classList.remove('active'));
      const tabMap = { dashboard: 'dashboard', history: 'history', upload: 'upload', mypage: 'mypage', analysis: 'upload', goals: 'mypage', profile: 'mypage' };
      const activeTab = tabMap[screen];
      if (activeTab) {
        const tab = document.querySelector(`.tab-item[data-tab="${activeTab}"]`);
        if (tab) tab.classList.add('active');
      }
    }

    App.currentScreen = screen;

    // Screen-specific init
    switch (screen) {
      case 'dashboard': Dashboard.load(); break;
      case 'history': History.load(); break;
      case 'mypage': MyPage.load(); break;
      case 'analysis': if (data) Analysis.render(data); break;
      case 'goals': Goals.load(); break;
      case 'profile': Profile.load(); break;
      case 'upload':
        // Always start upload screen fresh unless a request is genuinely in-flight
        if (window.Upload && !window.Upload.isAnalyzing) window.Upload.reset();
        // Show profile recommendation banner if missing
        if (window.Upload) {
          window.Upload.checkProfile().then(has => {
            const banner = document.getElementById('uploadProfileBanner');
            if (banner) banner.style.display = has ? 'none' : 'block';
          });
        }
        break;
    }
  }
};

/* ===== API Helper ===== */
const Api = {
  async get(url) {
    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'API 오류');
    return data;
  },

  async post(url, body) {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'API 오류');
    return data;
  },

  async upload(url, formData) {
    const res = await fetch(url, { method: 'POST', body: formData });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || 'API 오류');
    return data;
  }
};

/* ===== Toast ===== */
function showToast(msg, isError) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = 'toast visible' + (isError ? ' error' : '');
  setTimeout(() => el.classList.remove('visible'), 3000);
}

/* ===== Modal ===== */
const Modal = {
  show(title, bodyHTML) {
    document.getElementById('modalTitle').textContent = title;
    document.getElementById('modalBody').innerHTML = bodyHTML;
    document.getElementById('modalOverlay').classList.add('visible');
  },
  close(e) {
    if (e && e.target !== document.getElementById('modalOverlay')) return;
    document.getElementById('modalOverlay').classList.remove('visible');
  }
};

/* ===== Metrics Helpers ===== */
const MetricsHelper = {
  lrsInfo(score) {
    if (score >= 80) return { emoji: '\u{1F31F}', desc: '매우 안정적으로 달렸어요!' };
    if (score >= 60) return { emoji: '\u{1F60A}', desc: '일정하게 잘 달렸어요' };
    if (score >= 40) return { emoji: '\u{1F610}', desc: '페이스 변동이 있었어요' };
    return { emoji: '\u{1F613}', desc: '페이스 조절 연습이 필요해요' };
  },
  fiInfo(score) {
    if (score <= 30) return { emoji: '\u{1F4AA}', desc: '회복 상태 좋아요!' };
    if (score <= 50) return { emoji: '\u{1F60A}', desc: '적당한 상태예요' };
    if (score <= 70) return { emoji: '\u{1F610}', desc: '좀 쉬어가세요' };
    return { emoji: '\u26A0\uFE0F', desc: '휴식이 필요해요!' };
  },
  tiInfo(ti) {
    const map = {
      low: { kr: '저강도', desc: '가벼운 운동이었어요' },
      moderate: { kr: '중강도', desc: '적당한 운동이었어요' },
      high: { kr: '고강도', desc: '힘든 운동이었어요' },
      very_high: { kr: '최고강도', desc: '아주 힘든 운동이었어요!' }
    };
    return map[ti] || map.moderate;
  },
  formatDuration(sec) {
    if (!sec) return '0:00';
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) return `${h}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
    return `${m}:${String(s).padStart(2,'0')}`;
  },
  formatDate(dateStr) {
    if (!dateStr) return '-';
    const d = new Date(dateStr);
    const days = ['일','월','화','수','목','금','토'];
    return `${d.getMonth()+1}/${d.getDate()}(${days[d.getDay()]})`;
  }
};

/* ===== Analysis Renderer ===== */
const Analysis = {
  render(data) {
    const sess = data.session;
    const metrics = Array.isArray(sess.session_metrics) ? sess.session_metrics[0] : sess.session_metrics;
    const feedback = Array.isArray(sess.ai_feedbacks) ? sess.ai_feedbacks[0] : sess.ai_feedbacks;
    const splits = Array.isArray(sess.splits) ? sess.splits.sort((a,b) => a.split_number - b.split_number) : [];
    const isSample = data.is_sample;

    const strengths = feedback ? (typeof feedback.strengths === 'string' ? JSON.parse(feedback.strengths) : feedback.strengths) : [];
    const improvements = feedback ? (typeof feedback.improvements === 'string' ? JSON.parse(feedback.improvements) : feedback.improvements) : [];
    const nextTraining = feedback ? (typeof feedback.next_training === 'string' ? JSON.parse(feedback.next_training) : feedback.next_training) : null;

    let html = '';

    // Run banner
    html += `<div class="card animate delay-1">
      <div style="display:flex;align-items:center;gap:12px;">
        <span style="font-family:'Bebas Neue';font-size:22px;color:var(--accent);">${MetricsHelper.formatDate(sess.run_date)}</span>
        <span style="font-size:11px;color:var(--muted);padding:3px 10px;border:1px solid var(--border);border-radius:20px;">OUTDOOR RUN</span>
      </div>
    </div>`;

    // KPI Grid
    html += `<div class="kpi-grid animate delay-1">
      <div class="kpi-card highlight"><div class="kpi-label">총 거리</div><div class="kpi-value">${parseFloat(sess.distance).toFixed(1)}</div><div class="kpi-unit">km</div></div>
      <div class="kpi-card"><div class="kpi-label">운동 시간</div><div class="kpi-value">${MetricsHelper.formatDuration(sess.duration)}</div><div class="kpi-unit">mm:ss</div></div>
      <div class="kpi-card"><div class="kpi-label">칼로리</div><div class="kpi-value">${sess.calories || 0}</div><div class="kpi-unit">kcal</div></div>
      <div class="kpi-card"><div class="kpi-label">평균 페이스</div><div class="kpi-value">${sess.avg_pace || '-'}</div><div class="kpi-unit">분/km</div></div>
      <div class="kpi-card warning"><div class="kpi-label">평균 심박수</div><div class="kpi-value">${sess.avg_hr || '-'}</div><div class="kpi-unit">bpm · 최고 ${sess.max_hr || '-'}</div></div>
      <div class="kpi-card"><div class="kpi-label">케이던스</div><div class="kpi-value">${sess.avg_cadence || '-'}</div><div class="kpi-unit">spm</div></div>
    </div>`;

    // AI Feedback Summary + Metrics
    if (feedback || metrics) {
      html += `<div class="card animate delay-2">
        <div class="card-title">\u{1F4CA} 분석 결과</div>`;

      if (feedback && feedback.summary) {
        html += `<div class="ai-summary-text">"${feedback.summary}"</div>`;
      }

      if (metrics) {
        const lrs = MetricsHelper.lrsInfo(metrics.lrs);
        const fi = MetricsHelper.fiInfo(metrics.fi);
        const ti = MetricsHelper.tiInfo(metrics.ti);
        html += `<div style="margin-top:8px;">
          <div class="condition-item">
            <div class="condition-left"><span class="condition-label">페이스 안정도: <span class="condition-score">${metrics.lrs}점</span> ${lrs.emoji}</span></div>
            <button class="help-btn" onclick="MetricsPopup.showLRS()">?</button>
          </div>
          <div class="condition-item">
            <div class="condition-left"><span class="condition-label">피로도: <span class="condition-score">${metrics.fi}점</span> ${fi.emoji}</span></div>
            <button class="help-btn" onclick="MetricsPopup.showFI()">?</button>
          </div>
          <div class="condition-item">
            <div class="condition-left"><span class="condition-label">훈련 강도: <span class="condition-score">${ti.kr}</span></span></div>
            <button class="help-btn" onclick="MetricsPopup.showTI()">?</button>
          </div>
        </div>`;
      }

      // Collapsible detail
      if (strengths.length || improvements.length) {
        html += `<div class="ai-detail-toggle" onclick="this.nextElementSibling.classList.toggle('visible');this.innerHTML=this.nextElementSibling.classList.contains('visible')?'상세 분석 접기 \u25B2':'상세 분석 보기 \u25BC'">상세 분석 보기 \u25BC</div>
        <div class="ai-detail-content">`;

        if (strengths.length) {
          html += `<div class="ai-section-title">\u2705 잘한 점</div><ul class="ai-list">`;
          strengths.forEach(s => html += `<li>\u2022 ${s}</li>`);
          html += `</ul>`;
        }
        if (improvements.length) {
          html += `<div class="ai-section-title">\u{1F4A1} 개선점</div><ul class="ai-list">`;
          improvements.forEach(s => html += `<li>\u2022 ${s}</li>`);
          html += `</ul>`;
        }
        html += `</div>`;
      }
      html += `</div>`;
    }

    // Next training recommendation
    if (nextTraining) {
      html += `<div class="card animate delay-2">
        <div class="card-title">\u{1F3AF} 다음 훈련 추천</div>
        <div class="recommend-card">
          <div class="recommend-type">\u{1F3C3} ${nextTraining.type || ''}</div>
          <div class="recommend-detail">${nextTraining.duration || ''} | ${nextTraining.pace || ''} | ${nextTraining.zone || ''}</div>
          <div class="recommend-desc">"${nextTraining.description || ''}"</div>
        </div>
      </div>`;
    }

    // Charts - Pace
    if (splits.length) {
      const paces = splits.map(sp => {
        const parts = (sp.pace || '0:00').split(':').map(Number);
        return parts.length === 2 ? parts[0]*60+parts[1] : 0;
      });
      const maxP = Math.max(...paces);
      const minP = Math.min(...paces);
      const range = maxP - minP || 1;

      html += `<div class="chart-card animate delay-3"><div class="chart-title">구간별 페이스</div><div class="bar-chart">`;
      splits.forEach((sp, i) => {
        const pct = 40 + ((maxP - paces[i]) / range) * 55;
        html += `<div class="bar-row"><div class="bar-label">${sp.split_number}km</div><div class="bar-track"><div class="bar-fill" style="width:${pct}%">${sp.pace}/km</div></div></div>`;
      });
      html += `</div></div>`;

      // HR chart
      const maxHR = Math.max(...splits.map(s => s.max_hr || 0));
      html += `<div class="chart-card animate delay-3"><div class="chart-title">구간별 심박수</div><div class="bar-chart">`;
      splits.forEach(sp => {
        const pct = maxHR > 0 ? Math.max(8, (sp.avg_hr / maxHR) * 100) : 50;
        html += `<div class="bar-row"><div class="bar-label">${sp.split_number}km</div><div class="bar-track"><div class="bar-fill hr" style="width:${pct}%">${sp.avg_hr} bpm</div></div></div>`;
      });
      html += `</div></div>`;

      // Splits table
      html += `<div class="chart-card animate delay-3"><div class="chart-title">구간별 상세 데이터</div>
        <div style="overflow-x:auto;"><table class="splits-table"><thead><tr><th>구간</th><th>페이스</th><th>심박</th><th>케이던스</th></tr></thead><tbody>`;
      splits.forEach(sp => {
        html += `<tr><td>${sp.split_number}km</td><td>${sp.pace}</td><td>${sp.avg_hr}</td><td>${sp.cadence}</td></tr>`;
      });
      html += `<tr><td>전체</td><td>${sess.avg_pace}</td><td>${sess.avg_hr}</td><td>${sess.avg_cadence}</td></tr>`;
      html += `</tbody></table></div></div>`;

      // Zone distribution
      const estMax = 190;
      const zones = [
        { name: 'Z1', label: '회복', color: '#4ade80', min: 0, max: 0.6 },
        { name: 'Z2', label: '유산소', color: '#facc15', min: 0.6, max: 0.7 },
        { name: 'Z3', label: '유산소+', color: '#fb923c', min: 0.7, max: 0.8 },
        { name: 'Z4', label: '무산소', color: '#f87171', min: 0.8, max: 0.9 },
        { name: 'Z5', label: '최대', color: '#e879f9', min: 0.9, max: 1.0 },
      ];
      const zoneCounts = [0,0,0,0,0];
      splits.forEach(sp => {
        const ratio = sp.avg_hr / estMax;
        const zi = zones.findIndex((z,i) => ratio >= z.min && (i===4 || ratio < zones[i+1].min));
        if (zi >= 0) zoneCounts[zi]++;
      });
      const total = splits.length || 1;

      html += `<div class="chart-card animate delay-3"><div class="chart-title">심박수 강도 구간 분포</div><div class="zone-bars">`;
      zones.forEach((z,i) => {
        const pct = (zoneCounts[i]/total)*100;
        const h = Math.max(4, pct*0.8);
        html += `<div class="zone-bar-wrap"><div class="zone-pct">${Math.round(pct)}%</div><div class="zone-bar" style="height:${h}px;background:${z.color};"></div></div>`;
      });
      html += `</div><div class="zone-labels">`;
      zones.forEach(z => {
        html += `<div class="zone-label-item"><div class="zone-label-name" style="color:${z.color}">${z.name}</div><div class="zone-label-desc">${z.label}</div></div>`;
      });
      html += `</div></div>`;
    }

    // Sample banner
    if (isSample) {
      html += `<div class="sample-banner">
        <div class="sample-banner-text">\u{1F4A1} 이건 샘플 분석이에요!</div>
        <button class="btn btn-primary btn-sm" onclick="App.navigate('upload')">내 데이터로 분석받기</button>
      </div>`;
    }

    document.getElementById('analysisContent').innerHTML = html;
  }
};

// Init on load
document.addEventListener('DOMContentLoaded', App.init);

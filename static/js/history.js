/* ARCC - History */

const History = {
  currentFilter: 'all',

  async load() {
    History.setFilter('all');
  },

  async setFilter(filter) {
    History.currentFilter = filter;

    // Update filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.filter === filter);
    });

    try {
      const data = await Api.get(`/api/sessions?filter=${filter}`);
      History.renderList(data.sessions || []);
    } catch (e) {
      showToast(e.message, true);
    }
  },

  renderList(sessions) {
    const container = document.getElementById('historyList');

    if (!sessions.length) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-state-icon">\u{1F3C3}</div>
          <div class="empty-state-text">러닝 기록이 없어요.<br>CSV를 업로드해보세요!</div>
        </div>`;
      return;
    }

    let html = '';
    sessions.forEach(s => {
      const m = Array.isArray(s.session_metrics) && s.session_metrics[0] ? s.session_metrics[0] : s.session_metrics;
      const ti = m ? MetricsHelper.tiInfo(m.ti) : null;
      const lrs = m ? MetricsHelper.lrsInfo(m.lrs) : null;
      const fi = m ? MetricsHelper.fiInfo(m.fi) : null;

      html += `
        <div class="history-item" onclick="History.viewSession('${s.id}')">
          <div class="history-header">
            <div class="history-date">${MetricsHelper.formatDate(s.run_date)} ${s.is_sample ? '(샘플)' : ''}</div>
            ${ti ? `<span class="recent-run-intensity intensity-${m.ti}">${ti.kr}</span>` : ''}
          </div>
          <div class="history-stats">
            <span><span class="history-stat-value">${parseFloat(s.distance).toFixed(1)}</span>km</span>
            <span><span class="history-stat-value">${MetricsHelper.formatDuration(s.duration)}</span></span>
            <span><span class="history-stat-value">${s.avg_pace || '-'}</span>/km</span>
          </div>
          ${m ? `<div class="history-metrics">
            <span class="history-metric">페이스 ${m.lrs}점 ${lrs.emoji}</span>
            <span class="history-metric">피로도 ${m.fi}점 ${fi.emoji}</span>
          </div>` : ''}
        </div>`;
    });

    container.innerHTML = html;
  },

  async viewSession(sessionId) {
    try {
      const data = await Api.get(`/api/sessions/${sessionId}`);
      App.navigate('analysis', { session: data.session, is_sample: data.session.is_sample });
    } catch (e) {
      showToast(e.message, true);
    }
  }
};

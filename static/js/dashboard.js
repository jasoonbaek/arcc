/* ARCC - Dashboard */

const Dashboard = {
  async load() {
    if (!App.user) return;

    // Set name
    document.getElementById('dashName').textContent = App.user.name || '러너';

    try {
      const data = await Api.get('/api/dashboard');

      // Weekly summary
      document.getElementById('dashRuns').textContent = data.weekly.runs;
      document.getElementById('dashTarget').textContent = data.weekly.target;
      document.getElementById('dashDistance').textContent = data.weekly.distance;
      document.getElementById('dashDuration').textContent = MetricsHelper.formatDuration(data.weekly.duration);
      document.getElementById('dashProgress').style.width = data.weekly.progress + '%';
      document.getElementById('dashProgressText').textContent = data.weekly.progress + '% 달성';

      // Condition
      if (data.metrics) {
        const m = data.metrics;
        const lrs = MetricsHelper.lrsInfo(m.lrs);
        const fi = MetricsHelper.fiInfo(m.fi);
        const ti = MetricsHelper.tiInfo(m.ti);

        document.getElementById('dashCondition').innerHTML = `
          <div class="condition-item">
            <div>
              <div class="condition-label">페이스 안정도: <span class="condition-score">${m.lrs}점</span> ${lrs.emoji}</div>
              <div class="condition-desc">"${lrs.desc}"</div>
            </div>
            <button class="help-btn" onclick="MetricsPopup.showLRS()">?</button>
          </div>
          <div class="condition-item">
            <div>
              <div class="condition-label">피로도: <span class="condition-score">${m.fi}점</span> ${fi.emoji}</div>
              <div class="condition-desc">"${fi.desc}"</div>
            </div>
            <button class="help-btn" onclick="MetricsPopup.showFI()">?</button>
          </div>
          <div class="condition-item">
            <div>
              <div class="condition-label">훈련 강도: <span class="condition-score">${ti.kr}</span></div>
              <div class="condition-desc">"${ti.desc}"</div>
            </div>
            <button class="help-btn" onclick="MetricsPopup.showTI()">?</button>
          </div>`;
        document.getElementById('dashConditionCard').style.display = 'block';
      } else {
        document.getElementById('dashConditionCard').style.display = 'none';
      }

      // AI Recommendation
      if (data.feedback && data.feedback.next_training) {
        const nt = typeof data.feedback.next_training === 'string'
          ? JSON.parse(data.feedback.next_training)
          : data.feedback.next_training;

        document.getElementById('dashRecommend').innerHTML = `
          <div class="recommend-card">
            <div class="recommend-type">\u{1F3C3} ${nt.type || '이지런'}</div>
            <div class="recommend-detail">${nt.duration || ''} | ${nt.pace || ''} | ${nt.zone || ''}</div>
            <div class="recommend-desc">"${nt.description || '꾸준히 달려봐요!'}"</div>
          </div>`;
        document.getElementById('dashRecommendCard').style.display = 'block';
      } else {
        document.getElementById('dashRecommend').innerHTML = `
          <div style="text-align:center;padding:16px;color:var(--muted);font-size:13px;">
            러닝 데이터를 업로드하면 맞춤 추천을 받을 수 있어요!
          </div>`;
        document.getElementById('dashRecommendCard').style.display = 'block';
      }

      // Recent runs
      if (data.recent && data.recent.length > 0) {
        let html = '';
        data.recent.forEach(r => {
          const m = Array.isArray(r.session_metrics) && r.session_metrics[0] ? r.session_metrics[0] : r.session_metrics;
          const ti = m ? MetricsHelper.tiInfo(m.ti) : null;
          html += `
            <div class="recent-run-item" onclick="History.viewSession('${r.id}')">
              <div class="recent-run-date">${MetricsHelper.formatDate(r.run_date)}</div>
              <div class="recent-run-info">${parseFloat(r.distance).toFixed(1)}km ${MetricsHelper.formatDuration(r.duration)}</div>
              ${ti ? `<span class="recent-run-intensity intensity-${m.ti}">${ti.kr}</span>` : ''}
            </div>`;
        });
        document.getElementById('dashRecent').innerHTML = html;
        document.getElementById('dashMoreLink').style.display = 'block';
      }

    } catch (e) {
      console.error('Dashboard load error:', e);
    }
  }
};

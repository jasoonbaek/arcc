/* ARCC - MyPage, Goals, Profile */

const MyPage = {
  load() {
    if (!App.user) return;
    document.getElementById('mypageName').textContent = App.user.name || '-';
    document.getElementById('mypageEmail').textContent = App.user.email || '-';
  },

  showGoals() { App.navigate('goals'); },
  showProfile() { App.navigate('profile'); }
};

const Goals = {
  selectedEvent: 'half',

  resetForm() {
    Goals.selectedEvent = 'half';
    document.getElementById('goalHour').value = '';
    document.getElementById('goalMin').value = '';
    document.getElementById('goalSec').value = '';
    document.getElementById('goalWeekly').value = 3;
    Goals.updateUI();
  },

  async load() {
    // Always reset before populating to avoid stale values from previous user
    Goals.resetForm();
    try {
      const data = await Api.get('/api/goals');
      if (data.goals) {
        Goals.selectedEvent = data.goals.target_event || 'half';
        if (data.goals.target_time) {
          const parts = data.goals.target_time.split(':');
          if (parts.length >= 2) {
            document.getElementById('goalHour').value = parseInt(parts[0]) || '';
            document.getElementById('goalMin').value = parseInt(parts[1]) || '';
            if (parts[2]) document.getElementById('goalSec').value = parseInt(parts[2]) || '';
          }
        }
        document.getElementById('goalWeekly').value = data.goals.weekly_count || 3;
      }
      Goals.updateUI();
    } catch {}
  },

  selectEvent(event) {
    Goals.selectedEvent = event;
    Goals.updateUI();
  },

  updateUI() {
    document.querySelectorAll('.goal-option').forEach(opt => {
      opt.classList.toggle('selected', opt.dataset.event === Goals.selectedEvent);
    });
  },

  async save() {
    const h = document.getElementById('goalHour').value;
    const m = document.getElementById('goalMin').value;
    const s = document.getElementById('goalSec').value;
    let targetTime = null;
    if (h || m || s) {
      targetTime = `${(h||0).toString().padStart(1,'0')}:${(m||0).toString().padStart(2,'0')}:${(s||0).toString().padStart(2,'0')}`;
    }

    try {
      await Api.post('/api/goals', {
        target_event: Goals.selectedEvent,
        target_time: targetTime,
        weekly_count: parseInt(document.getElementById('goalWeekly').value) || 3
      });
      showToast('목표가 저장되었습니다');
      App.navigate('mypage');
    } catch (e) {
      showToast(e.message, true);
    }
  }
};

const Profile = {
  resetForm() {
    ['profileBirthDate','profileHeight','profileWeight','profileRestHR','profileMaxHR','profileInjury'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.value = '';
    });
    // Reset gender radio to "선택 안함"
    document.querySelectorAll('input[name="profileGender"]').forEach(r => {
      r.checked = (r.value === '');
    });
  },

  _getGender() {
    const el = document.querySelector('input[name="profileGender"]:checked');
    return el ? el.value || null : null;
  },

  _setGender(val) {
    document.querySelectorAll('input[name="profileGender"]').forEach(r => {
      r.checked = (r.value === (val || ''));
    });
  },

  async load() {
    // Always reset first — prevents previous user's values from leaking
    Profile.resetForm();
    try {
      const data = await Api.get('/api/profile');
      if (data.profile) {
        const p = data.profile;
        document.getElementById('profileBirthDate').value = (p.birth_date || '').slice(0, 10);
        document.getElementById('profileHeight').value = p.height || '';
        document.getElementById('profileWeight').value = p.weight || '';
        document.getElementById('profileRestHR').value = p.resting_hr || '';
        document.getElementById('profileMaxHR').value = p.max_hr || '';
        document.getElementById('profileInjury').value = p.injury_history || '';
        Profile._setGender(p.gender);
      }
    } catch {}
  },

  async save() {
    try {
      await Api.post('/api/profile', {
        birth_date: document.getElementById('profileBirthDate').value || null,
        gender: Profile._getGender(),
        height: parseFloat(document.getElementById('profileHeight').value) || null,
        weight: parseFloat(document.getElementById('profileWeight').value) || null,
        resting_hr: parseInt(document.getElementById('profileRestHR').value) || null,
        max_hr: parseInt(document.getElementById('profileMaxHR').value) || null,
        injury_history: document.getElementById('profileInjury').value.trim() || null
      });
      showToast('신체 정보가 저장되었습니다');
      App.navigate('mypage');
    } catch (e) {
      showToast(e.message, true);
    }
  }
};

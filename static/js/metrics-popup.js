/* ARCC - Metrics Help Popups (LRS/FI/TI) */

const MetricsPopup = {
  showLRS() {
    Modal.show('\u2753 페이스 안정도란?', `
      <p>러닝 중 페이스가 얼마나 일정했는지 측정하는 지표예요.</p>
      <ul>
        <li><strong>80점 이상:</strong> \u{1F31F} 매우 안정적</li>
        <li><strong>60~79점:</strong> \u{1F60A} 양호</li>
        <li><strong>40~59점:</strong> \u{1F610} 보통</li>
        <li><strong>40점 미만:</strong> \u{1F613} 불안정</li>
      </ul>
      <div class="modal-tip">\u{1F4A1} 페이스가 일정할수록 효율적인 러닝이에요!</div>
    `);
  },

  showFI() {
    Modal.show('\u2753 피로도란?', `
      <p>최근 훈련 대비 현재 피로 누적 상태를 측정하는 지표예요.</p>
      <ul>
        <li><strong>0~30점:</strong> \u{1F4AA} 회복 상태 좋음</li>
        <li><strong>31~50점:</strong> \u{1F60A} 적정</li>
        <li><strong>51~70점:</strong> \u{1F610} 피로 누적</li>
        <li><strong>71점 이상:</strong> \u26A0\uFE0F 과훈련 위험</li>
      </ul>
      <div class="modal-tip">\u{1F4A1} 점수가 낮을수록 좋아요! 높으면 휴식이 필요해요.</div>
    `);
  },

  showTI() {
    Modal.show('\u2753 훈련 강도란?', `
      <p>심박수 기반으로 이번 러닝의 강도를 측정한 지표예요.</p>
      <ul>
        <li><strong>저강도:</strong> 회복 조깅, 가벼운 운동</li>
        <li><strong>중강도:</strong> 일반적인 러닝</li>
        <li><strong>고강도:</strong> 템포런, 인터벌</li>
        <li><strong>최고강도:</strong> 전력 질주, 레이스</li>
      </ul>
      <div class="modal-tip">\u{1F4A1} 목적에 맞는 강도로 훈련하는 게 중요해요!</div>
    `);
  }
};

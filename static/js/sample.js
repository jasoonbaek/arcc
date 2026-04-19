/* ARCC - Sample Data Experience */

const Sample = {
  async runSample() {
    showToast('샘플 분석을 준비하고 있어요...');

    try {
      const result = await Api.post('/api/sample-analysis', {});
      App.navigate('analysis', result);
      showToast('샘플 분석이 완료되었습니다!');
    } catch (e) {
      showToast(e.message || '샘플 분석에 실패했습니다', true);
    }
  }
};

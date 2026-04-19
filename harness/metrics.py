"""하네스 2: 특허 지표 계산 (LRS / FI / TI)"""
import math
from datetime import datetime, timedelta


def get_estimated_max_hr(user_id, supabase, profile):
    """최대심박수 추정 - 3단계 우선순위
    반환: (max_hr: int, source: str)
      1순위: 프로필 직접 입력값
      2순위: 최근 6개월 러닝 기록 max_hr의 최대값 (>=150bpm 일 때만)
      3순위: 공식 계산 (여성 226-age, 남성/미지정 220-age)
    """
    profile = profile or {}

    # 1순위: 직접 입력
    if profile.get('max_hr'):
        return int(profile['max_hr']), '직접 입력'

    # 2순위: 최근 6개월 실측 최대값
    if supabase and user_id:
        try:
            six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
            res = supabase.table('running_sessions').select('max_hr').eq(
                'user_id', user_id
            ).gte('created_at', six_months_ago).execute()
            candidates = [r['max_hr'] for r in (res.data or []) if r.get('max_hr')]
            if candidates:
                observed = max(candidates)
                # 신뢰 하한선: 최소 150bpm (그 미만은 측정 오류 가능)
                if observed >= 150:
                    return int(observed), '러닝 기록 기반 실측'
        except Exception:
            pass

    # 3순위: 공식 계산
    age = int(profile.get('age') or 40)
    gender = profile.get('gender')
    if gender == 'female':
        return 226 - age, '공식 계산 (여성)'
    return 220 - age, '공식 계산 (남성)'


def calculate(validated, profile=None, user_id=None, supabase=None):
    """LRS(페이스 안정도), FI(피로도), TI(훈련 강도) 계산
    profile: {'age','gender','resting_hr','max_hr'} - 개인화
    user_id/supabase: 실측 max_hr 조회용 (선택)
    """
    splits = validated['splits']
    summary = validated['summary']

    # 최대심박수 결정 (3단계 우선순위)
    max_hr_est, max_hr_source = get_estimated_max_hr(user_id, supabase, profile)

    lrs = _calc_lrs(splits)
    fi = _calc_fi(splits, summary)
    ti = _calc_ti(summary, profile, max_hr_est)

    return {
        'lrs': max(0, min(100, lrs)),
        'fi': max(0, min(100, fi)),
        'ti': ti,
        'max_hr_est': max_hr_est,
        'max_hr_source': max_hr_source
    }


def _calc_lrs(splits):
    """LRS (Lap-pace Regularity Score) - 페이스 안정도
    각 구간 페이스의 변동계수(CV)를 기반으로 계산
    CV가 낮을수록 안정적 → 점수 높음
    """
    if len(splits) < 2:
        return 70  # 구간이 부족하면 기본값

    paces = []
    for sp in splits:
        pace_parts = sp['pace'].split(':')
        if len(pace_parts) == 2:
            sec = int(pace_parts[0]) * 60 + int(pace_parts[1])
            if sec > 0:
                paces.append(sec)

    if len(paces) < 2:
        return 70

    mean = sum(paces) / len(paces)
    variance = sum((p - mean) ** 2 for p in paces) / len(paces)
    std_dev = math.sqrt(variance)
    cv = (std_dev / mean) * 100 if mean > 0 else 0

    # CV 0% → 100점, CV 15%+ → 0점
    score = max(0, min(100, round(100 - (cv * 6.67))))
    return score


def _calc_fi(splits, summary):
    """FI (Fatigue Index) - 피로도
    후반부 페이스 하락률 기반
    하락이 클수록 피로도 높음
    """
    if len(splits) < 4:
        return 30  # 기본값

    paces = []
    for sp in splits:
        pace_parts = sp['pace'].split(':')
        if len(pace_parts) == 2:
            sec = int(pace_parts[0]) * 60 + int(pace_parts[1])
            if sec > 0:
                paces.append(sec)

    if len(paces) < 4:
        return 30

    half = len(paces) // 2
    first_half_avg = sum(paces[:half]) / half
    second_half_avg = sum(paces[half:]) / (len(paces) - half)

    # 후반부가 느려진 비율 (양수 = 피로 증가)
    decline_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100

    # HR drift도 고려
    hrs_first = [sp['avg_hr'] for sp in splits[:half] if sp['avg_hr'] > 0]
    hrs_second = [sp['avg_hr'] for sp in splits[half:] if sp['avg_hr'] > 0]

    hr_drift = 0
    if hrs_first and hrs_second:
        hr_drift = (sum(hrs_second) / len(hrs_second)) - (sum(hrs_first) / len(hrs_first))

    # 페이스 하락 + HR 상승 = 높은 피로도
    fi = max(0, min(100, round(decline_pct * 5 + hr_drift * 1.5)))
    return fi


def _calc_ti(summary, profile=None, max_hr_est=None):
    """TI (Training Intensity) - Karvonen HRR 공식 기반
      intensity = (avg_hr - resting_hr) / (max_hr - resting_hr)
    max_hr_est: 외부에서 계산한 최대심박 (없으면 세션 max 또는 190)
    """
    avg_hr = summary['avg_hr']
    session_max = summary.get('max_hr', 0)

    if avg_hr <= 0:
        return 'moderate'

    resting_hr = 60
    if profile and profile.get('resting_hr'):
        resting_hr = profile['resting_hr']

    max_hr = max_hr_est or 190
    max_hr = max(max_hr, session_max)

    # Karvonen HRR 공식
    hrr = max_hr - resting_hr
    if hrr <= 0:
        ratio = avg_hr / max_hr
    else:
        ratio = (avg_hr - resting_hr) / hrr

    if ratio < 0.5:
        return 'low'
    elif ratio < 0.7:
        return 'moderate'
    elif ratio < 0.85:
        return 'high'
    else:
        return 'very_high'

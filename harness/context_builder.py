"""하네스 3: 컨텍스트 주입 (최대 4000 토큰)"""
import json


def build(user_id, validated, calc_metrics, supabase):
    """AI에게 전달할 컨텍스트 문자열 생성"""
    parts = []

    # 1. 현재 러닝 데이터
    summary = validated['summary']
    parts.append(f"""## 현재 러닝 데이터
- 거리: {summary['distance']}km
- 시간: {_sec_to_time(summary['duration_sec'])}
- 평균 페이스: {summary['avg_pace']}/km
- 평균 심박수: {summary['avg_hr']}bpm
- 최고 심박수: {summary['max_hr']}bpm
- 평균 케이던스: {summary['avg_cadence']}spm
- 칼로리: {summary.get('calories', 0)}kcal""")

    # 2. 구간 데이터
    splits_info = []
    for i, sp in enumerate(validated['splits'][:10]):  # Max 10 splits
        splits_info.append(f"  {i+1}km: 페이스 {sp['pace']}, HR {sp['avg_hr']}bpm, 케이던스 {sp['cadence']}spm")
    parts.append("## 구간 데이터\n" + "\n".join(splits_info))

    # 3. 계산된 지표
    ti_kr = {'low': '저강도', 'moderate': '중강도', 'high': '고강도', 'very_high': '최고강도'}.get(calc_metrics['ti'], '중강도')
    parts.append(f"""## 분석 지표
- 페이스 안정도 (LRS): {calc_metrics['lrs']}점/100
- 피로도 (FI): {calc_metrics['fi']}점/100
- 훈련 강도 (TI): {ti_kr}""")

    # 4. 사용자 프로필 — users 테이블에서 조회 (gender/birth_date/height/weight/max_hr/goal)
    u = {}
    try:
        res = supabase.table('users').select(
            'gender, birth_date, height, weight, max_hr, injury_history, '
            'goal, goal_target_time, weekly_runs'
        ).eq('id', user_id).single().execute()
        if res.data:
            u = res.data
    except Exception:
        pass

    # health_records에서 최신 안정시 심박수 조회
    resting = None
    try:
        hr_res = supabase.table('health_records').select(
            'resting_hr, weight, height, measured_at'
        ).eq('user_id', user_id).order('measured_at', desc=True).limit(1).execute()
        if hr_res.data:
            resting = hr_res.data[0].get('resting_hr')
    except Exception:
        pass

    if u:
        profile_info = "## 사용자 정보"
        age = _age_from_birth(u.get('birth_date'))
        if age: profile_info += f"\n- 나이: {age}세"
        gender_kr = {'male': '남성', 'female': '여성'}.get(u.get('gender'))
        if gender_kr: profile_info += f"\n- 성별: {gender_kr}"
        if u.get('height'): profile_info += f"\n- 키: {u['height']}cm"
        if u.get('weight'): profile_info += f"\n- 체중: {u['weight']}kg"
        if resting: profile_info += f"\n- 안정시 심박수: {resting}bpm"

        # 최대심박수: 하네스 2가 계산한 값 + source
        max_hr_user = calc_metrics.get('max_hr_est')
        max_hr_source = calc_metrics.get('max_hr_source', '')
        if max_hr_user:
            profile_info += f"\n- 최대 심박수: {max_hr_user}bpm ({max_hr_source})"

        if u.get('injury_history'):
            profile_info += f"\n- 부상 이력: {u['injury_history']}"

        # HRR 기반 개인화 지표 (Karvonen)
        avg_hr_run = summary.get('avg_hr', 0)
        if max_hr_user and resting and avg_hr_run > 0:
            hrr = max_hr_user - resting
            if hrr > 0:
                intensity = round((avg_hr_run - resting) / hrr * 100)
                profile_info += (f"\n- 개인 HRR 기반 강도: {intensity}% "
                                 f"(최대심박 {max_hr_user}bpm, 안정시 {resting}bpm 기준)")
        parts.append(profile_info)

    # 5. 목표 — users 테이블에 통합됨
    if u.get('goal') or u.get('weekly_runs'):
        event_kr = {'10K': '10K', 'half': '하프마라톤', 'full': '풀마라톤'}.get(u.get('goal'), u.get('goal') or '')
        goals_info = "## 목표"
        if event_kr: goals_info += f"\n- 종목: {event_kr}"
        if u.get('goal_target_time'): goals_info += f"\n- 목표 기록: {u['goal_target_time']}"
        if u.get('weekly_runs'): goals_info += f"\n- 주간 훈련 횟수: {u['weekly_runs']}회"
        parts.append(goals_info)

    # 6. 최근 30일 러닝 기록 + LRS/FI/TI 추이
    try:
        from datetime import datetime, timedelta
        thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        recent = supabase.table('running_sessions').select(
            'id, run_date, distance, avg_pace, avg_hr, session_metrics(lrs, fi, ti)'
        ).eq('user_id', user_id).gte('run_date', thirty_days_ago).eq(
            'is_sample', False
        ).order('run_date', desc=True).limit(10).execute()

        if recent.data:
            recent_info = "## 최근 30일 러닝 기록 (지표 추이 포함)"
            for r in recent.data:
                m = r.get('session_metrics')
                m = m[0] if isinstance(m, list) and m else m
                metrics_str = ''
                if m:
                    ti_kr2 = {'low': '저강도', 'moderate': '중강도', 'high': '고강도', 'very_high': '최고강도'}.get(m.get('ti'), '-')
                    metrics_str = f", LRS {m.get('lrs','-')}, FI {m.get('fi','-')}, TI {ti_kr2}"
                recent_info += f"\n- {r['run_date']}: {r['distance']}km, {r['avg_pace']}/km, HR {r['avg_hr']}bpm{metrics_str}"
            parts.append(recent_info)
    except Exception:
        pass

    context = "\n\n".join(parts)

    # Truncate if too long (rough token estimate: 1 char ≈ 0.5 token for Korean)
    max_chars = 8000  # ~4000 tokens
    if len(context) > max_chars:
        context = context[:max_chars] + "\n\n(컨텍스트가 잘렸습니다)"

    return context


def _age_from_birth(birth_date):
    """birth_date(문자열 또는 date) → 만 나이"""
    if not birth_date:
        return None
    try:
        from datetime import date, datetime
        if isinstance(birth_date, str):
            # 'YYYY-MM-DD' 형식만 지원
            bd = datetime.strptime(birth_date[:10], '%Y-%m-%d').date()
        else:
            bd = birth_date
        today = date.today()
        return today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
    except Exception:
        return None


def _sec_to_time(sec):
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"

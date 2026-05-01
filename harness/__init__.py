"""ARCC Harness Engineering - 6-stage AI coaching pipeline"""
import json
import time
import traceback

from . import csv_validator, input_validator, metrics, context_builder, safety_filter, quality_checker, logger


def run_pipeline(csv_text, user_id, supabase, filename=None):
    """CSV 텍스트 → 6단계 하네스 → AI 코칭 결과 반환"""
    start_time = time.time()
    log_entry = {
        'user_id': user_id,
        'harness0_passed': False,
        'harness1_passed': False,
        'harness4_passed': False,
        'harness5_passed': False,
        'retry_count': 0,
        'is_sample': False
    }

    try:
        # Harness 0: CSV parsing validation
        parsed = csv_validator.validate(csv_text)
        log_entry['harness0_passed'] = True

        # Harness 1: Input range validation
        validated = input_validator.validate(parsed, filename=filename)
        log_entry['harness1_passed'] = True

        # Harness 2: Calculate metrics (LRS/FI/TI) — profile-personalized
        user_profile = _fetch_profile(user_id, supabase)
        calculated_metrics = metrics.calculate(
            validated, profile=user_profile, user_id=user_id, supabase=supabase
        )
        print(f'[HARNESS2] max_hr={calculated_metrics["max_hr_est"]}bpm ({calculated_metrics["max_hr_source"]})')

        # Save session to DB
        session_data = _save_session(user_id, validated, calculated_metrics, supabase)
        session_id = session_data['id']
        log_entry['session_id'] = session_id

        # Harness 3: Build context
        context = context_builder.build(user_id, validated, calculated_metrics, supabase)

        # Debug: log context (first 500 chars) + verify profile inclusion
        print(f'[HARNESS3] user_id={user_id} context_len={len(context)} has_profile={"## 사용자 정보" in context}')
        print(f'[HARNESS3] context preview:\n{context[:500]}\n...')
        log_entry['context_full'] = context  # 전체 프롬프트 아카이빙 (하네스 6에서 저장)

        # Call Claude AI
        ai_result = None
        for attempt in range(3):
            try:
                ai_result = _call_claude(context)
                log_entry['retry_count'] = attempt

                # Harness 4: Safety filter
                safe_result = safety_filter.check(ai_result)
                log_entry['harness4_passed'] = True

                # Harness 5: Quality check
                quality = quality_checker.check(safe_result)
                log_entry['harness5_passed'] = True
                log_entry['quality_score'] = quality['score']

                # Save AI feedback
                _save_feedback(session_id, user_id, safe_result, supabase)
                break
            except quality_checker.QualityError:
                log_entry['retry_count'] = attempt + 1
                if attempt == 2:
                    # Use fallback response
                    safe_result = _get_fallback_response(calculated_metrics)
                    _save_feedback(session_id, user_id, safe_result, supabase)
            except safety_filter.SafetyError:
                safe_result = _get_fallback_response(calculated_metrics)
                log_entry['harness4_passed'] = False
                _save_feedback(session_id, user_id, safe_result, supabase)
                break

        # Calculate timing
        duration = int((time.time() - start_time) * 1000)
        log_entry['api_duration_ms'] = duration

        # Harness 6: Log
        logger.log(log_entry, supabase)

        # Return full session data
        result = supabase.table('running_sessions').select(
            '*, session_metrics(*), ai_feedbacks(*), splits(*)'
        ).eq('id', session_id).execute()

        return {'session': result.data[0], 'is_sample': False}

    except csv_validator.CSVError as e:
        logger.log(log_entry, supabase)
        raise Exception(f'CSV 파일 오류: {e}')
    except input_validator.ValidationError as e:
        log_entry['harness0_passed'] = True
        logger.log(log_entry, supabase)
        raise Exception(f'데이터 검증 오류: {e}')
    except Exception as e:
        logger.log(log_entry, supabase)
        raise


def _fetch_profile(user_id, supabase):
    """사용자 프로필 조회 → metrics.calculate()가 기대하는 평탄한 dict 반환.
    users 테이블(기본 속성) + health_records 최신 측정값(resting_hr)을 결합.
    반환 키: age, gender, height, weight, resting_hr, max_hr, injury_history
    """
    profile = {}
    try:
        res = supabase.table('users').select(
            'gender, birth_date, height, weight, max_hr, injury_history'
        ).eq('id', user_id).single().execute()
        if res.data:
            u = res.data
            profile['gender'] = u.get('gender')
            profile['height'] = u.get('height')
            profile['weight'] = u.get('weight')
            profile['max_hr'] = u.get('max_hr')
            profile['injury_history'] = u.get('injury_history')
            # birth_date → 나이 계산
            from . import context_builder
            age = context_builder._age_from_birth(u.get('birth_date'))
            if age:
                profile['age'] = age
    except Exception as e:
        print(f'[HARNESS] users fetch failed: {e}')

    # health_records 최신 안정시 심박수
    try:
        hr_res = supabase.table('health_records').select(
            'resting_hr, measured_at'
        ).eq('user_id', user_id).order('measured_at', desc=True).limit(1).execute()
        if hr_res.data and hr_res.data[0].get('resting_hr'):
            profile['resting_hr'] = hr_res.data[0]['resting_hr']
    except Exception as e:
        print(f'[HARNESS] health_records fetch failed: {e}')

    return profile or None


def _save_session(user_id, validated, calc_metrics, supabase):
    """Phase 3-7 B-3: PostgreSQL RPC 단일 호출로 트랜잭션 묶음 저장.

    insert_session_bundle() PL/pgSQL 함수가
    running_sessions + splits + session_metrics 3-INSERT를
    단일 트랜잭션으로 처리 → 부분 실패 시 자동 ROLLBACK (원자성 보장).
    """
    summary = validated['summary']

    res = supabase.rpc('insert_session_bundle', {
        'p_user_id': user_id,
        'p_session': {
            'run_date': validated.get('date') or time.strftime('%Y-%m-%d'),
            'distance': summary['distance'],
            'duration': summary['duration_sec'],   # dict 키 'duration_sec' → DB 컬럼 'duration'
            'calories': summary.get('calories', 0),
            'avg_pace': summary['avg_pace'],
            'avg_hr': summary['avg_hr'],
            'max_hr': summary['max_hr'],
            'avg_cadence': summary['avg_cadence'],
            'avg_stride': summary.get('avg_stride', 0),
            'is_sample': False,
        },
        'p_splits': [
            {
                'split_number': i + 1,
                'distance': sp['distance'],
                'time': sp['time'],
                'pace': sp['pace'],
                'avg_hr': sp['avg_hr'],
                'max_hr': sp['max_hr'],
                'cadence': sp['cadence'],
                'stride': sp.get('stride', 0),
            }
            for i, sp in enumerate(validated['splits'])
        ],
        'p_metrics': {
            'lrs': calc_metrics['lrs'],
            'fi': calc_metrics['fi'],
            'ti': calc_metrics['ti'],
        }
    }).execute()

    # RPC 응답에서 UUID 추출 (SDK 버전에 따라 dict/list/scalar 가능)
    session_id = res.data
    if isinstance(session_id, list):
        session_id = session_id[0] if session_id else None
    if isinstance(session_id, dict):
        session_id = session_id.get('insert_session_bundle')

    print(f'[B-3 RPC] insert_session_bundle → session_id={session_id}')
    return {'id': session_id}


def _call_claude(context):
    """Claude API 호출"""
    import anthropic
    import config

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    system_prompt = """당신은 ARCC(AI Running Coaching by Claude)의 AI 러닝 코치입니다.
COROS 워치 데이터를 기반으로 한국어로 러닝 코칭을 제공합니다.

반드시 아래 JSON 형식으로 응답하세요:
{
  "summary": "한줄 요약 (50자 이내)",
  "analysis": "상세 분석 (200자 이내)",
  "strengths": ["잘한 점 1", "잘한 점 2"],
  "improvements": ["개선점 1", "개선점 2"],
  "next_training": {
    "type": "훈련 유형",
    "duration": "시간",
    "pace": "추천 페이스",
    "zone": "심박 존",
    "description": "상세 설명"
  }
}

주의사항:
- 의료 진단이나 처방을 하지 마세요
- "병원에 가세요", "약을 드세요" 같은 의료 조언 금지
- 한국어로만 응답하세요
- 격려하는 톤으로 작성하세요
- 구체적이고 실행 가능한 조언을 하세요

**개인화 필수**: 컨텍스트에 '## 사용자 정보'가 있으면 나이/체중/안정시 심박수를
반드시 분석에 반영하세요. 예) 50대와 30대의 회복 속도가 다르고, 안정시 심박수
60 vs 50의 훈련 강도 해석이 다릅니다. 같은 러닝 데이터라도 개인 특성에 따라
피드백이 달라야 합니다."""

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": context}]
    )

    response_text = message.content[0].text

    # Extract JSON from response
    try:
        # Try parsing directly
        return json.loads(response_text)
    except json.JSONDecodeError:
        # Try extracting JSON from markdown code block
        import re
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(1))
        raise quality_checker.QualityError('AI 응답에서 JSON을 추출할 수 없습니다')


def _save_feedback(session_id, user_id, result, supabase):
    """AI 피드백 저장 (user_id NOT NULL 제약 + RLS 정책 충족)"""
    supabase.table('ai_feedbacks').upsert({
        'user_id': user_id,
        'session_id': session_id,
        'summary': result.get('summary', ''),
        'strengths': json.dumps(result.get('strengths', []), ensure_ascii=False),
        'improvements': json.dumps(result.get('improvements', []), ensure_ascii=False),
        'next_training': json.dumps(result.get('next_training', {}), ensure_ascii=False),
        'full_response': json.dumps(result, ensure_ascii=False)
    }).execute()


def _get_fallback_response(calc_metrics):
    """안전 기본 응답"""
    lrs = calc_metrics['lrs']
    fi = calc_metrics['fi']
    ti = calc_metrics['ti']

    ti_kr = {'low': '저강도', 'moderate': '중강도', 'high': '고강도', 'very_high': '최고강도'}.get(ti, '중강도')

    return {
        'summary': f'{ti_kr} 러닝을 완료했어요! 꾸준한 훈련이 중요합니다.',
        'analysis': f'페이스 안정도 {lrs}점, 피로도 {fi}점으로 측정되었습니다.',
        'strengths': ['꾸준히 훈련하고 있어요', '완주를 해냈어요'],
        'improvements': ['페이스 안정성을 높여보세요', '충분한 휴식을 취하세요'],
        'next_training': {
            'type': '이지런',
            'duration': '30분',
            'pace': '편한 페이스',
            'zone': 'Zone 2',
            'description': '가볍게 달리며 몸을 회복시켜요'
        }
    }

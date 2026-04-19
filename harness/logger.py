"""하네스 6: AI 코칭 로깅"""


def log(entry, supabase):
    """AI 코칭 호출 로그 저장"""
    try:
        log_data = {
            'user_id': entry.get('user_id'),
            'session_id': entry.get('session_id'),
            'api_duration_ms': entry.get('api_duration_ms', 0),
            'input_tokens': entry.get('input_tokens', 0),
            'output_tokens': entry.get('output_tokens', 0),
            'harness0_passed': entry.get('harness0_passed', False),
            'harness1_passed': entry.get('harness1_passed', False),
            'harness4_passed': entry.get('harness4_passed', False),
            'harness5_passed': entry.get('harness5_passed', False),
            'retry_count': entry.get('retry_count', 0),
            'quality_score': entry.get('quality_score'),
            'is_sample': entry.get('is_sample', False),
            'context_full': entry.get('context_full'),  # 하네스 3 전문 아카이빙
        }
        supabase.table('ai_coaching_logs').insert(log_data).execute()
    except Exception:
        pass  # Logging should never break the main flow

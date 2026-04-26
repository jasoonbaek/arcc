"""DB 어댑터 팩토리.

USE_SUPABASE 플래그에 따라 SupabaseAdapter 또는 MockAdapter 반환.
두 어댑터 모두 Supabase Python SDK와 동일한 체인 API를 노출하므로
호출 측 코드는 모드를 알 필요가 없음.

사용:
    from db import get_db
    db = get_db()
    res = db.table('users').select('*').eq('id', uid).execute()
    db.auth.sign_up({'email': e, 'password': p})
"""
import config

_instance = None


def get_db():
    """프로세스 전역 싱글턴 어댑터 반환."""
    global _instance
    if _instance is not None:
        return _instance

    # 안전 모드: 강제로 MOCK 폴백 (USE_SUPABASE보다 우선)
    if config.ROLLBACK_TO_MOCK:
        from .mock_adapter import MockAdapter
        _instance = MockAdapter()
        print('[DB] Mode: MOCK (FORCED by ROLLBACK_TO_MOCK)')
        return _instance

    if config.USE_SUPABASE:
        from .supabase_adapter import SupabaseAdapter
        _instance = SupabaseAdapter(config.SUPABASE_URL, config.SUPABASE_KEY)
        print(f'[DB] Mode: SUPABASE ({config.SUPABASE_URL})')
    else:
        from .mock_adapter import MockAdapter
        _instance = MockAdapter()
        print('[DB] Mode: MOCK (in-memory)')

    return _instance


def reset_for_testing():
    """테스트용: 싱글턴 초기화."""
    global _instance
    _instance = None

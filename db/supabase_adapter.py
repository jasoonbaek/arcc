"""실제 Supabase 어댑터 — supabase-py 클라이언트를 그대로 위임.

supabase-py의 체인 API가 이미 우리의 표준이므로 이 래퍼는 극히 얇다.
복잡한 기능이 필요해지면 여기에서만 확장하면 된다.
"""
from supabase import create_client, Client


class SupabaseAdapter:
    def __init__(self, url: str, key: str, _existing_client: Client = None):
        self._url = url
        self._key = key
        # 내부 호출용: 이미 만들어진 client를 받으면 재사용 (with_auth 용)
        self._client: Client = _existing_client or create_client(url, key)

    def table(self, name: str):
        """체인 쿼리 빌더 반환 — supabase-py가 제공하는 PostgrestQueryBuilder."""
        return self._client.table(name)

    @property
    def auth(self):
        """Supabase Auth 네임스페이스 — sign_up / sign_in_with_password / sign_out 등."""
        return self._client.auth

    @property
    def raw(self):
        """고급 기능이 필요할 때를 위한 탈출구(escape hatch)."""
        return self._client

    def with_auth(self, access_token: str):
        """현재 요청의 access_token을 PostgREST에 주입한 새 어댑터 인스턴스 반환.

        ⚠️ 동시성 안전성: 매 요청마다 새 client 인스턴스를 만들기 때문에
        Werkzeug 멀티스레드 환경에서도 race condition 없음.
        (글로벌 client에 .postgrest.auth(token)을 박으면 다른 요청과 섞일 위험)

        한 요청 안에서 여러 번 호출되어도 같은 토큰이면 같은 효과 — 캐시 안 함.
        """
        if not access_token:
            return self
        new_client = create_client(self._url, self._key)
        new_client.postgrest.auth(access_token)
        return SupabaseAdapter(self._url, self._key, _existing_client=new_client)

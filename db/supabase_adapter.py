"""실제 Supabase 어댑터 — supabase-py 클라이언트를 그대로 위임.

supabase-py의 체인 API가 이미 우리의 표준이므로 이 래퍼는 극히 얇다.
복잡한 기능이 필요해지면 여기에서만 확장하면 된다.
"""
from supabase import create_client, Client


class SupabaseAdapter:
    def __init__(self, url: str, key: str):
        self._client: Client = create_client(url, key)

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

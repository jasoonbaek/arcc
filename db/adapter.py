"""DB 어댑터 공통 타입 — 두 어댑터가 동일한 shape을 반환하도록."""


class Result:
    """Supabase의 APIResponse와 호환되는 최소 shape."""
    def __init__(self, data=None, count=None):
        self.data = data
        self.count = count

    def __repr__(self):
        n = len(self.data) if isinstance(self.data, list) else ('dict' if self.data else 'None')
        return f'<Result data={n} count={self.count}>'

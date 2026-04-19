"""MOCK 어댑터 — supabase-py 체인 API를 인메모리 dict 위에 흉내낸다.

목적:
    USE_SUPABASE=False 상태에서도 엔드포인트 코드가 실 모드와 동일하게 동작하도록.

지원 체인:
    .select(cols) .eq(k,v) .gte(k,v) .lte(k,v) .order(k,desc=) .limit(n) .single()
    .insert(dict|list) .update(dict) .delete() .upsert(dict, on_conflict=)
    → .execute() → Result(data, count)

Auth:
    auth.sign_up({'email','password'}) / auth.sign_in_with_password({...}) / auth.sign_out()
    반환 shape은 Supabase Auth와 동일하게 {'user': {...}, 'session': {...}}
"""
import hashlib
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from .adapter import Result


# ============================================================
# 내부 스토어
# ============================================================
class _Store:
    """테이블별 row list + PK 자동증분."""
    def __init__(self):
        self.tables: Dict[str, List[Dict[str, Any]]] = {}
        self._seq: Dict[str, int] = {}

    def rows(self, table: str) -> List[Dict[str, Any]]:
        return self.tables.setdefault(table, [])

    def next_id(self, table: str) -> int:
        self._seq[table] = self._seq.get(table, 0) + 1
        return self._seq[table]


# ============================================================
# Query Builder
# ============================================================
class _Query:
    def __init__(self, store: _Store, table: str):
        self._store = store
        self._table = table
        self._filters: List[tuple] = []   # (op, key, value)
        self._order: Optional[tuple] = None  # (key, desc)
        self._limit: Optional[int] = None
        self._single = False
        # mutation state
        self._op = 'select'   # 'select' | 'insert' | 'update' | 'delete' | 'upsert'
        self._payload: Any = None
        self._on_conflict: Optional[str] = None

    # ---- select/filter chain ----
    def select(self, *columns, count=None):
        self._op = 'select'
        return self

    def eq(self, key, value):
        self._filters.append(('eq', key, value)); return self

    def neq(self, key, value):
        self._filters.append(('neq', key, value)); return self

    def gte(self, key, value):
        self._filters.append(('gte', key, value)); return self

    def lte(self, key, value):
        self._filters.append(('lte', key, value)); return self

    def gt(self, key, value):
        self._filters.append(('gt', key, value)); return self

    def lt(self, key, value):
        self._filters.append(('lt', key, value)); return self

    def order(self, key, desc=False):
        self._order = (key, desc); return self

    def limit(self, n):
        self._limit = n; return self

    def single(self):
        self._single = True; return self

    # ---- mutations ----
    def insert(self, payload):
        self._op = 'insert'
        self._payload = payload if isinstance(payload, list) else [payload]
        return self

    def update(self, payload: dict):
        self._op = 'update'
        self._payload = payload
        return self

    def delete(self):
        self._op = 'delete'
        return self

    def upsert(self, payload, on_conflict: Optional[str] = None):
        self._op = 'upsert'
        self._payload = payload if isinstance(payload, list) else [payload]
        self._on_conflict = on_conflict
        return self

    # ---- terminal ----
    def execute(self) -> Result:
        if self._op == 'select':
            return self._do_select()
        if self._op == 'insert':
            return self._do_insert()
        if self._op == 'update':
            return self._do_update()
        if self._op == 'delete':
            return self._do_delete()
        if self._op == 'upsert':
            return self._do_upsert()
        raise RuntimeError(f'Unknown op: {self._op}')

    # ---- impl ----
    def _matches(self, row: dict) -> bool:
        for op, k, v in self._filters:
            rv = row.get(k)
            if op == 'eq' and rv != v: return False
            if op == 'neq' and rv == v: return False
            if op == 'gte' and (rv is None or rv < v): return False
            if op == 'lte' and (rv is None or rv > v): return False
            if op == 'gt'  and (rv is None or rv <= v): return False
            if op == 'lt'  and (rv is None or rv >= v): return False
        return True

    def _do_select(self) -> Result:
        rows = [r for r in self._store.rows(self._table) if self._matches(r)]
        if self._order:
            k, desc = self._order
            rows = sorted(rows, key=lambda r: (r.get(k) is None, r.get(k)), reverse=desc)
        if self._limit:
            rows = rows[:self._limit]
        if self._single:
            return Result(data=(rows[0] if rows else None))
        return Result(data=rows, count=len(rows))

    def _do_insert(self) -> Result:
        inserted = []
        now = datetime.now().isoformat()
        for row in self._payload:
            new_row = dict(row)
            # 기본 필드 자동 주입
            if 'id' not in new_row:
                new_row['id'] = self._store.next_id(self._table)
            if 'created_at' not in new_row:
                new_row['created_at'] = now
            self._store.rows(self._table).append(new_row)
            inserted.append(new_row)
        return Result(data=inserted, count=len(inserted))

    def _do_update(self) -> Result:
        updated = []
        for row in self._store.rows(self._table):
            if self._matches(row):
                row.update(self._payload)
                updated.append(row)
        return Result(data=updated, count=len(updated))

    def _do_delete(self) -> Result:
        rows = self._store.rows(self._table)
        keep = [r for r in rows if not self._matches(r)]
        removed = [r for r in rows if self._matches(r)]
        self._store.tables[self._table] = keep
        return Result(data=removed, count=len(removed))

    def _do_upsert(self) -> Result:
        """on_conflict 키로 기존 row 찾아 update, 없으면 insert."""
        conflict_key = self._on_conflict or 'id'
        rows = self._store.rows(self._table)
        result = []
        for payload in self._payload:
            existing = next(
                (r for r in rows if r.get(conflict_key) == payload.get(conflict_key)),
                None
            )
            if existing:
                existing.update(payload)
                result.append(existing)
            else:
                new_row = dict(payload)
                if 'id' not in new_row:
                    new_row['id'] = self._store.next_id(self._table)
                if 'created_at' not in new_row:
                    new_row['created_at'] = datetime.now().isoformat()
                rows.append(new_row)
                result.append(new_row)
        return Result(data=result, count=len(result))


# ============================================================
# Auth (Supabase Auth 인터페이스 흉내)
# ============================================================
class _User:
    """Supabase gotrue.User 흉내 — 속성 접근 + dict 변환 둘 다 지원."""
    def __init__(self, data: dict):
        self.__dict__.update(data)
        self._data = data
    def dict(self):
        return dict(self._data)
    def model_dump(self):
        return dict(self._data)


class _AuthResponse:
    def __init__(self, user, session=None):
        self.user = user
        self.session = session


class _MockAuth:
    def __init__(self, store: _Store):
        self._store = store
        self._current_user: Optional[dict] = None

    @staticmethod
    def _hash(pw: str) -> str:
        return hashlib.sha256(pw.encode()).hexdigest()

    def sign_up(self, credentials: dict):
        email = credentials.get('email', '').strip()
        password = credentials.get('password', '')
        if not email or not password:
            raise ValueError('email/password required')
        users = self._store.rows('_auth_users')
        if any(u['email'] == email for u in users):
            raise ValueError(f'User already registered: {email}')
        user = {
            'id': str(uuid.uuid4()),
            'email': email,
            'password_hash': self._hash(password),
            'created_at': datetime.now().isoformat(),
        }
        users.append(user)
        self._current_user = user
        return _AuthResponse(user=_User(user), session={'access_token': f'mock-{user["id"]}'})

    def sign_in_with_password(self, credentials: dict):
        email = credentials.get('email', '').strip()
        password = credentials.get('password', '')
        pw_hash = self._hash(password)
        users = self._store.rows('_auth_users')
        user = next((u for u in users if u['email'] == email and u['password_hash'] == pw_hash), None)
        if not user:
            raise ValueError('Invalid login credentials')
        self._current_user = user
        return _AuthResponse(user=_User(user), session={'access_token': f'mock-{user["id"]}'})

    def sign_out(self):
        self._current_user = None
        return None

    def get_user(self):
        if not self._current_user:
            return None
        return _AuthResponse(user=_User(self._current_user))


# ============================================================
# MockAdapter (공개 API)
# ============================================================
class MockAdapter:
    def __init__(self):
        self._store = _Store()
        self._auth = _MockAuth(self._store)

    def table(self, name: str) -> _Query:
        return _Query(self._store, name)

    @property
    def auth(self) -> _MockAuth:
        return self._auth

    # 디버깅/검사용
    def _dump(self) -> dict:
        return {t: list(rows) for t, rows in self._store.tables.items()}

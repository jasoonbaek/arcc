"""ARCC - AI Running Coaching by Claude (Phase 2)
Mock mode: DB/API 없이 인메모리 더미 데이터로 UI 확인
"""
import os
import json
import hashlib
import time
import copy
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, render_template, request, jsonify, session

import config
from db import get_db

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# DB 어댑터 초기화 (USE_SUPABASE에 따라 Supabase 또는 MOCK 어댑터 선택)
db = get_db()

# ============================================================
# MOCK DATA STORE (in-memory)
# ============================================================
MOCK = {
    'users': {
        1: {'id': 1, 'email': 'runner@coros.com', 'name': '김코로스', 'password_hash': hashlib.sha256(b'123456').hexdigest()},
    },
    'next_user_id': 2,
    'disclaimers': {1: True},
    'goals': {
        1: {'user_id': 1, 'purpose': 'record', 'target_event': 'half', 'target_time': '1:50:00', 'weekly_count': 4}
    },
    # profiles: production users + health_records 를 평탄하게 흉내낸 mock
    'profiles': {
        1: {
            'user_id': 1,
            'birth_date': '1990-05-15',  # age auto-calculated
            'gender': 'male',
            'height': 175.0, 'weight': 72.0,
            'resting_hr': 58,   # 실제로는 health_records 최신값에서 옴
            'max_hr': 188,
            'injury_history': None
        }
    },
}


# ============================================================
# HELPERS
# ============================================================

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return jsonify({'error': '로그인이 필요합니다'}), 401
        return f(*args, **kwargs)
    return decorated


def _authed_db():
    """현재 요청의 access_token을 주입한 DB 어댑터 반환.

    Phase 3-2 핵심: RLS 정책 (auth.uid() = id) 통과를 위해
    매 요청마다 사용자의 JWT를 PostgREST에 전달해야 함.
    토큰이 없으면 anon 그대로 — RLS가 차단할 것.
    """
    token = session.get('access_token')
    return db.with_auth(token) if token else db


def _hms_to_seconds(s):
    """'HH:MM:SS' 또는 'MM:SS' → 정수 초. None/빈값/잘못된 형식은 None."""
    if not s:
        return None
    try:
        parts = [int(p) for p in str(s).split(':')]
    except (ValueError, TypeError):
        return None
    if len(parts) == 3:
        h, m, sec = parts
    elif len(parts) == 2:
        h, m, sec = 0, parts[0], parts[1]
    else:
        return None
    return h * 3600 + m * 60 + sec


def _seconds_to_hms(n):
    """정수 초 → 'H:MM:SS'. None은 None."""
    if n is None:
        return None
    try:
        n = int(n)
    except (ValueError, TypeError):
        return None
    h, rem = divmod(n, 3600)
    m, s = divmod(rem, 60)
    return f'{h}:{m:02d}:{s:02d}'


# ============================================================
# ROUTES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html')


# ---------- Supabase 연결 테스트 (Phase 2 임시, Phase 3에서 삭제) ----------

@app.route('/api/supabase-test')
def supabase_test():
    """현재 DB 모드 + 실제 Supabase 연결 가능 여부 진단."""
    if not config.USE_SUPABASE:
        return jsonify({'mode': 'MOCK', 'supabase': False})
    try:
        from supabase import create_client
        client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
        result = client.table('users').select('id, email').limit(3).execute()
        return jsonify({
            'mode': 'SUPABASE',
            'supabase': True,
            'connection': 'OK',
            'users_count': len(result.data),
            'sample_emails': [u.get('email', 'no-email') for u in result.data],
        })
    except Exception as e:
        return jsonify({
            'mode': 'SUPABASE',
            'supabase': True,
            'connection': 'FAIL',
            'error': str(e),
            'error_type': type(e).__name__,
        }), 500


@app.route('/api/auth-test')
@login_required
def auth_test():
    """Phase 3-2 진단: access_token이 PostgREST에 주입되어 RLS 통과하는지 검증.

    로그인 상태에서 호출 → 본인 row 조회 → 1건 나와야 정상.
    Phase 3-7에서 제거 예정.
    """
    uid = session['user_id']
    has_token = bool(session.get('access_token'))

    # (1) anon으로 조회 — RLS가 차단해서 0건 또는 None 나와야 정상
    try:
        anon_res = db.table('users').select('id, email').eq('id', uid).execute()
        anon_count = len(anon_res.data) if anon_res.data else 0
    except Exception as e:
        anon_count = f'ERR: {type(e).__name__}'

    # (2) authed로 조회 — 본인 row 1건 나와야 정상
    try:
        authed = _authed_db()
        authed_res = authed.table('users').select('id, email, name').eq('id', uid).single().execute()
        authed_data = authed_res.data
    except Exception as e:
        authed_data = f'ERR: {type(e).__name__}: {str(e)[:200]}'

    return jsonify({
        'session_user_id': uid,
        'has_access_token': has_token,
        'anon_select_count': anon_count,  # 기대: 0 (RLS 차단)
        'authed_select': authed_data,     # 기대: {id, email, name}
        'verdict': 'OK' if isinstance(authed_data, dict) and authed_data.get('id') == uid else 'FAIL',
    })


# ---------- Auth ----------

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    """Phase 3-1: Supabase Auth 기반 가입.
    - db.auth.sign_up() → auth.users 생성 → 트리거가 public.users 자동 동기화
    - 비번은 Supabase가 bcrypt로 처리 (SHA256 폐기)
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()

    if not email or not password or not name:
        return jsonify({'error': '모든 필드를 입력해주세요'}), 400
    if len(password) < 6:
        return jsonify({'error': '비밀번호는 6자 이상이어야 합니다'}), 400

    try:
        resp = db.auth.sign_up({
            'email': email,
            'password': password,
            'options': {'data': {'name': name}},
        })
    except Exception as e:
        msg = str(e)
        print(f'[AUTH/SIGNUP] error: {type(e).__name__}: {msg}')
        if 'already' in msg.lower() or 'registered' in msg.lower():
            return jsonify({'error': '이미 가입된 이메일입니다'}), 400
        return jsonify({'error': f'가입 실패: {msg}'}), 400

    if not resp.user:
        return jsonify({'error': '가입 실패: 사용자 정보가 반환되지 않았습니다'}), 500

    uid = resp.user.id  # UUID 문자열
    access_token = resp.session.access_token if resp.session else None

    session['user_id'] = uid
    session['user_name'] = name
    session['user_email'] = email
    if access_token:
        session['access_token'] = access_token

    print(f'[AUTH/SIGNUP] uid={uid} email={email} session_token={"yes" if access_token else "no(email_confirm_required?)"}')
    return jsonify({'user': {'id': uid, 'name': name, 'email': email}})


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Phase 3-1: Supabase Auth 기반 로그인.
    - db.auth.sign_in_with_password() → access_token 발급
    - has_disclaimer/has_goals는 Phase 3-2 전까지 MOCK 그대로 (전환 예정)
    """
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({'error': '이메일과 비밀번호를 입력해주세요'}), 400

    try:
        resp = db.auth.sign_in_with_password({'email': email, 'password': password})
    except Exception as e:
        print(f'[AUTH/LOGIN] failed for {email}: {type(e).__name__}: {e}')
        return jsonify({'error': '이메일 또는 비밀번호가 올바르지 않습니다'}), 401

    if not resp.user or not resp.session:
        return jsonify({'error': '이메일 또는 비밀번호가 올바르지 않습니다'}), 401

    uid = resp.user.id  # UUID
    # 이름은 raw_user_meta_data에 저장됨 (Supabase Auth 표준)
    meta = getattr(resp.user, 'user_metadata', None) or {}
    name = meta.get('name') or email.split('@')[0]

    session['user_id'] = uid
    session['user_name'] = name
    session['user_email'] = email
    session['access_token'] = resp.session.access_token

    print(f'[AUTH/LOGIN] uid={uid} email={email}')

    # Phase 3-2: has_disclaimer/has_goals 를 실 DB(users 테이블)에서 판정
    has_disclaimer = False
    has_goals = False
    try:
        u_res = db.with_auth(resp.session.access_token).table('users').select(
            'disclaimer_agreed_at, goal'
        ).eq('id', uid).single().execute()
        if u_res.data:
            has_disclaimer = bool(u_res.data.get('disclaimer_agreed_at'))
            has_goals = bool(u_res.data.get('goal'))
    except Exception as e:
        print(f'[AUTH/LOGIN] onboarding flags fetch warning: {type(e).__name__}: {e}')

    return jsonify({
        'user': {'id': uid, 'name': name, 'email': email},
        'has_disclaimer': has_disclaimer,
        'has_goals': has_goals,
    })


@app.route('/api/auth/logout', methods=['POST'])
def logout():
    """Phase 3-1: Supabase Auth 토큰 무효화 + Flask 세션 비움."""
    try:
        db.auth.sign_out()
    except Exception as e:
        # Supabase 측 토큰 만료/네트워크 실패해도 로컬 세션은 반드시 비워야 함
        print(f'[AUTH/LOGOUT] sign_out warning (ignored): {type(e).__name__}: {e}')
    session.clear()
    return jsonify({'ok': True})


@app.route('/api/auth/me')
def auth_me():
    if 'user_id' not in session:
        return jsonify({'user': None})
    return jsonify({
        'user': {
            'id': session['user_id'],
            'name': session.get('user_name'),
            'email': session.get('user_email')
        }
    })


# ---------- Onboarding ----------

@app.route('/api/disclaimer', methods=['POST'])
@login_required
def save_disclaimer():
    """Phase 3-2: 의료 면책 동의 시각을 users.disclaimer_agreed_at 에 기록."""
    uid = session['user_id']
    try:
        _authed_db().table('users').update({
            'disclaimer_agreed_at': datetime.now().isoformat()
        }).eq('id', uid).execute()
        return jsonify({'ok': True})
    except Exception as e:
        print(f'[DISCLAIMER] save error: {type(e).__name__}: {e}')
        return jsonify({'error': '면책 동의 저장 실패'}), 500


@app.route('/api/goals', methods=['GET'])
@login_required
def get_goals():
    """Phase 3-2: users 테이블에서 goal/goal_target_time/weekly_runs 조회.
    응답 키는 클라이언트 호환 위해 target_event/target_time/weekly_count 유지."""
    uid = session['user_id']
    try:
        res = _authed_db().table('users').select(
            'goal, goal_target_time, weekly_runs'
        ).eq('id', uid).single().execute()
    except Exception as e:
        print(f'[GOALS/GET] error: {type(e).__name__}: {e}')
        return jsonify({'goals': None})

    row = res.data or {}
    if not row.get('goal'):
        return jsonify({'goals': None})

    return jsonify({'goals': {
        'user_id': uid,
        'purpose': 'record',
        'target_event': row.get('goal'),
        'target_time': _seconds_to_hms(row.get('goal_target_time')),  # INT(초) → 'H:MM:SS'
        'weekly_count': row.get('weekly_runs') or 3,
    }})


@app.route('/api/goals', methods=['POST'])
@login_required
def save_goals():
    """Phase 3-2: 클라이언트 키(target_event/target_time/weekly_count)를
    DB 컬럼(goal/goal_target_time/weekly_runs)으로 매핑해서 UPDATE."""
    data = request.json or {}
    uid = session['user_id']
    try:
        _authed_db().table('users').update({
            'goal': data.get('target_event', 'half'),
            'goal_target_time': _hms_to_seconds(data.get('target_time')),  # 'H:MM:SS' → INT(초)
            'weekly_runs': int(data.get('weekly_count') or 3),
        }).eq('id', uid).execute()
        return jsonify({'ok': True})
    except Exception as e:
        print(f'[GOALS/SAVE] error: {type(e).__name__}: {e}')
        return jsonify({'error': '목표 저장 실패'}), 500


# ---------- Profile ----------

@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    """Phase 3-2: users 컬럼들 + health_records 최신 resting_hr 결합."""
    uid = session['user_id']
    authed = _authed_db()

    # (1) users 본인 row
    try:
        u_res = authed.table('users').select(
            'birth_date, gender, height, weight, max_hr, injury_history'
        ).eq('id', uid).single().execute()
        u = u_res.data
    except Exception as e:
        print(f'[PROFILE/GET] users error: {type(e).__name__}: {e}')
        return jsonify({'profile': None})

    if not u:
        return jsonify({'profile': None})

    # (2) health_records 최신 row → resting_hr
    resting_hr = None
    try:
        hr_res = authed.table('health_records').select(
            'resting_hr, measured_at'
        ).eq('user_id', uid).order('measured_at', desc=True).limit(1).execute()
        if hr_res.data and hr_res.data[0].get('resting_hr'):
            resting_hr = hr_res.data[0]['resting_hr']
    except Exception as e:
        print(f'[PROFILE/GET] health_records warning: {type(e).__name__}: {e}')

    # 프로필이 비어있다고 판단되면 None 반환 (UI가 "입력하세요" 표시)
    has_any = any([
        u.get('birth_date'), u.get('gender'), u.get('height'),
        u.get('weight'), u.get('max_hr'), u.get('injury_history'), resting_hr
    ])
    if not has_any:
        return jsonify({'profile': None})

    return jsonify({'profile': {
        'user_id': uid,
        'birth_date': u.get('birth_date'),
        'gender': u.get('gender'),
        'height': u.get('height'),
        'weight': u.get('weight'),
        'resting_hr': resting_hr,
        'max_hr': u.get('max_hr'),
        'injury_history': u.get('injury_history'),
    }})


@app.route('/api/profile', methods=['POST'])
@login_required
def save_profile():
    """Phase 3-2: users 컬럼 UPDATE + resting_hr 는 health_records 새 row INSERT."""
    data = request.json or {}
    uid = session['user_id']
    authed = _authed_db()

    gender = data.get('gender')
    if gender not in ('male', 'female'):
        gender = None

    # (1) users 컬럼 UPDATE — None 도 그대로 보내서 사용자가 비웠으면 NULL 처리
    try:
        authed.table('users').update({
            'birth_date': data.get('birth_date'),
            'gender': gender,
            'height': data.get('height'),
            'weight': data.get('weight'),
            'max_hr': data.get('max_hr'),
            'injury_history': data.get('injury_history'),
        }).eq('id', uid).execute()
    except Exception as e:
        print(f'[PROFILE/SAVE] users update error: {type(e).__name__}: {e}')
        return jsonify({'error': '프로필 저장 실패'}), 500

    # (2) resting_hr — 값이 있으면 health_records 에 새 row INSERT (이력 누적)
    resting_hr = data.get('resting_hr')
    if resting_hr:
        try:
            authed.table('health_records').insert({
                'user_id': uid,
                'resting_hr': int(resting_hr),
            }).execute()
        except Exception as e:
            print(f'[PROFILE/SAVE] health_records insert warning: {type(e).__name__}: {e}')
            # users UPDATE는 이미 성공 → 부분 성공 OK

    return jsonify({'ok': True})


# ---------- Dashboard ----------

@app.route('/api/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    """Phase 3-3 Step 2: Supabase 직접 SELECT (MOCK 의존 제거).

    - 이번 주 통계: running_sessions 임베디드 쿼리 (월요일~)
    - 최근 3건: session_metrics 임베디드 JOIN
    - 다음 훈련 추천: 가장 최근 ai_feedbacks
    - 목표: users 테이블의 goal/goal_target_time/weekly_runs 직접 매핑
    """
    uid = session['user_id']
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    week_start = monday.strftime('%Y-%m-%d')
    authed = _authed_db()

    # 이번 주 세션 (실 사용자 데이터만, 샘플 제외)
    weekly_runs = 0
    weekly_distance = 0.0
    weekly_duration = 0
    try:
        w_res = authed.table('running_sessions').select(
            'distance, duration'
        ).eq('user_id', uid).eq('is_sample', False).gte('run_date', week_start).execute()
        for r in (w_res.data or []):
            weekly_runs += 1
            weekly_distance += float(r.get('distance') or 0)
            weekly_duration += int(r.get('duration') or 0)
    except Exception as e:
        print(f'[DASHBOARD] weekly fetch warning: {type(e).__name__}: {e}')

    # 목표 (users 테이블)
    weekly_target = 3
    goals_payload = None
    try:
        u_res = authed.table('users').select(
            'goal, goal_target_time, weekly_runs'
        ).eq('id', uid).single().execute()
        if u_res.data:
            weekly_target = int(u_res.data.get('weekly_runs') or 3)
            if u_res.data.get('goal'):
                goals_payload = {
                    'user_id': uid,
                    'purpose': 'record',
                    'target_event': u_res.data.get('goal'),
                    'target_time': _seconds_to_hms(u_res.data.get('goal_target_time')),
                    'weekly_count': weekly_target,
                }
    except Exception as e:
        print(f'[DASHBOARD] goals fetch warning: {type(e).__name__}: {e}')

    # 최근 3건 + 임베디드 metrics + 가장 최근 feedback
    recent = []
    latest_metrics = None
    feedback = None
    try:
        # ORDER BY created_at DESC — 같은 run_date 의 여러 시도 중 가장 최근 INSERT 우선
        # (run_date DESC 만 쓰면 같은 날짜 내 순서가 임의가 됨 → 옛 실패 row가 latest로 잡힘)
        r_res = authed.table('running_sessions').select(
            'id, user_id, run_date, distance, duration, calories, '
            'avg_pace, avg_hr, max_hr, avg_cadence, avg_stride, is_sample, created_at, '
            'session_metrics(lrs, fi, ti), '
            'ai_feedbacks(summary, strengths, improvements, next_training)'
        ).eq('user_id', uid).eq('is_sample', False).order('created_at', desc=True).limit(3).execute()
        for r in (r_res.data or []):
            recent.append(r)
        if recent:
            sm = recent[0].get('session_metrics') or []
            latest_metrics = sm[0] if sm else None
            af = recent[0].get('ai_feedbacks') or []
            feedback = af[0] if af else None
    except Exception as e:
        print(f'[DASHBOARD] recent fetch warning: {type(e).__name__}: {e}')

    payload = {
        'weekly': {
            'runs': weekly_runs,
            'distance': round(weekly_distance, 1),
            'duration': weekly_duration,
            'target': weekly_target,
            'progress': min(100, round(weekly_runs / weekly_target * 100)) if weekly_target else 0
        },
        'metrics': latest_metrics,
        'feedback': feedback,
        'recent': recent,
        'goals': goals_payload,
    }
    # Phase 3-3 디버그: 응답 shape 검증 (Phase 3-7 정리 시 제거)
    print(f'[DASHBOARD] uid={uid} weekly={payload["weekly"]} '
          f'metrics={latest_metrics} '
          f'recent_count={len(recent)} '
          f'feedback_keys={list(feedback.keys()) if feedback else None}')
    return jsonify(payload)


# ---------- Sessions (History) ----------

@app.route('/api/sessions', methods=['GET'])
@login_required
def get_sessions():
    """Phase 3-3 Step 2: 히스토리 — Supabase 직접 SELECT.
    필터: this_month | last_month | all (default).
    """
    uid = session['user_id']
    filter_type = request.args.get('filter', 'all')
    now = datetime.now()

    q = _authed_db().table('running_sessions').select(
        'id, user_id, run_date, distance, duration, calories, '
        'avg_pace, avg_hr, max_hr, avg_cadence, avg_stride, is_sample, created_at, '
        'session_metrics(lrs, fi, ti), '
        'ai_feedbacks(summary, strengths, improvements, next_training)'
    ).eq('user_id', uid)

    if filter_type == 'this_month':
        start = now.replace(day=1).strftime('%Y-%m-%d')
        q = q.gte('run_date', start)
    elif filter_type == 'last_month':
        first_this = now.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        q = q.gte('run_date', last_month_start.strftime('%Y-%m-%d')) \
             .lte('run_date', last_month_end.strftime('%Y-%m-%d'))

    try:
        # 같은 run_date 내 여러 row 일관된 정렬 위해 created_at 보조키 (Phase 3-7 cleanup item)
        res = q.order('run_date', desc=True).order('created_at', desc=True).execute()
        return jsonify({'sessions': res.data or []})
    except Exception as e:
        print(f'[SESSIONS] fetch error: {type(e).__name__}: {e}')
        return jsonify({'sessions': []})


@app.route('/api/sessions/<string:session_id>', methods=['GET'])
@login_required
def get_session_detail(session_id):
    """Phase 3-3 Step 2: 세션 상세 — Supabase 임베디드 SELECT.
    UUID 라우트(<string:>) — 기존 <int:> 에서 변경 (UUID 호환).
    RLS 가 본인 row만 조회 허용 → 별도 user_id 체크 불필요.
    """
    uid = session['user_id']
    try:
        res = _authed_db().table('running_sessions').select(
            '*, session_metrics(*), ai_feedbacks(*), splits(*)'
        ).eq('id', session_id).eq('user_id', uid).single().execute()
    except Exception as e:
        print(f'[SESSION/DETAIL] error sid={session_id}: {type(e).__name__}: {e}')
        return jsonify({'error': '세션을 찾을 수 없습니다'}), 404

    if not res.data:
        return jsonify({'error': '세션을 찾을 수 없습니다'}), 404
    return jsonify({'session': res.data})


# ---------- CSV Upload (mock) ----------

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_csv():
    """Phase 3-3: harness.run_pipeline() 호출로 풀 파이프라인 실행.

    실제 흐름:
        Harness 0 (CSV 파싱) → 1 (입력 검증) → 2 (LRS/FI/TI 계산)
        → DB 저장 (running_sessions/splits/session_metrics)
        → Harness 3 (컨텍스트) → Claude API 호출 → 4 (안전 필터) → 5 (품질 검증)
        → ai_feedbacks INSERT → Harness 6 (ai_coaching_logs 로깅)
    """
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': '파일을 선택해주세요'}), 400

    # CSV 디코딩 (BOM 제거)
    try:
        content = file.read()
        if content[:3] == b'\xef\xbb\xbf':
            content = content[3:]
        csv_text = content.decode('utf-8')
    except UnicodeDecodeError:
        return jsonify({'error': 'CSV 파일 인코딩 오류 (UTF-8 필요)'}), 400

    uid = session['user_id']
    # access_token이 주입된 supabase-py Client (RLS 정책 통과용)
    supabase_client = _authed_db().raw

    print(f'[UPLOAD] user={uid} filename={file.filename} csv_size={len(csv_text)}자')

    try:
        from harness import run_pipeline
        result = run_pipeline(csv_text, uid, supabase_client, filename=file.filename)
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ---------- Sample Analysis (mock) ----------

SAMPLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'sample_data', 'sample_analysis.json')


@app.route('/api/sample-analysis', methods=['POST'])
@login_required
def sample_analysis():
    """Phase 3-7: 정적 JSON 기반 샘플 분석.

    DB INSERT/MOCK dict 의존 없이 sample_data/sample_analysis.json 의
    콘텐츠를 그대로 반환. run_date/created_at만 동적 주입.
    """
    uid = session['user_id']
    try:
        with open(SAMPLE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f'[SAMPLE] load failed: {type(e).__name__}: {e}')
        return jsonify({'error': '샘플 데이터를 불러올 수 없습니다'}), 500

    now_iso = datetime.now().isoformat()
    today = datetime.now().strftime('%Y-%m-%d')
    fake_sid = 'sample-fixed'

    summary = data['summary']
    metrics = data['metrics']
    feedback = data['feedback']
    splits = data['splits']

    return jsonify({
        'is_sample': True,
        'session': {
            'id': fake_sid,
            'user_id': uid,
            'run_date': today,
            'distance': summary['distance'],
            'duration': summary['duration'],
            'calories': summary['calories'],
            'avg_pace': summary['avg_pace'],
            'avg_hr': summary['avg_hr'],
            'max_hr': summary['max_hr'],
            'avg_cadence': summary['avg_cadence'],
            'avg_stride': summary['avg_stride'],
            'is_sample': True,
            'created_at': now_iso,
            'session_metrics': [{
                'session_id': fake_sid,
                'lrs': metrics['lrs'],
                'fi': metrics['fi'],
                'ti': metrics['ti'],
            }],
            'ai_feedbacks': [{
                'session_id': fake_sid,
                'summary': feedback['summary'],
                'strengths': feedback['strengths'],
                'improvements': feedback['improvements'],
                'next_training': feedback['next_training'],
                'full_response': {'is_sample': True},
                'created_at': now_iso,
            }],
            'splits': [{'session_id': fake_sid, **sp} for sp in splits],
        }
    })


# ============================================================

if __name__ == '__main__':
    print('\n' + '='*50)
    print('  ARCC Phase 2 - MOCK MODE')
    print('  DB/API 연동 없이 더미 데이터로 실행')
    print('  테스트 계정: runner@coros.com / 123456')
    print('='*50 + '\n')
    app.run(host='0.0.0.0', port=5000, debug=True)

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
app.secret_key = 'arcc-mock-dev-key'

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
    'sessions': {},
    'next_session_id': 1,
    'splits': {},
    'metrics': {},
    'feedbacks': {},
}


def _seed_mock_sessions():
    """초기 더미 러닝 세션 생성"""
    now = datetime.now()
    runs = [
        {'days_ago': 0, 'distance': 5.2, 'duration': 2280, 'calories': 345, 'avg_pace': '7:23', 'avg_hr': 152, 'max_hr': 172, 'avg_cadence': 178, 'avg_stride': 71, 'lrs': 78, 'fi': 28, 'ti': 'high'},
        {'days_ago': 2, 'distance': 7.5, 'duration': 3420, 'calories': 510, 'avg_pace': '7:36', 'avg_hr': 145, 'max_hr': 165, 'avg_cadence': 176, 'avg_stride': 70, 'lrs': 65, 'fi': 45, 'ti': 'moderate'},
        {'days_ago': 4, 'distance': 4.8, 'duration': 1680, 'calories': 290, 'avg_pace': '5:50', 'avg_hr': 162, 'max_hr': 185, 'avg_cadence': 185, 'avg_stride': 78, 'lrs': 58, 'fi': 62, 'ti': 'high'},
        {'days_ago': 7, 'distance': 10.1, 'duration': 4260, 'calories': 680, 'avg_pace': '7:02', 'avg_hr': 148, 'max_hr': 170, 'avg_cadence': 180, 'avg_stride': 72, 'lrs': 82, 'fi': 38, 'ti': 'moderate'},
        {'days_ago': 10, 'distance': 6.0, 'duration': 2520, 'calories': 400, 'avg_pace': '7:00', 'avg_hr': 140, 'max_hr': 158, 'avg_cadence': 182, 'avg_stride': 73, 'lrs': 85, 'fi': 22, 'ti': 'low'},
        {'days_ago': 14, 'distance': 8.3, 'duration': 3480, 'calories': 560, 'avg_pace': '6:59', 'avg_hr': 150, 'max_hr': 175, 'avg_cadence': 179, 'avg_stride': 74, 'lrs': 70, 'fi': 50, 'ti': 'high'},
        {'days_ago': 35, 'distance': 5.0, 'duration': 2100, 'calories': 330, 'avg_pace': '7:00', 'avg_hr': 142, 'max_hr': 160, 'avg_cadence': 180, 'avg_stride': 72, 'lrs': 75, 'fi': 30, 'ti': 'moderate'},
    ]

    split_templates = [
        {'pace': '7:30', 'avg_hr': 138, 'max_hr': 148, 'cadence': 176, 'stride': 70},
        {'pace': '7:20', 'avg_hr': 145, 'max_hr': 158, 'cadence': 178, 'stride': 71},
        {'pace': '7:10', 'avg_hr': 150, 'max_hr': 165, 'cadence': 180, 'stride': 72},
        {'pace': '7:15', 'avg_hr': 148, 'max_hr': 162, 'cadence': 179, 'stride': 72},
        {'pace': '6:55', 'avg_hr': 155, 'max_hr': 170, 'cadence': 182, 'stride': 74},
    ]

    for r in runs:
        sid = MOCK['next_session_id']
        MOCK['next_session_id'] += 1
        run_date = (now - timedelta(days=r['days_ago'])).strftime('%Y-%m-%d')

        MOCK['sessions'][sid] = {
            'id': sid, 'user_id': 1, 'run_date': run_date,
            'distance': r['distance'], 'duration': r['duration'],
            'calories': r['calories'], 'avg_pace': r['avg_pace'],
            'avg_hr': r['avg_hr'], 'max_hr': r['max_hr'],
            'avg_cadence': r['avg_cadence'], 'avg_stride': r['avg_stride'],
            'is_sample': False, 'created_at': run_date
        }
        MOCK['metrics'][sid] = {'session_id': sid, 'lrs': r['lrs'], 'fi': r['fi'], 'ti': r['ti']}

        num_splits = max(1, int(r['distance']))
        splits = []
        for i in range(num_splits):
            tpl = split_templates[i % len(split_templates)]
            splits.append({
                'session_id': sid, 'split_number': i + 1, 'distance': 1.0,
                'time': tpl['pace'], 'pace': tpl['pace'],
                'avg_hr': tpl['avg_hr'], 'max_hr': tpl['max_hr'],
                'cadence': tpl['cadence'], 'stride': tpl['stride']
            })
        MOCK['splits'][sid] = splits

    # AI feedback for most recent session
    first_sid = 1
    MOCK['feedbacks'][first_sid] = {
        'session_id': first_sid,
        'summary': '후반부 페이스를 잘 끌어올렸어요! 꾸준한 훈련 효과가 나타나고 있습니다.',
        'strengths': json.dumps([
            '네거티브 스플릿 달성 (후반 가속)',
            '심박수 존 3~4 유지로 효율적 훈련',
            '케이던스 178spm으로 안정적'
        ]),
        'improvements': json.dumps([
            '초반 1km 워밍업 페이스를 더 천천히',
            '케이던스를 182~185spm으로 올려보세요',
            '러닝 후 스트레칭 10분 추가'
        ]),
        'next_training': json.dumps({
            'type': '템포런',
            'duration': '40분',
            'pace': '6:30/km',
            'zone': 'Zone 3-4',
            'description': '하프마라톤 기록 단축을 위해 속도 지구력을 키워봐요!'
        }),
        'full_response': json.dumps({}),
        'created_at': datetime.now().isoformat()
    }

_seed_mock_sessions()


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


def _session_with_relations(sid):
    """세션 + metrics + feedbacks + splits 결합"""
    s = copy.deepcopy(MOCK['sessions'].get(sid))
    if not s:
        return None
    s['session_metrics'] = [MOCK['metrics'].get(sid)] if sid in MOCK['metrics'] else []
    s['ai_feedbacks'] = [MOCK['feedbacks'].get(sid)] if sid in MOCK['feedbacks'] else []
    s['splits'] = MOCK['splits'].get(sid, [])
    return s


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


# ---------- Auth ----------

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()
    name = data.get('name', '').strip()

    if not email or not password or not name:
        return jsonify({'error': '모든 필드를 입력해주세요'}), 400
    if len(password) < 6:
        return jsonify({'error': '비밀번호는 6자 이상이어야 합니다'}), 400

    for u in MOCK['users'].values():
        if u['email'] == email:
            return jsonify({'error': '이미 가입된 이메일입니다'}), 400

    uid = MOCK['next_user_id']
    MOCK['next_user_id'] += 1
    MOCK['users'][uid] = {
        'id': uid, 'email': email, 'name': name,
        'password_hash': hashlib.sha256(password.encode()).hexdigest()
    }
    # Defensive: ensure no stale profile/goals/disclaimer for this new user_id
    MOCK['profiles'].pop(uid, None)
    MOCK['goals'].pop(uid, None)
    MOCK['disclaimers'].pop(uid, None)

    session['user_id'] = uid
    session['user_name'] = name
    session['user_email'] = email
    return jsonify({'user': {'id': uid, 'name': name, 'email': email}})


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not email or not password:
        return jsonify({'error': '이메일과 비밀번호를 입력해주세요'}), 400

    pw_hash = hashlib.sha256(password.encode()).hexdigest()
    user = None
    for u in MOCK['users'].values():
        if u['email'] == email and u['password_hash'] == pw_hash:
            user = u
            break

    if not user:
        return jsonify({'error': '이메일 또는 비밀번호가 올바르지 않습니다'}), 401

    session['user_id'] = user['id']
    session['user_name'] = user['name']
    session['user_email'] = user['email']

    return jsonify({
        'user': {'id': user['id'], 'name': user['name'], 'email': user['email']},
        'has_disclaimer': user['id'] in MOCK['disclaimers'],
        'has_goals': user['id'] in MOCK['goals']
    })


@app.route('/api/auth/logout', methods=['POST'])
def logout():
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
    MOCK['disclaimers'][session['user_id']] = True
    return jsonify({'ok': True})


@app.route('/api/goals', methods=['GET'])
@login_required
def get_goals():
    g = MOCK['goals'].get(session['user_id'])
    return jsonify({'goals': g})


@app.route('/api/goals', methods=['POST'])
@login_required
def save_goals():
    data = request.json or {}
    MOCK['goals'][session['user_id']] = {
        'user_id': session['user_id'],
        'purpose': 'record',
        'target_event': data.get('target_event', 'half'),
        'target_time': data.get('target_time'),
        'weekly_count': data.get('weekly_count', 3)
    }
    return jsonify({'ok': True})


# ---------- Profile ----------

@app.route('/api/profile', methods=['GET'])
@login_required
def get_profile():
    p = MOCK['profiles'].get(session['user_id'])
    return jsonify({'profile': p})


@app.route('/api/profile', methods=['POST'])
@login_required
def save_profile():
    data = request.json or {}
    gender = data.get('gender')
    if gender not in ('male', 'female', None):
        gender = None
    MOCK['profiles'][session['user_id']] = {
        'user_id': session['user_id'],
        'birth_date': data.get('birth_date'),  # 'YYYY-MM-DD'
        'gender': gender,
        'height': data.get('height'),
        'weight': data.get('weight'),
        'resting_hr': data.get('resting_hr'),  # 프로덕션: health_records 최신값
        'max_hr': data.get('max_hr'),
        'injury_history': data.get('injury_history')
    }
    return jsonify({'ok': True})


# ---------- Dashboard ----------

@app.route('/api/dashboard', methods=['GET'])
@login_required
def get_dashboard():
    uid = session['user_id']
    now = datetime.now()
    monday = now - timedelta(days=now.weekday())
    week_start = monday.strftime('%Y-%m-%d')

    user_sessions = [s for s in MOCK['sessions'].values()
                     if s['user_id'] == uid and not s['is_sample']]

    # Weekly
    weekly = [s for s in user_sessions if s['run_date'] >= week_start]
    total_runs = len(weekly)
    total_distance = sum(s['distance'] for s in weekly)
    total_duration = sum(s['duration'] for s in weekly)

    goals = MOCK['goals'].get(uid, {})
    weekly_target = goals.get('weekly_count', 3) if goals else 3

    # Latest metrics
    sorted_sessions = sorted(user_sessions, key=lambda s: s['run_date'], reverse=True)
    latest_metrics = None
    if sorted_sessions:
        latest_id = sorted_sessions[0]['id']
        latest_metrics = MOCK['metrics'].get(latest_id)

    # Latest feedback
    feedback = None
    for s in sorted_sessions:
        if s['id'] in MOCK['feedbacks']:
            feedback = MOCK['feedbacks'][s['id']]
            break

    # Recent 3
    recent = []
    for s in sorted_sessions[:3]:
        rs = copy.deepcopy(s)
        rs['session_metrics'] = [MOCK['metrics'].get(s['id'])] if s['id'] in MOCK['metrics'] else []
        recent.append(rs)

    return jsonify({
        'weekly': {
            'runs': total_runs,
            'distance': round(total_distance, 1),
            'duration': total_duration,
            'target': weekly_target,
            'progress': min(100, round(total_runs / weekly_target * 100)) if weekly_target else 0
        },
        'metrics': latest_metrics,
        'feedback': feedback,
        'recent': recent,
        'goals': goals if goals else None
    })


# ---------- Sessions (History) ----------

@app.route('/api/sessions', methods=['GET'])
@login_required
def get_sessions():
    uid = session['user_id']
    filter_type = request.args.get('filter', 'all')
    now = datetime.now()

    user_sessions = [s for s in MOCK['sessions'].values() if s['user_id'] == uid]

    if filter_type == 'this_month':
        start = now.replace(day=1).strftime('%Y-%m-%d')
        user_sessions = [s for s in user_sessions if s['run_date'] >= start]
    elif filter_type == 'last_month':
        first_this = now.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        lms = last_month_start.strftime('%Y-%m-%d')
        lme = last_month_end.strftime('%Y-%m-%d')
        user_sessions = [s for s in user_sessions if lms <= s['run_date'] <= lme]

    user_sessions.sort(key=lambda s: s['run_date'], reverse=True)

    result = []
    for s in user_sessions:
        rs = copy.deepcopy(s)
        rs['session_metrics'] = [MOCK['metrics'].get(s['id'])] if s['id'] in MOCK['metrics'] else []
        rs['ai_feedbacks'] = [MOCK['feedbacks'].get(s['id'])] if s['id'] in MOCK['feedbacks'] else []
        result.append(rs)

    return jsonify({'sessions': result})


@app.route('/api/sessions/<int:session_id>', methods=['GET'])
@login_required
def get_session_detail(session_id):
    s = _session_with_relations(session_id)
    if not s or s['user_id'] != session['user_id']:
        return jsonify({'error': '세션을 찾을 수 없습니다'}), 404
    return jsonify({'session': s})


# ---------- CSV Upload (mock) ----------

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_csv():
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'error': '파일을 선택해주세요'}), 400

    # Mock: CSV를 실제로 파싱하되 AI 호출은 스킵
    try:
        content = file.read()
        if content[:3] == b'\xef\xbb\xbf':
            content = content[3:]
        csv_text = content.decode('utf-8')

        # 실제 CSV 파싱 (harness 0, 1, 2만 실행)
        from harness.csv_validator import validate as csv_validate
        from harness.input_validator import validate as input_validate
        from harness.metrics import calculate as calc_metrics

        parsed = csv_validate(csv_text)
        validated = input_validate(parsed, filename=file.filename)

        # 신체정보를 지표 계산에 반영 (개인화)
        user_profile = MOCK['profiles'].get(session['user_id'])
        if user_profile and user_profile.get('birth_date') and not user_profile.get('age'):
            # birth_date → age 계산 (metrics가 age 키를 기대)
            from harness.context_builder import _age_from_birth
            user_profile = dict(user_profile)
            user_profile['age'] = _age_from_birth(user_profile['birth_date'])
        calculated = calc_metrics(validated, profile=user_profile)  # supabase=None → 공식 fallback
        print(f'[MOCK/UPLOAD] user={session["user_id"]} profile={user_profile} '
              f'ti={calculated["ti"]} max_hr={calculated["max_hr_est"]}bpm ({calculated["max_hr_source"]})')

        # Mock 세션 저장
        sid = MOCK['next_session_id']
        MOCK['next_session_id'] += 1
        summary = validated['summary']

        MOCK['sessions'][sid] = {
            'id': sid, 'user_id': session['user_id'],
            'run_date': validated.get('date') or datetime.now().strftime('%Y-%m-%d'),
            'distance': summary['distance'], 'duration': summary['duration_sec'],
            'calories': summary.get('calories', 0), 'avg_pace': summary['avg_pace'],
            'avg_hr': summary['avg_hr'], 'max_hr': summary['max_hr'],
            'avg_cadence': summary['avg_cadence'], 'avg_stride': summary.get('avg_stride', 0),
            'is_sample': False, 'created_at': datetime.now().isoformat()
        }
        MOCK['metrics'][sid] = {'session_id': sid, 'lrs': calculated['lrs'], 'fi': calculated['fi'], 'ti': calculated['ti']}

        splits_data = []
        for i, sp in enumerate(validated['splits']):
            splits_data.append({
                'session_id': sid, 'split_number': i + 1, 'distance': sp['distance'],
                'time': sp['time'], 'pace': sp['pace'],
                'avg_hr': sp['avg_hr'], 'max_hr': sp['max_hr'],
                'cadence': sp['cadence'], 'stride': sp.get('stride', 0)
            })
        MOCK['splits'][sid] = splits_data

        # Mock AI feedback — 신체정보를 반영하여 사용자별로 다른 피드백 생성
        ti_kr = {'low': '저강도', 'moderate': '중강도', 'high': '고강도', 'very_high': '최고강도'}.get(calculated['ti'], '중강도')

        age = (user_profile or {}).get('age')
        weight = (user_profile or {}).get('weight')
        resting_hr = (user_profile or {}).get('resting_hr')

        # 연령대별 조언 차별화
        if age and age >= 50:
            age_advice = '50대 이상은 회복에 48시간 이상이 필요해요. 다음 훈련 전 충분히 쉬세요'
            next_type, next_pace, next_zone = '이지런 + 워킹 인터벌', '편한 페이스', 'Zone 2'
        elif age and age >= 40:
            age_advice = '40대는 점진적 훈련이 중요해요. 주 3~4회 페이스로 꾸준히'
            next_type, next_pace, next_zone = '지속주', '6:30~7:00/km', 'Zone 2-3'
        elif age and age >= 30:
            age_advice = '30대는 지구력과 속도 모두 발달시킬 수 있는 시기예요'
            next_type, next_pace, next_zone = '템포런', '6:00/km', 'Zone 3-4'
        elif age:
            age_advice = '20대의 젊음을 활용해 고강도 훈련에도 도전해보세요'
            next_type, next_pace, next_zone = '인터벌', '5:30/km', 'Zone 4'
        else:
            age_advice = '신체정보를 입력하면 연령별 맞춤 조언을 드려요'
            next_type, next_pace, next_zone = '이지런', '편한 페이스', 'Zone 2'

        # 안정시 심박수 기반 HRR 강도
        hrr_note = ''
        if age and resting_hr:
            max_hr_est = (user_profile or {}).get('max_hr') or (220 - age)
            hrr = max_hr_est - resting_hr
            if hrr > 0:
                hrr_pct = round((summary['avg_hr'] - resting_hr) / hrr * 100)
                hrr_note = f' HRR {hrr_pct}%로 개인 심폐능력 대비 {ti_kr} 운동이었습니다.'

        # 체중 기반 칼로리 소모 효율
        weight_note = ''
        if weight:
            est_kcal = round(summary['distance'] * weight * 1.036)
            weight_note = f'체중 {weight}kg 기준 예상 소모 {est_kcal}kcal (실측 {summary.get("calories", 0)}kcal)'

        strengths_list = [
            f'총 {summary["distance"]}km 완주',
            f'평균 심박수 {summary["avg_hr"]}bpm 유지',
            f'케이던스 {summary["avg_cadence"]}spm 유지'
        ]
        if weight_note:
            strengths_list.append(weight_note)

        MOCK['feedbacks'][sid] = {
            'session_id': sid,
            'summary': f'{ti_kr} 러닝 완료! 페이스 안정도 {calculated["lrs"]}점.{hrr_note}',
            'strengths': json.dumps(strengths_list),
            'improvements': json.dumps([
                age_advice,
                '케이던스를 185spm까지 올려보세요',
                '러닝 후 충분한 스트레칭'
            ]),
            'next_training': json.dumps({
                'type': next_type,
                'duration': '30분',
                'pace': next_pace,
                'zone': next_zone,
                'description': f'{age_advice} 맞춤 훈련으로 꾸준히 발전해봐요!'
            }),
            'full_response': json.dumps({'profile_used': bool(user_profile)}),
            'created_at': datetime.now().isoformat()
        }

        result = _session_with_relations(sid)
        return jsonify({'session': result, 'is_sample': False})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ---------- Sample Analysis (mock) ----------

@app.route('/api/sample-analysis', methods=['POST'])
@login_required
def sample_analysis():
    uid = session['user_id']
    sid = MOCK['next_session_id']
    MOCK['next_session_id'] += 1

    MOCK['sessions'][sid] = {
        'id': sid, 'user_id': uid,
        'run_date': datetime.now().strftime('%Y-%m-%d'),
        'distance': 5.0, 'duration': 2100, 'calories': 320,
        'avg_pace': '7:00', 'avg_hr': 145, 'max_hr': 168,
        'avg_cadence': 180, 'avg_stride': 72,
        'is_sample': True, 'created_at': datetime.now().isoformat()
    }

    MOCK['splits'][sid] = [
        {'session_id': sid, 'split_number': 1, 'distance': 1.0, 'time': '7:15', 'pace': '7:15', 'avg_hr': 138, 'max_hr': 148, 'cadence': 178, 'stride': 71},
        {'session_id': sid, 'split_number': 2, 'distance': 1.0, 'time': '7:05', 'pace': '7:05', 'avg_hr': 142, 'max_hr': 155, 'cadence': 180, 'stride': 72},
        {'session_id': sid, 'split_number': 3, 'distance': 1.0, 'time': '6:55', 'pace': '6:55', 'avg_hr': 148, 'max_hr': 160, 'cadence': 182, 'stride': 73},
        {'session_id': sid, 'split_number': 4, 'distance': 1.0, 'time': '7:00', 'pace': '7:00', 'avg_hr': 146, 'max_hr': 162, 'cadence': 180, 'stride': 72},
        {'session_id': sid, 'split_number': 5, 'distance': 1.0, 'time': '6:45', 'pace': '6:45', 'avg_hr': 150, 'max_hr': 168, 'cadence': 181, 'stride': 74},
    ]

    MOCK['metrics'][sid] = {'session_id': sid, 'lrs': 72, 'fi': 35, 'ti': 'moderate'}

    MOCK['feedbacks'][sid] = {
        'session_id': sid,
        'summary': '안정적인 페이스로 5km를 완주했어요! 심박수 관리도 잘 되고 있네요.',
        'strengths': json.dumps([
            '일정한 페이스 유지 (7:00/km)',
            '적정 심박수 존 유지 (145bpm)',
            '후반부 페이스 향상 (네거티브 스플릿)'
        ]),
        'improvements': json.dumps([
            '케이던스를 185spm까지 올려보세요',
            '마지막 1km 페이스 유지 연습',
            '워밍업 구간을 추가해보세요'
        ]),
        'next_training': json.dumps({
            'type': '인터벌',
            'duration': '30분',
            'pace': '6:30/km',
            'zone': 'Zone 3-4',
            'description': '400m x 6회, 회복 200m 조깅. 하프마라톤 기록 단축을 위해 속도 지구력을 키워봐요!'
        }),
        'full_response': json.dumps({'is_sample': True}),
        'created_at': datetime.now().isoformat()
    }

    result = _session_with_relations(sid)
    return jsonify({'session': result, 'is_sample': True})


# ============================================================

if __name__ == '__main__':
    print('\n' + '='*50)
    print('  ARCC Phase 2 - MOCK MODE')
    print('  DB/API 연동 없이 더미 데이터로 실행')
    print('  테스트 계정: runner@coros.com / 123456')
    print('='*50 + '\n')
    app.run(host='0.0.0.0', port=5000, debug=True)

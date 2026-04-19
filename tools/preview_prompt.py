"""AI 분석 요청 프롬프트 시뮬레이터.

Claude API 호출 전, 실제로 Claude에게 전달되는 system prompt + user context 전문을 출력합니다.
Supabase를 FakeSupabase로 스텁해서 DB 없이도 실행 가능.

실행:
    python tools/preview_prompt.py
"""
import sys
import os
import json
import io
from datetime import datetime, timedelta

# Force UTF-8 output on Windows (cp949 default)
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from harness import context_builder, metrics


# ============================================================
# FakeSupabase: context_builder의 supabase.table(...).select(...)...execute() 체인 흉내
# ============================================================
class _Result:
    def __init__(self, data): self.data = data

class _Query:
    def __init__(self, store, table):
        self.store = store; self.table = table; self.filters = []; self._limit = None
    def select(self, *a, **kw): return self
    def eq(self, k, v): self.filters.append(('eq', k, v)); return self
    def gte(self, k, v): self.filters.append(('gte', k, v)); return self
    def order(self, *a, **kw): return self
    def limit(self, n): self._limit = n; return self
    def single(self):
        # .single() → execute() returns first row as dict (not list)
        self._single = True
        return self
    def execute(self):
        rows = self.store.get(self.table, [])
        out = []
        for r in rows:
            ok = True
            for op, k, v in self.filters:
                if op == 'eq' and r.get(k) != v: ok = False; break
                if op == 'gte' and r.get(k, '') < v: ok = False; break
            if ok: out.append(r)
        if self._limit: out = out[:self._limit]
        if getattr(self, '_single', False):
            return _Result(out[0] if out else None)
        return _Result(out)

class FakeSupabase:
    def __init__(self, store): self.store = store
    def table(self, name): return _Query(self.store, name)


# ============================================================
# 시나리오 A: 완전한 데이터 - 50대 여성, 하프마라톤 목표, 30일 기록 다수
# ============================================================
def scenario_full():
    now = datetime.now()
    past = [
        {'id': 100, 'user_id': 1, 'run_date': (now - timedelta(days=d)).strftime('%Y-%m-%d'),
         'created_at': (now - timedelta(days=d)).strftime('%Y-%m-%d'),
         'distance': dist, 'avg_pace': pace, 'avg_hr': hr, 'max_hr': mhr,
         'is_sample': False,
         'session_metrics': [{'lrs': lrs, 'fi': fi, 'ti': ti}]}
        for d, dist, pace, hr, mhr, lrs, fi, ti in [
            (3, 5.2, '7:20', 148, 172, 72, 35, 'moderate'),
            (6, 8.0, '7:05', 152, 178, 65, 52, 'high'),
            (10, 6.1, '7:15', 145, 165, 78, 28, 'moderate'),
            (14, 10.3, '6:58', 155, 181, 60, 58, 'high'),  # ← 실측 최대값
            (18, 5.0, '7:30', 140, 158, 82, 22, 'low'),
            (22, 7.5, '7:00', 150, 170, 68, 45, 'moderate'),
            (27, 5.5, '7:25', 142, 163, 80, 30, 'low'),
        ]
    ]
    # 프로덕션 스키마: users 테이블에 프로필/목표 통합, health_records에 resting_hr
    store = {
        'users': [{
            'id': 1, 'gender': 'female', 'birth_date': '1972-08-10',  # 약 52-53세
            'height': 162.0, 'weight': 58.5,
            'max_hr': None,  # 직접 입력 없음 → 실측/공식으로 폴백
            'injury_history': '왼쪽 무릎 반월판 부분 파열 (2023)',
            'goal': 'half', 'goal_target_time': '2:00:00', 'weekly_runs': 4,
        }],
        'health_records': [
            {'user_id': 1, 'resting_hr': 62, 'measured_at': '2026-04-10'}
        ],
        'running_sessions': past,
    }
    validated = {
        'summary': {
            'distance': 6.5, 'duration_sec': 2880, 'calories': 385,
            'avg_pace': '7:23', 'avg_hr': 151, 'max_hr': 172,
            'avg_cadence': 178, 'avg_stride': 70
        },
        'splits': [
            {'pace': '7:35', 'avg_hr': 142, 'cadence': 176},
            {'pace': '7:28', 'avg_hr': 148, 'cadence': 177},
            {'pace': '7:22', 'avg_hr': 152, 'cadence': 178},
            {'pace': '7:20', 'avg_hr': 154, 'cadence': 179},
            {'pace': '7:18', 'avg_hr': 155, 'cadence': 180},
            {'pace': '7:15', 'avg_hr': 157, 'cadence': 180},
        ],
        'date': now.strftime('%Y-%m-%d'),
    }
    supa = FakeSupabase(store)
    # 프로필을 실제 경로(_fetch_profile)로 조립해서 metrics에 전달
    from harness import _fetch_profile
    profile = _fetch_profile(1, supa)
    calc = metrics.calculate(validated, profile=profile, user_id=1, supabase=supa)
    return 'A. 완전 데이터 (52세 여성, 하프 목표, 7회 기록)', 1, validated, calc, supa


# ============================================================
# 시나리오 B: 신체정보 없음 - 신규 유저
# ============================================================
def scenario_minimal():
    store = {'users': [], 'health_records': [], 'running_sessions': []}
    validated = {
        'summary': {
            'distance': 5.0, 'duration_sec': 2100, 'calories': 320,
            'avg_pace': '7:00', 'avg_hr': 145, 'max_hr': 168,
            'avg_cadence': 180, 'avg_stride': 72
        },
        'splits': [
            {'pace': '7:10', 'avg_hr': 138, 'cadence': 178},
            {'pace': '7:00', 'avg_hr': 145, 'cadence': 180},
            {'pace': '6:55', 'avg_hr': 150, 'cadence': 182},
            {'pace': '6:58', 'avg_hr': 148, 'cadence': 181},
            {'pace': '6:50', 'avg_hr': 152, 'cadence': 183},
        ],
        'date': datetime.now().strftime('%Y-%m-%d'),
    }
    calc = metrics.calculate(validated, profile=None)
    return 'B. 신체정보 없음 (신규 유저)', 2, validated, calc, FakeSupabase(store)


# ============================================================
# SYSTEM PROMPT (harness/__init__.py 와 동일)
# ============================================================
SYSTEM_PROMPT = """당신은 ARCC(AI Running Coaching by Claude)의 AI 러닝 코치입니다.
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


def print_section(title, ch='='):
    print('\n' + ch * 72)
    print(f' {title}')
    print(ch * 72)


def run(scenario_fn):
    name, user_id, validated, calc, supa = scenario_fn()
    print_section(f'시나리오: {name}', '#')

    print_section('[1] SYSTEM PROMPT (Claude `system` 파라미터)', '=')
    print(SYSTEM_PROMPT)

    print_section('[2] 계산된 지표 (harness 2)', '=')
    print(f'  LRS(페이스 안정도) = {calc["lrs"]}')
    print(f'  FI (피로도)       = {calc["fi"]}')
    print(f'  TI (훈련 강도)    = {calc["ti"]}')
    print(f'  최대심박 추정     = {calc["max_hr_est"]}bpm  ({calc["max_hr_source"]})')

    context = context_builder.build(user_id, validated, calc, supa)

    print_section('[3] USER MESSAGE - Claude에게 전달되는 실제 컨텍스트', '=')
    print(context)

    print_section('[4] 포함 여부 체크리스트', '=')
    checks = [
        ('이번 세션 러닝 데이터',   '## 현재 러닝 데이터' in context),
        ('구간별 페이스/HR/케이던스', '## 구간 데이터' in context),
        ('LRS/FI/TI 계산값',         '## 분석 지표' in context),
        ('사용자 프로필 (나이/체중)', '## 사용자 정보' in context),
        ('성별',                      '성별:' in context),
        ('최대심박 추정 방식 표시',   '러닝 기록 기반' in context or '공식 계산' in context or '직접 입력' in context),
        ('안정시 심박수',            '안정시 심박수' in context),
        ('HRR 기반 개인 강도',       'HRR 기반 강도' in context),
        ('부상 이력',                '부상 이력' in context),
        ('목표 (종목/기록)',         '## 목표' in context),
        ('과거 30일 러닝 기록',      '## 최근 30일' in context),
        ('과거 LRS/FI/TI 추이',      '지표 추이' in context),
    ]
    for label, ok in checks:
        print(f'  [{"O" if ok else "X"}] {label}')

    print_section('[5] 요약', '=')
    print(f'  컨텍스트 길이: {len(context)}자 (≈ {len(context)//2} 토큰)')
    print(f'  max_chars 8000 대비 {len(context)*100//8000}% 사용')


if __name__ == '__main__':
    run(scenario_full)
    print('\n\n')
    run(scenario_minimal)

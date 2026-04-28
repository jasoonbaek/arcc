import os
from dotenv import load_dotenv

load_dotenv(override=True)  # OS 환경변수보다 .env 우선 — 빈 환경변수 prior 잔존 문제 회피

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
SECRET_KEY = os.environ.get('SECRET_KEY', 'arcc-phase2-secret-key-change-in-production')

# ---- 모드 플래그 ----
# SUPABASE_URL + SUPABASE_KEY 가 둘 다 설정되어 있을 때만 Supabase 모드
# 둘 중 하나라도 비어있으면 MOCK 인메모리 모드로 자동 폴백
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# ---- 안전 모드 (비상 폴백) ----
# Supabase 전환 중 문제가 생기면 이 값을 True로 바꾸고 서버 재시작 → 즉시 MOCK 모드로 복귀
# (.env 환경변수 ROLLBACK_TO_MOCK=1 로도 켤 수 있음)
ROLLBACK_TO_MOCK = os.environ.get('ROLLBACK_TO_MOCK', '0').lower() in ('1', 'true', 'yes')

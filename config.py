import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
SECRET_KEY = os.environ.get('SECRET_KEY', 'arcc-phase2-secret-key-change-in-production')

# ---- 모드 플래그 ----
# SUPABASE_URL + SUPABASE_KEY 가 둘 다 설정되어 있을 때만 Supabase 모드
# 둘 중 하나라도 비어있으면 MOCK 인메모리 모드로 자동 폴백
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

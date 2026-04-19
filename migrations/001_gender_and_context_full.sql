-- ARCC Migration 001 (v2) — 기존 프로덕션 DB 구조에 맞춰 재작성
-- Date: 2026-04-17
--
-- 발견 사항:
--   - users 테이블에 이미 gender, birth_date, height, weight, goal, weekly_runs 존재
--   - health_records 테이블에 resting_hr, measured_at 저장됨
--   - 별도 user_profile / goals 테이블 없음
--
-- 필요한 변경:
--   1) users.max_hr 컬럼 추가 (사용자가 직접 입력하는 최대심박수)
--   2) ai_coaching_logs 테이블 신규 생성 (없으면)
--   3) ai_coaching_logs.context_full 컬럼 (아카이빙)

-- ===== 1. users.max_hr 추가 =====
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS max_hr INTEGER;

-- ===== 2. ai_coaching_logs 테이블 =====
CREATE TABLE IF NOT EXISTS ai_coaching_logs (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,
  session_id UUID REFERENCES running_sessions(id) ON DELETE SET NULL,
  api_duration_ms INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  harness0_passed BOOLEAN,
  harness1_passed BOOLEAN,
  harness4_passed BOOLEAN,
  harness5_passed BOOLEAN,
  retry_count INTEGER DEFAULT 0,
  quality_score INTEGER,
  is_sample BOOLEAN DEFAULT FALSE,
  context_full TEXT,  -- 하네스 3에서 Claude에게 전달한 전체 프롬프트 (아카이빙)
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 이미 존재하는 경우 context_full 컬럼만 추가
ALTER TABLE ai_coaching_logs
  ADD COLUMN IF NOT EXISTS context_full TEXT;

-- 인덱스: 사용자별/세션별 로그 조회 최적화
CREATE INDEX IF NOT EXISTS idx_ai_logs_user ON ai_coaching_logs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ai_logs_session ON ai_coaching_logs(session_id);

-- ===== 확인 쿼리 (주석 해제 후 실행) =====
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'users' AND column_name IN ('gender','birth_date','max_hr','goal','weekly_runs');
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'ai_coaching_logs';

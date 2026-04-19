-- ARCC Phase 2 Database Schema
-- Supabase (PostgreSQL)
--
-- 주의: 프로덕션 users 테이블은 이미 Phase 1에서 생성되어 있으며 아래 필드를 포함함.
--       신규 배포 시에만 이 스키마 사용. 기존 DB는 migrations/ 디렉토리 적용.

-- 사용자 테이블 (프로필 통합)
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  name VARCHAR(100) NOT NULL,
  password_hash VARCHAR(64),
  -- 프로필 필드 (user_profile 별도 테이블 없음)
  gender TEXT CHECK (gender IS NULL OR gender IN ('male', 'female')),
  birth_date DATE,
  height DECIMAL(5,1),   -- cm
  weight DECIMAL(5,1),   -- kg
  bmi DECIMAL(4,1),
  max_hr INTEGER,        -- 직접 입력값 (없으면 실측/공식으로 추정)
  blood_pressure_sys INTEGER,
  blood_pressure_dia INTEGER,
  skeletal_muscle DECIMAL(5,1),
  body_fat_rate DECIMAL(4,1),
  visceral_fat INTEGER,
  injury_history TEXT,
  -- 목표 필드 (goals 별도 테이블 없음)
  goal VARCHAR(20),              -- '10K' | 'half' | 'full'
  goal_target_time VARCHAR(10),  -- 'HH:MM:SS'
  weekly_runs INTEGER,
  run_duration INTEGER,          -- 분 단위
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 건강 측정 이력
CREATE TABLE IF NOT EXISTS health_records (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  measured_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  resting_hr INTEGER,  -- 안정시 심박수
  weight DECIMAL(5,1),
  height DECIMAL(5,1),
  bmi DECIMAL(4,1),
  notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_health_records_user_date
  ON health_records(user_id, measured_at DESC);

-- 러닝 세션
CREATE TABLE IF NOT EXISTS running_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  run_date DATE NOT NULL,
  distance DECIMAL(6,2),  -- km
  duration INTEGER,  -- seconds
  calories INTEGER,
  avg_pace VARCHAR(10),  -- 'MM:SS'
  avg_hr INTEGER,
  max_hr INTEGER,
  avg_cadence INTEGER,
  avg_stride INTEGER,  -- cm
  is_sample BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 구간 데이터
CREATE TABLE IF NOT EXISTS splits (
  id SERIAL PRIMARY KEY,
  session_id INTEGER REFERENCES running_sessions(id) ON DELETE CASCADE,
  split_number INTEGER NOT NULL,
  distance DECIMAL(6,2),
  time VARCHAR(10),
  pace VARCHAR(10),
  avg_hr INTEGER,
  max_hr INTEGER,
  cadence INTEGER,
  stride INTEGER
);

-- 세션 지표 (LRS/FI/TI)
CREATE TABLE IF NOT EXISTS session_metrics (
  id SERIAL PRIMARY KEY,
  session_id INTEGER REFERENCES running_sessions(id) ON DELETE CASCADE,
  lrs INTEGER,  -- 페이스 안정도 0-100
  fi INTEGER,   -- 피로도 0-100
  ti VARCHAR(20),  -- 훈련 강도 low/moderate/high/very_high
  UNIQUE(session_id)
);

-- AI 피드백
CREATE TABLE IF NOT EXISTS ai_feedbacks (
  id SERIAL PRIMARY KEY,
  session_id INTEGER REFERENCES running_sessions(id) ON DELETE CASCADE,
  summary TEXT,
  strengths JSONB,  -- ["항목1", "항목2"]
  improvements JSONB,
  next_training JSONB,  -- {"type": "", "duration": "", "description": ""}
  full_response JSONB,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(session_id)
);

-- AI 코칭 로그
CREATE TABLE IF NOT EXISTS ai_coaching_logs (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  session_id UUID REFERENCES running_sessions(id),
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
  context_full TEXT,  -- Claude에게 전달된 전체 프롬프트 (아카이빙)
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 의료 면책 동의
CREATE TABLE IF NOT EXISTS medical_disclaimers (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  agreed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id)
);

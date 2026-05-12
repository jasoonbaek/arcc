-- ============================================================
-- ARCC master_schema.sql
-- ============================================================
-- 목적: ARCC (AI Running Coaching by Claude) 프로젝트의
--       Supabase PostgreSQL 데이터베이스 *진짜* 스키마 정의
-- 작성일: 2026-05-09 (KST)
-- 작성 근거:
--   - D-035 (schema 진실 복원 + master_schema.sql 채택)
--   - D-037 (Q-018~Q-022 통합 결정 5종 반영)
-- 출처:
--   - Mumbai Supabase 운영 DB 추출 (5/9 17:30~19:50)
--   - docs/mumbai_schema_extracted_5_9.md
-- 단일 진실 원칙: D-007
-- 적용: D-034 Seoul 이전 시 이 파일 사용
-- ============================================================

-- ----------------------------------------------------------
-- 1. users (사용자 + 프로필 통합)
-- ----------------------------------------------------------
-- 5/9 발견:
-- - subscription_tier: B2C 구독 모델 3단계 (free/plus/pro) - D-037 Q-020
-- - disclaimer_agreed_at: 의료 면책 동의 (medical_disclaimers 테이블 대체)
-- - gender CHECK: D-037 Q-020 채택 (4개 값 + NULL)
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  
  -- 인구통계 정보
  gender TEXT CHECK (
    gender IS NULL 
    OR gender IN ('male', 'female', 'other', 'prefer_not_to_say')
  ),
  birth_date DATE,
  
  -- 신체 정보 (현재 시점 스냅샷, 시계열은 health_records/health_metrics)
  height DECIMAL(5,2),                -- cm
  weight DECIMAL(5,2),                -- kg
  bmi DECIMAL(5,2),
  blood_pressure_sys INTEGER,         -- 수축기 혈압
  blood_pressure_dia INTEGER,         -- 이완기 혈압
  skeletal_muscle DECIMAL(5,2),       -- 골격근량 (kg)
  body_fat_rate DECIMAL(5,2),         -- 체지방률 (%)
  visceral_fat INTEGER,               -- 내장지방 레벨
  max_hr INTEGER,                     -- 최대 심박수 (직접 입력 또는 추정)
  injury_history TEXT,                -- 부상 이력 (자유 텍스트)
  
  -- 러닝 목표
  goal TEXT,                          -- '10K', 'half', 'full' 등
  goal_target_time INTEGER,           -- 목표 시간 (초 단위)
  weekly_runs INTEGER,                -- 주간 러닝 횟수
  run_duration INTEGER,               -- 평균 러닝 시간 (분)
  
  -- 비즈니스 속성
  subscription_tier VARCHAR(10) NOT NULL DEFAULT 'free'
    CHECK (subscription_tier IN ('free', 'plus', 'pro')),
  disclaimer_agreed_at TIMESTAMP WITH TIME ZONE,
  
  -- 메타
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- ----------------------------------------------------------
-- 2. health_records (건강 측정 이력 - 시계열)
-- ----------------------------------------------------------
-- 측정 기록은 보존 정책 (UPDATE/DELETE RLS 차단)
CREATE TABLE IF NOT EXISTS health_records (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,  -- D-037 Q-018
  measured_at DATE DEFAULT CURRENT_DATE,
  
  -- 활력 징후
  resting_hr INTEGER,                 -- 안정시 심박수
  bp_systolic INTEGER,                -- 수축기 혈압
  bp_diastolic INTEGER,               -- 이완기 혈압
  
  -- 체성분
  weight DECIMAL(5,1),                -- kg
  height DECIMAL(5,1),                -- cm
  bmi DECIMAL(5,1),
  bmr INTEGER,                        -- 기초대사량 (kcal)
  skeletal_muscle DECIMAL(5,1),       -- 골격근량 (kg)
  body_fat_pct DECIMAL(5,1),          -- 체지방률 (%)
  visceral_fat INTEGER,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- ----------------------------------------------------------
-- 3. running_sessions (러닝 세션 - 핵심 테이블)
-- ----------------------------------------------------------
-- 5/9 발견 4 (D-037 Q-022): csv_data 유지, splits_data 제거
-- - csv_data: 원본 CSV 보존 (특허/디버깅 추적성)
-- - splits 테이블: 정규화 분석 데이터 (별도 테이블 활용)
-- - splits_data: 제거 (중복, 디스크 11GB 절감 @ 11만명)
CREATE TABLE IF NOT EXISTS running_sessions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,  -- D-037 Q-018
  
  -- 러닝 기본 정보
  run_date DATE,
  distance DECIMAL(6,2),              -- km
  duration INTEGER,                   -- 초
  calories INTEGER,
  
  -- 페이스 / 심박
  avg_pace TEXT,                      -- 'MM:SS' 형식
  avg_hr INTEGER,
  max_hr INTEGER,
  
  -- 케이던스 / 스트라이드
  avg_cadence INTEGER,                -- 분당 발걸음 수
  avg_stride INTEGER,                 -- 평균 보폭 (cm)
  
  -- 고도
  elevation_gain INTEGER,             -- 상승 (m)
  elevation_loss INTEGER,             -- 하강 (m)
  
  -- 원본 데이터 (D-037 Q-022 - 보존)
  csv_data JSONB,                     -- COROS/Garmin 원본 CSV (추적성)
  
  -- 메타
  is_sample BOOLEAN DEFAULT false,    -- 샘플 데이터 여부
  created_at TIMESTAMP DEFAULT now()
);

-- ----------------------------------------------------------
-- 4. splits (구간 데이터 - 정규화)
-- ----------------------------------------------------------
-- 5/9 발견: id BIGINT 시퀀스 운영 중 (Q-012 해결)
-- D-037 Q-022 채택: 정규화 분석용으로 유지
CREATE TABLE IF NOT EXISTS splits (
  id BIGSERIAL PRIMARY KEY,
  session_id UUID NOT NULL REFERENCES running_sessions(id) ON DELETE CASCADE,
  
  split_number INTEGER NOT NULL,      -- 구간 번호 (1, 2, 3...)
  
  -- 구간별 측정값
  distance DECIMAL(6,2),              -- 구간 거리 (km)
  time VARCHAR(10),                   -- 구간 시간 'MM:SS' 또는 'HH:MM:SS'
  pace VARCHAR(10),                   -- 구간 페이스 'MM:SS'
  avg_hr INTEGER,
  max_hr INTEGER,
  cadence INTEGER,
  stride INTEGER,                     -- 보폭 (cm)
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
  
  -- 한 세션에서 같은 split_number 중복 방지
  UNIQUE (session_id, split_number)
);

-- ----------------------------------------------------------
-- 5. session_metrics (세션 지표 - LRS/FI/TI)
-- ----------------------------------------------------------
-- 도메인 용어 (메모리 박제):
-- - LRS (Running Rhythm Stability): 러닝리듬 안정도 0-100
-- - FI (Fatigue Index): 피로도 지수 0-100
-- - TI (Training Intensity): 훈련 강도 (low/moderate/high/very_high)
CREATE TABLE IF NOT EXISTS session_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID REFERENCES running_sessions(id) ON DELETE CASCADE,
  
  lrs INTEGER,                        -- 0-100, 페이스 안정도
  fi INTEGER,                         -- 0-100, 피로도
  ti VARCHAR(20)                      -- 'low'/'moderate'/'high'/'very_high'
    CHECK (ti IS NULL OR ti IN ('low', 'moderate', 'high', 'very_high')),
  
  calculated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- ----------------------------------------------------------
-- 6. health_metrics (체성분 측정 데이터 - 시계열)
-- ----------------------------------------------------------
-- 도메인 용어 (메모리 박제, 특허 전략):
-- - "체성분 측정 데이터"로 통칭 (브랜드 중립)
-- 5/9 발견 1: RLS 정책 누락 → D-037 Q-019로 해결 (RLS 섹션 참조)
CREATE TABLE IF NOT EXISTS health_metrics (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,  -- D-037 Q-018
  measured_date DATE NOT NULL,
  
  -- 체성분 측정값
  weight DECIMAL(5,2),                -- kg
  body_fat_rate DECIMAL(5,2),         -- 체지방률 (%)
  skeletal_muscle DECIMAL(5,2),       -- 골격근량 (kg)
  visceral_fat INTEGER,               -- 내장지방 레벨
  inbody_score INTEGER,               -- 체성분 측정 종합 점수
  
  -- 활력 징후
  blood_pressure_sys INTEGER,         -- 수축기 혈압
  blood_pressure_dia INTEGER,         -- 이완기 혈압
  
  created_at TIMESTAMP DEFAULT now()
);

-- ----------------------------------------------------------
-- 7. ai_conversations (AI 대화 이력 - ARCC 핵심 차별점)
-- ----------------------------------------------------------
-- 5/9 발견 2: schema.sql에 누락됐던 테이블 (D-035로 발견)
-- 비즈니스 의미: ChatGPT 대비 ARCC의 핵심 moat = 누적 코칭 이력
CREATE TABLE IF NOT EXISTS ai_conversations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,  -- D-037 Q-018 (NO ACTION → CASCADE)
  session_id UUID REFERENCES running_sessions(id) ON DELETE CASCADE,  -- D-037 Q-018
  
  -- 대화 내용
  request_data JSONB,                 -- Claude API 요청 데이터
  ai_response TEXT,                   -- Claude 응답 본문
  analysis_type TEXT,                 -- 분석 유형 (예: 'session_analysis', 'weekly_review')
  
  created_at TIMESTAMP DEFAULT now()
);

-- ----------------------------------------------------------
-- 8. ai_feedbacks (AI 피드백 - 구조화)
-- ----------------------------------------------------------
-- 5/9 발견 5: feedback_type 컬럼 존재 (세션/주간/월간 구분 가능)
-- - 향후 Q-002, Q-003 (자동 훈련 계획, 다음 세션 추천) 구현 시 활용
-- 5/9 발견 4: ai_feedbacks DELETE 차단 (RLS 의도)
CREATE TABLE IF NOT EXISTS ai_feedbacks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,  -- D-037 Q-018
  session_id UUID REFERENCES running_sessions(id) ON DELETE CASCADE,
  
  -- 피드백 분류 (5/9 발견 5)
  feedback_type TEXT DEFAULT 'session',  -- 'session'/'weekly'/'monthly' 등
  feedback_data JSONB,                   -- 확장 가능한 피드백 데이터
  
  -- 구조화된 피드백 (Claude 응답 파싱 결과)
  summary TEXT,                       -- 요약
  strengths JSONB,                    -- ["항목1", "항목2"] 강점 배열
  improvements JSONB,                 -- 개선점 배열
  next_training JSONB,                -- {"type": "", "duration": "", "description": ""}
  full_response JSONB,                -- 원본 Claude 응답 전체
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- ----------------------------------------------------------
-- 9. ai_coaching_logs (AI 코칭 로그 - 운영 분석용)
-- ----------------------------------------------------------
-- 5/9 발견: id BIGINT 시퀀스 (Q-012 해결)
-- D-037 Q-018: SET NULL 유지 (사용자 탈퇴 후에도 익명 로그 보존)
-- 메모리 박제 D-022 Level 1+2+3과 관련:
-- - harness0~5_passed: AI 응답 품질 검증 통과 여부
CREATE TABLE IF NOT EXISTS ai_coaching_logs (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES users(id) ON DELETE SET NULL,        -- D-037 Q-018 유지
  session_id UUID REFERENCES running_sessions(id) ON DELETE SET NULL,  -- D-037 Q-018 유지
  
  -- API 호출 측정값
  api_duration_ms INTEGER,            -- API 호출 소요 시간 (ms)
  input_tokens INTEGER,               -- 입력 토큰 수
  output_tokens INTEGER,              -- 출력 토큰 수
  retry_count INTEGER DEFAULT 0,      -- 재시도 횟수
  
  -- 품질 검증 (Harness 시스템)
  quality_score INTEGER,              -- 품질 점수
  harness0_passed BOOLEAN,            -- Harness 0 통과 여부
  harness1_passed BOOLEAN,            -- Harness 1 통과 여부
  harness4_passed BOOLEAN,            -- Harness 4 통과 여부
  harness5_passed BOOLEAN,            -- Harness 5 통과 여부
  
  -- 컨텍스트 보존
  context_full TEXT,                  -- Claude에게 전달된 전체 프롬프트 (아카이빙)
  is_sample BOOLEAN DEFAULT false,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- ============================================================
-- RLS (Row Level Security) 정책
-- ============================================================
-- 5/9 발견: 9개 테이블 모두 RLS 활성화 운영
-- D-037 Q-019: health_metrics 정책 신규 추가 (누락 해소)
-- 패턴 1: 단순 own (auth.uid() = user_id)
-- 패턴 2: 간접 own (running_sessions 통한 EXISTS)

-- ----------------------------------------------------------
-- 모든 테이블 RLS 활성화
-- ----------------------------------------------------------
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE running_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE splits ENABLE ROW LEVEL SECURITY;
ALTER TABLE session_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE health_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_feedbacks ENABLE ROW LEVEL SECURITY;
ALTER TABLE ai_coaching_logs ENABLE ROW LEVEL SECURITY;

-- ----------------------------------------------------------
-- users (본인만 SELECT/UPDATE, INSERT는 Auth 처리, DELETE는 별도)
-- ----------------------------------------------------------
CREATE POLICY users_select_own ON users
  FOR SELECT USING (auth.uid() = id);

CREATE POLICY users_update_own ON users
  FOR UPDATE USING (auth.uid() = id) WITH CHECK (auth.uid() = id);

-- ----------------------------------------------------------
-- health_records (INSERT/SELECT만, 측정 기록 보존)
-- ----------------------------------------------------------
CREATE POLICY hr_insert_own ON health_records
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY hr_select_own ON health_records
  FOR SELECT USING (auth.uid() = user_id);

-- ----------------------------------------------------------
-- running_sessions (4 CRUD 모두)
-- ----------------------------------------------------------
CREATE POLICY rs_insert_own ON running_sessions
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY rs_select_own ON running_sessions
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY rs_update_own ON running_sessions
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY rs_delete_own ON running_sessions
  FOR DELETE USING (auth.uid() = user_id);

-- ----------------------------------------------------------
-- splits (간접 own - running_sessions 통한 EXISTS)
-- INSERT/SELECT/DELETE만 (UPDATE 없음 - 구간 데이터 보존)
-- ----------------------------------------------------------
CREATE POLICY sp_insert_own ON splits
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM running_sessions rs
      WHERE rs.id = splits.session_id
        AND rs.user_id = auth.uid()
    )
  );

CREATE POLICY sp_select_own ON splits
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM running_sessions rs
      WHERE rs.id = splits.session_id
        AND rs.user_id = auth.uid()
    )
  );

CREATE POLICY sp_delete_own ON splits
  FOR DELETE USING (
    EXISTS (
      SELECT 1 FROM running_sessions rs
      WHERE rs.id = splits.session_id
        AND rs.user_id = auth.uid()
    )
  );

-- ----------------------------------------------------------
-- session_metrics (간접 own)
-- INSERT/SELECT/UPDATE만 (DELETE 없음 - 계산 결과 보존)
-- ----------------------------------------------------------
CREATE POLICY sm_insert_own ON session_metrics
  FOR INSERT WITH CHECK (
    EXISTS (
      SELECT 1 FROM running_sessions rs
      WHERE rs.id = session_metrics.session_id
        AND rs.user_id = auth.uid()
    )
  );

CREATE POLICY sm_select_own ON session_metrics
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM running_sessions rs
      WHERE rs.id = session_metrics.session_id
        AND rs.user_id = auth.uid()
    )
  );

CREATE POLICY sm_update_own ON session_metrics
  FOR UPDATE USING (
    EXISTS (
      SELECT 1 FROM running_sessions rs
      WHERE rs.id = session_metrics.session_id
        AND rs.user_id = auth.uid()
    )
  );

-- ----------------------------------------------------------
-- health_metrics (D-037 Q-019 신규 추가 - health_records 패턴 동일)
-- INSERT/SELECT만 (측정 기록 보존)
-- ----------------------------------------------------------
CREATE POLICY hm_insert_own ON health_metrics
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY hm_select_own ON health_metrics
  FOR SELECT USING (auth.uid() = user_id);

-- ----------------------------------------------------------
-- ai_conversations (4 CRUD 모두)
-- ----------------------------------------------------------
CREATE POLICY ac_insert_own ON ai_conversations
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY ac_select_own ON ai_conversations
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY ac_update_own ON ai_conversations
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

CREATE POLICY ac_delete_own ON ai_conversations
  FOR DELETE USING (auth.uid() = user_id);

-- ----------------------------------------------------------
-- ai_feedbacks (INSERT/SELECT/UPDATE만, DELETE 차단)
-- ----------------------------------------------------------
CREATE POLICY af_insert_own ON ai_feedbacks
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY af_select_own ON ai_feedbacks
  FOR SELECT USING (auth.uid() = user_id);

CREATE POLICY af_update_own ON ai_feedbacks
  FOR UPDATE USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- ----------------------------------------------------------
-- ai_coaching_logs (INSERT/SELECT만, 로그 보존)
-- ----------------------------------------------------------
CREATE POLICY acl_insert_own ON ai_coaching_logs
  FOR INSERT WITH CHECK (auth.uid() = user_id);

CREATE POLICY acl_select_own ON ai_coaching_logs
  FOR SELECT USING (auth.uid() = user_id);

-- ============================================================
-- INDEX 정의
-- ============================================================
-- 5/9 D-037 Q-021 채택 (옵션 A+, 11만명 시나리오 검증)
-- - 기본 7개 (Mumbai 기존)
-- - 신규 7개 (D-037 Q-021)
-- 총 14개 (PK/UNIQUE 자동 인덱스 제외)

-- ----------------------------------------------------------
-- 기존 INDEX (Mumbai 운영 중, 그대로 유지)
-- ----------------------------------------------------------

-- ai_coaching_logs
CREATE INDEX idx_ai_logs_session 
  ON ai_coaching_logs (session_id);

CREATE INDEX idx_ai_logs_user 
  ON ai_coaching_logs (user_id, created_at DESC);

-- ai_feedbacks
CREATE INDEX idx_ai_feedbacks_session 
  ON ai_feedbacks (session_id);

CREATE INDEX idx_ai_feedbacks_user 
  ON ai_feedbacks (user_id);

-- health_records
CREATE INDEX idx_health_records_user_date 
  ON health_records (user_id, measured_at DESC);

-- session_metrics
CREATE INDEX idx_session_metrics_session 
  ON session_metrics (session_id);

-- splits
CREATE INDEX idx_splits_session 
  ON splits (session_id, split_number);

-- ----------------------------------------------------------
-- 신규 INDEX (D-037 Q-021 옵션 A+, 11만명 확장 대비)
-- ----------------------------------------------------------

-- ai_conversations (5/9 발견 7: 누락 해소)
CREATE INDEX idx_ai_conversations_user_date 
  ON ai_conversations (user_id, created_at DESC);

CREATE INDEX idx_ai_conversations_session 
  ON ai_conversations (session_id);

-- health_metrics (5/9 발견 7: 누락 해소)
CREATE INDEX idx_health_metrics_user_date 
  ON health_metrics (user_id, measured_date DESC);

-- running_sessions (5/9 발견 7: user_id INDEX 누락 해소)
CREATE INDEX idx_running_sessions_user_date 
  ON running_sessions (user_id, run_date DESC);

-- 확장 대비 3개
CREATE INDEX idx_users_subscription_tier 
  ON users (subscription_tier);

CREATE INDEX idx_ai_feedbacks_created_at 
  ON ai_feedbacks (created_at);

CREATE INDEX idx_running_sessions_run_date 
  ON running_sessions (run_date);

-- ============================================================
-- END OF master_schema.sql
-- ============================================================
-- 작성 완료: 2026-05-09 (KST)
-- 다음 작업: D-034 Seoul 이전 시 이 파일 적용
-- 검증 필요:
-- - Mumbai와 컬럼 순서/타입 정확성 대조
-- - Q-023 (익명 통계 인프라) 결정 후 추가 테이블 정의
-- - splits_data 마이그레이션 (Replit 코드 검토 후)
-- ============================================================
-- v2 추가 (2026-05-12): Auth ↔ public.users 동기화 트리거
-- D-039 Q-024 옵션 A 채택
-- 근거: 5/11 grep으로 ARCC 코드 public.users 직접 INSERT 안 함 확인
-- ============================================================

-- 함수: auth.users에 새 row 생기면 public.users에도 같은 id로 동기화
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger AS $$
BEGIN
  INSERT INTO public.users (id, email)
  VALUES (NEW.id, NEW.email);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 트리거: auth.users INSERT 후 매 row마다 함수 실행
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW
  EXECUTE FUNCTION public.handle_new_user();

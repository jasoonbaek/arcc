# Mumbai Schema 추출 원본 (2026-05-09)

**목적**: master_schema.sql 작성을 위한 원본 자료  
**추출 시점**: 2026-05-09 KST 17:30~18:00  
**추출 방법**: Supabase Dashboard SQL Editor + information_schema 메타 쿼리  
**관련 결정**: D-035 (schema 진실 복원)

---

## ⚠️ 이 파일의 위치

- **이 파일**: 5/9 추출 *원본 데이터* (가공 전)
- **목표 파일**: `docs/master_schema.sql` (다음 세션 작성)
- **활용 방법**: 다음 세션에서 이 파일 + 의미 주석 + 정렬 → master_schema.sql

---

## 1. 컬럼 정의 (CREATE TABLE 자동 생성)

### ⚠️ 주의사항
- 자동 생성된 SQL이라 PK, FK, INDEX, CHECK 제약 *미포함*
- 컬럼 순서가 *논리적 순서가 아님* (DB 내부 순서)
- master_schema.sql 작성 시 컬럼 *재정렬 필요*

### 1-1. ai_coaching_logs

```sql
CREATE TABLE ai_coaching_logs (
  id BIGINT NOT NULL DEFAULT nextval('ai_coaching_logs_id_seq'::regclass),
  user_id UUID,
  session_id UUID,
  api_duration_ms INTEGER,
  input_tokens INTEGER,
  output_tokens INTEGER,
  retry_count INTEGER DEFAULT 0,
  quality_score INTEGER,
  harness0_passed BOOLEAN,
  harness1_passed BOOLEAN,
  harness4_passed BOOLEAN,
  harness5_passed BOOLEAN,
  context_full TEXT,
  is_sample BOOLEAN DEFAULT false,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### 1-2. ai_conversations ⚠️ schema.sql에 누락

```sql
CREATE TABLE ai_conversations (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  user_id UUID,
  session_id UUID,
  request_data JSONB,
  ai_response TEXT,
  analysis_type TEXT,
  created_at TIMESTAMP DEFAULT now()
);
```

### 1-3. ai_feedbacks

```sql
CREATE TABLE ai_feedbacks (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  session_id UUID,
  feedback_type TEXT DEFAULT 'session'::text,
  feedback_data JSONB,
  full_response JSONB,
  summary TEXT,
  strengths JSONB,
  improvements JSONB,
  next_training JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### 1-4. health_metrics ⚠️ schema.sql에 누락

```sql
CREATE TABLE health_metrics (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  user_id UUID,
  measured_date DATE NOT NULL,
  weight DECIMAL(5,2),
  body_fat_rate DECIMAL(5,2),
  skeletal_muscle DECIMAL(5,2),
  blood_pressure_sys INTEGER,
  blood_pressure_dia INTEGER,
  visceral_fat INTEGER,
  inbody_score INTEGER,
  created_at TIMESTAMP DEFAULT now()
);
```

### 1-5. health_records

```sql
CREATE TABLE health_records (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  user_id UUID,
  measured_at DATE DEFAULT CURRENT_DATE,
  resting_hr INTEGER,
  weight DECIMAL(5,1),
  height DECIMAL(5,1),
  bmi DECIMAL(5,1),
  bmr INTEGER,
  bp_systolic INTEGER,
  bp_diastolic INTEGER,
  skeletal_muscle DECIMAL(5,1),
  body_fat_pct DECIMAL(5,1),
  visceral_fat INTEGER,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### 1-6. running_sessions

```sql
CREATE TABLE running_sessions (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  user_id UUID,
  run_date DATE,
  distance DECIMAL(6,2),
  duration INTEGER,
  calories INTEGER,
  avg_pace TEXT,
  avg_hr INTEGER,
  max_hr INTEGER,
  avg_cadence INTEGER,
  avg_stride INTEGER,
  elevation_gain INTEGER,
  elevation_loss INTEGER,
  csv_data JSONB,
  splits_data JSONB,
  is_sample BOOLEAN DEFAULT false,
  created_at TIMESTAMP DEFAULT now()
);
```

### 1-7. session_metrics

```sql
CREATE TABLE session_metrics (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  session_id UUID,
  lrs INTEGER,
  fi INTEGER,
  ti VARCHAR(20),
  calculated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### 1-8. splits

```sql
CREATE TABLE splits (
  id BIGINT NOT NULL DEFAULT nextval('splits_id_seq'::regclass),
  session_id UUID NOT NULL,
  split_number INTEGER NOT NULL,
  distance DECIMAL(6,2),
  time VARCHAR(10),
  pace VARCHAR(10),
  avg_hr INTEGER,
  max_hr INTEGER,
  cadence INTEGER,
  stride INTEGER,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
```

### 1-9. users

```sql
CREATE TABLE users (
  id UUID NOT NULL DEFAULT gen_random_uuid(),
  email TEXT NOT NULL,
  name TEXT,
  gender TEXT,
  birth_date DATE,
  height DECIMAL(5,2),
  weight DECIMAL(5,2),
  bmi DECIMAL(5,2),
  blood_pressure_sys INTEGER,
  blood_pressure_dia INTEGER,
  skeletal_muscle DECIMAL(5,2),
  body_fat_rate DECIMAL(5,2),
  visceral_fat INTEGER,
  max_hr INTEGER,
  injury_history TEXT,
  goal TEXT,
  goal_target_time INTEGER,
  weekly_runs INTEGER,
  run_duration INTEGER,
  subscription_tier VARCHAR(10) NOT NULL DEFAULT 'free'::character varying,
  disclaimer_agreed_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);
```

---

## 2. Primary Keys

| 테이블 | PK 컬럼 |
|---|---|
| ai_coaching_logs | id |
| ai_conversations | id |
| ai_feedbacks | id |
| health_metrics | id |
| health_records | id |
| running_sessions | id |
| session_metrics | id |
| splits | id |
| users | id (⚠️ 추출 시 "id, id" 중복 표시 — 다음 세션 재확인 필요) |

---

## 3. Foreign Keys

| 출발 테이블 | 출발 컬럼 | 도착 테이블 | 도착 컬럼 | ON DELETE |
|---|---|---|---|---|
| ai_coaching_logs | user_id | users | id | SET NULL |
| ai_coaching_logs | session_id | running_sessions | id | SET NULL |
| ai_conversations | user_id | users | id | NO ACTION |
| ai_conversations | session_id | running_sessions | id | NO ACTION |
| ai_feedbacks | user_id | users | id | CASCADE |
| ai_feedbacks | session_id | running_sessions | id | CASCADE |
| health_metrics | user_id | users | id | NO ACTION |
| health_records | user_id | users | id | CASCADE |
| running_sessions | user_id | users | id | NO ACTION |
| session_metrics | session_id | running_sessions | id | CASCADE |
| splits | session_id | running_sessions | id | CASCADE |

⚠️ **ON DELETE 비일관성 → D-036 (Q-018) 결정 필요**

---

## 4. UNIQUE Constraints

| 테이블 | UNIQUE 컬럼 |
|---|---|
| splits | (session_id, split_number) — 복합 |
| users | email |

---

## 5. 추출 시 미포함 항목 (다음 세션 추가 추출 필요)

- [ ] CHECK 제약 (예: schema.sql의 `gender CHECK (...)`)
- [ ] INDEX 정보 (idx_health_records_user_date 등)
- [ ] CASCADE 외 옵션 (ON UPDATE)
- [ ] DEFAULT 표현식 정확한 문자열
- [ ] 시퀀스 정의 (ai_coaching_logs_id_seq, splits_id_seq)
- [ ] 트리거 (있다면)
- [ ] RLS (Row Level Security) 정책 (Supabase 핵심 기능)

⚠️ **RLS는 특히 중요**. Supabase의 보안 정책. 추가 추출 쿼리 필요.

---

## 6. 컬럼 의미 주석 작성 가이드 (다음 세션)

master_schema.sql 작성 시 각 컬럼에 *주석* 추가. 메모리 활용:

### 핵심 도메인 용어 (메모리 박제됨)
- `LRS` (러닝리듬 안정도)
- `FI` (피로도 지수)
- `TI` (훈련 강도): low/moderate/high/very_high
- `inbody_score` → "체성분 측정 점수"로 통칭 (특허 전략, 메모리 박제됨)

### 5/9 발견 컬럼 (의미 추적 필요)
- `subscription_tier`: B2C 구독 티어 ('free', 'pro' 등?). 5/2 결정과 관련. 추적 필요
- `csv_data` JSONB: 원본 CSV 보존
- `splits_data` JSONB: 구간 데이터 JSON (splits 테이블과 *이중 저장*. 정책 결정 필요)
- `disclaimer_agreed_at`: 의료 면책 동의 시점 (medical_disclaimers 테이블 대체)
- `feedback_type`: 'session'/'weekly'/'monthly' 추정 (ai_feedbacks)
- `harness0~5_passed`: AI 응답 품질 검증 통과 여부 (D-022 Level 1+2+3과 관련 추정)

---

## 7. master_schema.sql 작성 체크리스트 (다음 세션)

- [ ] 컬럼 *논리적 순서*로 재정렬 (id → 핵심 → 메타 → 시간)
- [ ] PK 명시 추가
- [ ] FK 명시 추가 + ON DELETE 정책 *결정 후* 통일
- [ ] UNIQUE 제약 추가
- [ ] CHECK 제약 추가 (gender 등)
- [ ] INDEX 정의 추가
- [ ] 시퀀스 명시
- [ ] 컬럼 의미 주석 추가
- [ ] 헤더 주석 (작성일, 출처, 버전)
- [ ] RLS 정책 별도 섹션 (또는 별도 파일)

---

## 8. 다음 세션 작업 흐름 (예상)
---

## 9. RLS (Row Level Security) — 5/9 19:35 추출

### 9-1. RLS 활성화 상태

✅ **9개 테이블 모두 RLS 활성화** (rowsecurity = true)
- ai_coaching_logs, ai_conversations, ai_feedbacks, health_metrics, health_records,
  running_sessions, session_metrics, splits, users

### 9-2. RLS 정책 23건

#### 패턴 1: 단순 own (auth.uid() = user_id)

| 테이블 | 정책 (CRUD) | 비고 |
|---|---|---|
| ai_coaching_logs | I, S | DELETE/UPDATE 없음 (로그 보존 의도) |
| ai_conversations | I, S, U, D | 4개 모두 |
| ai_feedbacks | I, S, U | DELETE 없음 (AI 응답 보존) |
| health_records | I, S | DELETE/UPDATE 없음 (측정 기록 보존) |
| running_sessions | I, S, U, D | 4개 모두 |
| users | S, U | INSERT는 Auth가 처리, DELETE 없음 |

(I=INSERT, S=SELECT, U=UPDATE, D=DELETE)

#### 패턴 2: 간접 own (running_sessions 통한 EXISTS)

session_id로 부모 테이블 거쳐 본인 확인:

```sql
EXISTS (
  SELECT 1 FROM running_sessions rs
  WHERE rs.id = [child].session_id
    AND rs.user_id = auth.uid()
)
```

- session_metrics: I, S, U (DELETE 없음)
- splits: I, S, D (UPDATE 없음)

### 9-3. 🚨 발견 1: health_metrics RLS 정책 *완전 누락*

**상태**: RLS 활성화 + 정책 0건  
**결과**: 모든 접근 거부 (사용 불가)  
**증거**: 데이터 0행  
**영향**: 5/2 결정의 "체성분 측정 데이터" 활용 불가능 상태  
**조치**: master_schema.sql 작성 시 RLS 정책 추가  
**우선순위**: 🔴 높음

---

## 10. CHECK 제약 — 5/9 19:35 추출

### 10-1. NOT NULL 자동 제약

NOT NULL 컬럼 (자동 생성, master_schema에서는 컬럼 정의에 통합):
- ai_coaching_logs.id, ai_conversations.id
- ai_feedbacks.id, ai_feedbacks.user_id
- health_metrics.id, health_metrics.measured_date
- health_records.id, running_sessions.id
- session_metrics.id, splits.id, splits.session_id, splits.split_number
- users.id, users.email, users.subscription_tier

### 10-2. 🆕 발견 5: subscription_tier 3단계 확정

```sql
CHECK ((subscription_tier)::text = ANY (ARRAY['free', 'plus', 'pro']))
```

→ **B2C 구독 모델 3단계 확정**:
- `free` (무료)
- `plus` (중간)
- `pro` (최고)

5/2 메모리 추정 "월 9,900원"은 *어느 티어인지* 추적 필요. 다음 세션 결정 또는 별도 트랙.

### 10-3. ⚠️ 발견 6: gender CHECK 제약 *부재*

- schema.sql 정의: `gender CHECK (gender IN ('male', 'female'))`
- Mumbai 실제: 자유 텍스트 (제약 없음)

→ master_schema.sql 작성 시 결정 필요:
- 옵션 A: 제약 추가 ('male', 'female', 'other' 등)
- 옵션 B: 자유 텍스트 유지

---

## 11. 시퀀스 — 5/9 19:35 추출

| 시퀀스 | 데이터 타입 | 시작값 | 증가값 |
|---|---|---|---|
| ai_coaching_logs_id_seq | bigint | 1 | 1 |
| splits_id_seq | bigint | 1 | 1 |

→ **Q-012 해결 단서**: splits.id, ai_coaching_logs.id = BIGINT 시퀀스로 정상 운영 중.

---

## 12. INDEX — 5/9 19:50 추출

### 12-1. 총 INDEX 18개

#### Primary Key 인덱스 (자동, 9개)
- 모든 테이블의 *_pkey 인덱스 (id 컬럼 UNIQUE)

#### UNIQUE 제약 인덱스 (자동, 2개)
- `splits_session_id_split_number_key`: (session_id, split_number)
- `users_email_key`: email

#### 사용자 정의 INDEX (성능 최적화, 7개)

| 인덱스 | 테이블 | 컬럼 | 용도 |
|---|---|---|---|
| idx_ai_logs_session | ai_coaching_logs | session_id | 세션별 로그 조회 |
| idx_ai_logs_user | ai_coaching_logs | (user_id, created_at DESC) | 사용자별 최신 로그 |
| idx_ai_feedbacks_session | ai_feedbacks | session_id | 세션별 피드백 |
| idx_ai_feedbacks_user | ai_feedbacks | user_id | 사용자별 피드백 |
| idx_health_records_user_date | health_records | (user_id, measured_at DESC) | 사용자별 최신 측정 |
| idx_session_metrics_session | session_metrics | session_id | 세션별 지표 |
| idx_splits_session | splits | (session_id, split_number) | 구간 정렬 조회 |

### 12-2. 🚨 발견 7: INDEX 누락 패턴

**INDEX 없는 테이블/컬럼 (성능 영향 가능)**:

- ❌ **ai_conversations**: PK만 있음. user_id, session_id INDEX 없음
- ❌ **health_metrics**: PK만 있음 (RLS도 누락)
- ❌ **running_sessions.user_id**: 사용자별 세션 조회 시 풀스캔 위험

→ master_schema.sql 작성 시 INDEX 추가 결정 필요.

---

## 13. 5/9 추가 발견 자산 (Step B 결과)

| # | 발견 | 영향 | 우선순위 |
|---|---|---|---|
| 1 | health_metrics RLS 정책 누락 | 사용 불가 상태 | 🔴 높음 |
| 2 | ai_coaching_logs UPDATE/DELETE 차단 | 의도적 추정 | 🟢 정상 |
| 3 | health_records UPDATE/DELETE 차단 | 의도적 추정 | 🟢 정상 |
| 4 | ai_feedbacks DELETE 차단 | 의도적 추정 | 🟢 정상 |
| 5 | subscription_tier 3단계 (free/plus/pro) | B2C 비즈니스 결정 | 🟡 박제 가치 |
| 6 | gender CHECK 제약 부재 | 정책 결정 필요 | 🟡 master_schema 작성 시 |
| 7 | INDEX 누락 (ai_conversations, health_metrics, running_sessions.user_id) | 성능 영향 | 🟡 master_schema 작성 시 |

---

## 14. 7번 체크리스트 갱신 (5/9 19:50)

- [x] CHECK 제약 추출 완료
- [x] INDEX 추출 완료
- [x] 시퀀스 정의 추출 완료
- [x] RLS 정책 추출 완료
- [ ] DEFAULT 표현식 정확한 문자열 — 다음 세션
- [ ] 트리거 (있다면) — 다음 세션
- [ ] FK ON UPDATE 옵션 — 다음 세션
- [ ] PRIMARY KEY users.id 중복 표시 재확인 — 다음 세션

"""하네스 1: 입력 범위 검증"""
import re
from datetime import datetime


class ValidationError(Exception):
    pass


def _extract_date_from_filename(filename):
    """파일명에서 YYYYMMDD 패턴 추출 → 'YYYY-MM-DD' 문자열 또는 None.

    - '서울특별시_러닝20260418061107.csv' → '2026-04-18'
    - '20260418_run.csv' → '2026-04-18'
    - 'my_running.csv' → None (호출부에서 오늘 날짜로 폴백)
    - 'test20301231.csv' → None (미래 날짜 안전장치)
    - 'run20269999.csv' → None (유효하지 않은 날짜)
    """
    if not filename:
        return None

    # 20으로 시작하는 8자리 숫자 (2020~2099년)
    match = re.search(r'(20\d{6})', filename)
    if not match:
        return None

    date_str = match.group(1)
    try:
        year = int(date_str[:4])
        month = int(date_str[4:6])
        day = int(date_str[6:8])
        date_obj = datetime(year, month, day)
        # 미래 날짜 방지
        if date_obj.date() > datetime.now().date():
            return None
        return date_obj.strftime('%Y-%m-%d')
    except (ValueError, IndexError):
        return None


def pace_to_sec(pace_str):
    """페이스 문자열을 초 단위로 변환"""
    parts = pace_str.strip().split(':')
    parts = [int(p) for p in parts if p]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def time_to_sec(time_str):
    """시간 문자열을 초 단위로 변환"""
    parts = time_str.strip().split(':')
    parts = [int(p) for p in parts if p]
    if len(parts) == 3:
        return parts[0] * 3600 + parts[1] * 60 + parts[2]
    if len(parts) == 2:
        return parts[0] * 60 + parts[1]
    return 0


def fmt_pace(sec):
    """초를 MM:SS 형식으로"""
    m = int(sec // 60)
    s = int(sec % 60)
    return f'{m}:{s:02d}'


def validate(parsed, filename=None):
    """파싱된 CSV 데이터의 값 범위 검증 (+ 파일명에서 세션 날짜 추출)"""
    rows = parsed['rows']

    # Separate summary and splits
    summary_row = None
    split_rows = []
    for row in rows:
        split_val = row.get('Split', '').lower()
        if 'summary' in split_val or 'total' in split_val:
            summary_row = row
        else:
            split_rows.append(row)

    if not split_rows:
        raise ValidationError('구간 데이터가 없습니다')

    # Validate and extract summary
    src = summary_row or split_rows[-1]
    distance = _parse_float(src.get('GetDistance', '0'))
    pace_str = src.get('Avg Pace') or src.get('Avg Moving Pace', '0:00')
    time_str = src.get('Time') or src.get('Moving Time', '0:00:00')
    avg_hr = _parse_int(src.get('Avg HR', '0'))
    max_hr = _parse_int(src.get('Max HR', '0'))
    avg_cadence_raw = _parse_int(src.get('Avg Run Cadence', '0'))
    # COROS CSV는 한발 기준 케이던스 → ×2로 양발 변환
    avg_cadence = avg_cadence_raw * 2 if avg_cadence_raw > 0 else 0
    avg_stride = _parse_int(src.get('Avg Stride Length', '0'))
    calories = _parse_int(src.get('Calories', '0'))
    duration_sec = time_to_sec(time_str)
    pace_sec = pace_to_sec(pace_str)

    # Range validation
    errors = []
    if distance < 0.5 or distance > 100:
        errors.append(f'거리가 범위를 벗어났습니다: {distance}km (0.5~100km)')
    if duration_sec < 60 or duration_sec > 86400:
        errors.append(f'시간이 범위를 벗어났습니다 (1분~24시간)')
    if pace_sec > 0 and (pace_sec < 120 or pace_sec > 900):
        errors.append(f'페이스가 범위를 벗어났습니다 (2:00~15:00/km)')
    if avg_hr > 0 and (avg_hr < 40 or avg_hr > 220):
        errors.append(f'심박수가 범위를 벗어났습니다: {avg_hr}bpm (40~220bpm)')
    if avg_cadence > 0 and (avg_cadence < 100 or avg_cadence > 250):
        errors.append(f'케이던스가 범위를 벗어났습니다: {avg_cadence}spm (100~250spm, 양발 기준)')

    if errors:
        raise ValidationError('; '.join(errors))

    # Extract splits data
    splits = []
    for row in split_rows:
        sp_pace = row.get('Avg Pace') or row.get('Avg Moving Pace', '0:00')
        splits.append({
            'split_number': row.get('Split', ''),
            'distance': _parse_float(row.get('GetDistance', '0')),
            'time': row.get('Time') or row.get('Moving Time', '0:00'),
            'pace': fmt_pace(pace_to_sec(sp_pace)) if sp_pace else '0:00',
            'avg_hr': _parse_int(row.get('Avg HR', '0')),
            'max_hr': _parse_int(row.get('Max HR', '0')),
            'cadence': _parse_int(row.get('Avg Run Cadence', '0')) * 2,  # COROS 한발→양발
            'stride': _parse_int(row.get('Avg Stride Length', '0'))
        })

    return {
        'summary': {
            'distance': distance,
            'duration_sec': duration_sec,
            'calories': calories,
            'avg_pace': fmt_pace(pace_sec),
            'avg_hr': avg_hr,
            'max_hr': max_hr,
            'avg_cadence': avg_cadence,
            'avg_stride': avg_stride
        },
        'splits': splits,
        'date': _extract_date_from_filename(filename)
    }


def _parse_float(val):
    try:
        return float(val.replace(',', ''))
    except (ValueError, AttributeError):
        return 0.0


def _parse_int(val):
    try:
        return int(float(val.replace(',', '')))
    except (ValueError, AttributeError):
        return 0

"""하네스 0: CSV 파싱 검증"""
import csv
import io


class CSVError(Exception):
    pass


REQUIRED_COLUMNS = ['Split', 'Time', 'GetDistance', 'Avg Pace', 'Avg HR', 'Max HR', 'Avg Run Cadence']
OPTIONAL_COLUMNS = ['Avg Stride Length', 'Calories', 'Avg Moving Pace', 'Moving Time']
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate(csv_text):
    """CSV 텍스트를 파싱하고 검증"""
    # Size check
    if len(csv_text.encode('utf-8')) > MAX_FILE_SIZE:
        raise CSVError('파일 크기가 10MB를 초과합니다')

    if not csv_text.strip():
        raise CSVError('빈 파일입니다')

    # Parse CSV
    try:
        reader = csv.DictReader(io.StringIO(csv_text))
        headers = reader.fieldnames

        if not headers:
            raise CSVError('CSV 헤더를 찾을 수 없습니다')

        # Clean headers (remove BOM, quotes, whitespace)
        headers = [h.strip().replace('"', '').replace('\ufeff', '') for h in headers]

        # Check required columns
        missing = []
        for col in REQUIRED_COLUMNS:
            # Try alternate column names
            if col not in headers:
                if col == 'Avg Pace' and 'Avg Moving Pace' in headers:
                    continue
                if col == 'Time' and 'Moving Time' in headers:
                    continue
                missing.append(col)

        if missing:
            raise CSVError(f'필수 컬럼이 없습니다: {", ".join(missing)}')

        # Parse rows
        rows = []
        for row in reader:
            # Clean row keys
            clean_row = {}
            for k, v in row.items():
                clean_key = k.strip().replace('"', '').replace('\ufeff', '')
                clean_row[clean_key] = v.strip().replace('"', '') if v else ''
            rows.append(clean_row)

        if not rows:
            raise CSVError('데이터가 없습니다')

        return {'headers': headers, 'rows': rows}

    except csv.Error as e:
        raise CSVError(f'CSV 파싱 오류: {e}')

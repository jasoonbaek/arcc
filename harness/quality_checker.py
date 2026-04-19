"""하네스 5: 품질 검증"""
import json
import re


class QualityError(Exception):
    pass


REQUIRED_FIELDS = ['summary', 'strengths', 'next_training']


def check(ai_result):
    """AI 응답 품질 검증"""
    if not isinstance(ai_result, dict):
        raise QualityError('응답이 JSON 객체가 아닙니다')

    # Required fields check
    missing = [f for f in REQUIRED_FIELDS if f not in ai_result]
    if missing:
        raise QualityError(f'필수 필드 누락: {", ".join(missing)}')

    # Text length check (200~2000 chars total)
    total_text = json.dumps(ai_result, ensure_ascii=False)
    text_len = len(total_text)
    if text_len < 100:
        raise QualityError(f'응답이 너무 짧습니다: {text_len}자')
    if text_len > 5000:
        raise QualityError(f'응답이 너무 깁니다: {text_len}자')

    # Korean ratio check (50% 이상)
    korean_chars = len(re.findall(r'[가-힣]', total_text))
    alpha_chars = len(re.findall(r'[a-zA-Z가-힣]', total_text))
    if alpha_chars > 0:
        korean_ratio = korean_chars / alpha_chars
        if korean_ratio < 0.4:
            raise QualityError(f'한국어 비율이 낮습니다: {korean_ratio:.0%}')

    # Quality score (0~100)
    score = 100
    if not ai_result.get('analysis'):
        score -= 10
    if not isinstance(ai_result.get('strengths'), list) or len(ai_result.get('strengths', [])) < 1:
        score -= 15
    if not isinstance(ai_result.get('improvements'), list) or len(ai_result.get('improvements', [])) < 1:
        score -= 15
    if not ai_result.get('next_training'):
        score -= 20

    return {'score': max(0, score), 'result': ai_result}

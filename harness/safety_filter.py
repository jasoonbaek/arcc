"""하네스 4: 출력 안전성 검증"""


class SafetyError(Exception):
    pass


# 의료 진단/처방 관련 금지 키워드
BANNED_MEDICAL = [
    '진단', '처방', '약을', '약물', '수술', '치료제',
    '병원에 가', '의사에게', '전문의',
    '골절', '인대 파열', '연골 손상',
    '항염증제', '진통제', '스테로이드',
    'MRI', 'CT', 'X-ray',
]

# 위험한 조언 키워드
DANGEROUS_ADVICE = [
    '통증을 무시', '아파도 계속', '참고 달려',
    '무리해서', '극한까지', '한계를 넘어',
    '탈수 상태에서', '공복에 전력',
    '매일 전력 질주', '휴식 없이',
]


def check(ai_result):
    """AI 응답의 안전성 검증"""
    if not isinstance(ai_result, dict):
        raise SafetyError('AI 응답 형식이 올바르지 않습니다')

    # Collect all text from response
    texts = []
    for key, val in ai_result.items():
        if isinstance(val, str):
            texts.append(val)
        elif isinstance(val, list):
            texts.extend(str(v) for v in val)
        elif isinstance(val, dict):
            texts.extend(str(v) for v in val.values())

    full_text = ' '.join(texts)

    # Check banned medical terms
    for keyword in BANNED_MEDICAL:
        if keyword in full_text:
            raise SafetyError(f'의료 관련 부적절한 내용 감지: {keyword}')

    # Check dangerous advice
    for keyword in DANGEROUS_ADVICE:
        if keyword in full_text:
            raise SafetyError(f'위험한 조언 감지: {keyword}')

    return ai_result

# 크레파스풍 사진 변환기

사진을 올리면 허깅페이스의 이미지 편집 모델(image-to-image)이 크레파스 그림처럼 바꿔 주는 Streamlit 앱입니다. 모델은 Inference Providers API로 호출하므로 GPU가 없어도 됩니다.

## 흐름

1. 사진 업로드 (올리면 바로 미리보기가 나옵니다)
2. 사이드바에서 스타일, 변환 강도, 모델 선택
3. 선택한 내용을 영어 지시문으로 자동 변환 (이미지 편집 모델은 영어 지시문에 강함)
4. `InferenceClient.image_to_image` 호출
5. 원본과 결과를 `records/`에 JPG로, 사용한 설정과 지시문은 `records/records.csv`에 저장
6. 원본/결과 비교, 갤러리에서 확인하고 내려받기

## 설정

| 항목 | 선택지 |
|---|---|
| 스타일 | 크레파스 / 오일 파스텔 / 색연필 / 수채화 |
| 변환 강도 | 약 / 중 / 강 (편집 모델은 숫자 강도가 없어 지시문의 세기로 조절) |
| 모델 | 아래 표 |
| 추가 요청 | 영어로 자유 입력 (예: `pastel colors, thicker outlines`) |

지시문에는 항상 다음 내용이 들어갑니다: 원본 구도와 색감 유지, 버튼·아이콘·글자 같은 화면 요소는 그리지 않기, 매끄러운 그라데이션과 사진 느낌 피하기.

## 모델

`app.py`의 `MODELS` 목록에서 고르며, 첫 번째가 기본값입니다.

| 모델 | 비고 |
|---|---|
| `black-forest-labs/FLUX.2-klein-4B` | 작은 FLUX 계열 (기본값) |
| `Qwen/Qwen-Image-Edit-2509` | 지시형 이미지 편집 |

제공 업체와 사용 가능 여부는 수시로 바뀌므로, 호출이 안 되면 허깅페이스 모델 페이지의 Inference Providers 항목을 확인하세요. 모델마다 라이선스가 다르니 배포 전에 확인하세요.

## 실행

```bash
pip install -r requirements.txt
cp .env.example .env     # 윈도우 PowerShell: copy .env.example .env
streamlit run app.py
```

`.env`의 `HF_TOKEN`에 허깅페이스 토큰을 넣어야 합니다. 토큰 권한에서 **Inference Providers 호출**을 켜 주세요. 무료 크레딧을 다 쓰면 호출이 실패할 수 있습니다.

## 폴더 구조

```
app.py             # Streamlit 앱
requirements.txt
.env.example
records/           # 실행 후 생성: 원본·결과 JPG + records.csv (깃에 올라가지 않음)
```

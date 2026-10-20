"""크레파스풍 사진 변환기

사진을 올리면 허깅페이스의 이미지 편집 모델(image-to-image)이 크레파스 그림처럼 바꿔 준다.
모델은 Inference Providers API로 호출하므로 내 컴퓨터에 GPU가 없어도 된다.

실행: streamlit run app.py
"""
import io
import os
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from huggingface_hub import InferenceClient
from PIL import Image, ImageOps

load_dotenv()

# 왜: 모델 이름을 목록으로 두면 같은 사진으로 모델끼리 비교하기 쉽다. 첫 번째가 기본값.
MODELS = [
    "black-forest-labs/FLUX.2-klein-4B",
    "Qwen/Qwen-Image-Edit-2509",
]

RECORD_DIR = Path("records")
RECORDS_CSV = RECORD_DIR / "records.csv"
MAX_SIDE = 1024  # 왜: 큰 사진을 그대로 보내면 느리고 API 사용량만 늘어난다

# 화면에 보이는 이름 -> 프롬프트에 들어가는 영어 스타일 설명
# 왜: 이미지 편집 모델은 영어 지시문에 강하고, 한글 짧은 입력만으로는 스타일이 흐려진다
# 왜: 색감 유지가 목표라 "진한 색", "선명한 색" 같은 색을 건드리는 표현은 스타일 설명에서 뺐다
STYLES = {
    "크레파스": (
        "a cute hand-drawn crayon drawing on cream-colored textured paper. "
        "Every area, including the background, is filled with dense diagonal waxy crayon hatching strokes, "
        "and tiny specks of white paper show through between the strokes. "
        "The outlines are rough and hand-drawn, in a darker shade of each area's own color instead of black. "
        "3D shading, highlights and shadows are flattened into simple rounded shapes with soft crayon color layers"
    ),
    "오일 파스텔": (
        "an oil pastel drawing with soft blended waxy strokes, creamy texture and rough paper grain"
    ),
    "색연필": (
        "a colored pencil drawing with fine hatching lines, layered pencil shading and visible paper grain"
    ),
    "수채화": (
        "a watercolor painting with soft bleeding edges, light washes and visible paper texture"
    ),
}

# 왜: 편집 모델은 strength 같은 숫자 조절이 없어서, 변환 정도를 문장의 세기로 조절한다
INTENSITIES = {
    "약": "Keep most fine details of the photo and apply only a light hand-drawn texture.",
    "중": "Simplify fine details into visible hand-drawn strokes.",
    "강": (
        "Simplify heavily into bold, chunky strokes with strong texture, like a child's drawing. "
        "It must look clearly hand-drawn and not like a photo."
    ),
}


def build_prompt(style_desc, intensity, extra):
    """선택한 스타일과 강도, 추가 요청을 모델에 보낼 영어 지시문으로 만든다."""
    prompt = (
        f"Redraw this photo as {style_desc}. {INTENSITIES[intensity]} "
        "Keep the original composition, subjects and poses clearly recognizable. "
        "Ignore and remove any screen UI elements such as buttons, arrows, icons or text overlays; draw only the character and its surroundings. "
        "Preserve the original colors and the overall color mood of the photo; do not change its color palette. "
        "Avoid smooth gradients, photographic realism and digital airbrushing."
    )
    if extra.strip():
        prompt += f" Additional request: {extra.strip()}"
    return prompt


def load_photo(data):
    """EXIF 회전을 반영하고 긴 변을 MAX_SIDE로 줄인 RGB 이미지를 돌려준다."""
    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data))).convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    return image


def to_jpeg_bytes(image):
    buf = io.BytesIO()
    image.save(buf, "JPEG", quality=92)
    return buf.getvalue()


def convert(image, prompt, model):
    client = InferenceClient(provider="auto", api_key=os.getenv("HF_TOKEN"))
    result = client.image_to_image(to_jpeg_bytes(image), prompt=prompt, model=model)
    return result.convert("RGB")


def explain_error(error):
    """자주 만나는 API 오류를 한글 안내로 바꾼다."""
    text = str(error).lower()
    if "402" in text or "credit" in text or "payment" in text:
        return "무료 크레딧을 다 쓴 것 같아요. 허깅페이스 계정의 Inference Providers 사용량을 확인해 주세요."
    if "401" in text or "403" in text or "unauthorized" in text or "forbidden" in text:
        return "토큰 권한 문제예요. 토큰에 'Inference Providers 호출' 권한이 켜져 있는지 확인해 주세요."
    if "404" in text or "not supported" in text or "no provider" in text:
        return "이 모델을 지금 제공하는 업체가 없어요. 사이드바에서 다른 모델을 골라 보세요."
    return "변환에 실패했어요. 잠시 뒤에 다시 시도하거나 다른 모델을 골라 보세요."


def safe_stem(filename):
    stem = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(filename).stem).strip("_")
    return stem or "photo"


def save_record(original, result, filename, style, prompt, model):
    """원본과 결과를 JPG로 저장하고 CSV에 한 줄 추가한다."""
    # 왜: 이미지만으로는 어떤 설정으로 만들었는지 알 수 없어서 메타데이터를 같이 저장한다
    RECORD_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = f"{stamp}_{safe_stem(filename)}"
    original_path = RECORD_DIR / f"{base}_original.jpg"
    result_path = RECORD_DIR / f"{base}_result.jpg"
    original.save(original_path, "JPEG", quality=92)
    result.save(result_path, "JPEG", quality=92)

    row = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "file": filename,
        "style": style,
        "model": model,
        "prompt": prompt,
        "original_path": str(original_path),
        "result_path": str(result_path),
    }
    pd.DataFrame([row]).to_csv(
        RECORDS_CSV, mode="a", header=not RECORDS_CSV.exists(), index=False, encoding="utf-8"
    )
    return result_path


def show_gallery():
    if not RECORDS_CSV.exists():
        st.info("아직 변환한 사진이 없어요. 위에서 첫 사진을 변환해 보세요.")
        return
    df = pd.read_csv(RECORDS_CSV).iloc[::-1].reset_index(drop=True)
    st.caption(f"총 {len(df)}장 · 최신순")
    cols = st.columns(3)
    for i, row in df.head(12).iterrows():
        path = Path(row["result_path"])
        if not path.exists():
            continue
        with cols[i % 3]:
            st.image(str(path), caption=f"{row['style']} · {row['model'].split('/')[-1]}")
            st.download_button("내려받기", path.read_bytes(), path.name, "image/jpeg", key=f"dl_{i}")
    with st.expander("전체 기록 (CSV)"):
        st.dataframe(df.drop(columns=["original_path", "result_path"]), hide_index=True)
        st.download_button(
            "CSV 내려받기", df.to_csv(index=False).encode("utf-8-sig"), "records.csv", "text/csv"
        )


def main():
    st.set_page_config(page_title="크레파스풍 사진 변환기", page_icon="🖍️")
    st.title("🖍️ 크레파스풍 사진 변환기")
    st.caption("사진을 올리면 허깅페이스 이미지 편집 모델이 그림처럼 바꿔 줘요.")

    with st.sidebar:
        st.header("설정")
        style = st.selectbox("스타일", list(STYLES))
        intensity = st.select_slider("변환 강도", options=list(INTENSITIES), value="중")
        model = st.selectbox("모델", MODELS)
        extra = st.text_input("추가 요청 (영어, 선택)", placeholder="pastel colors, thicker outlines")

    if not os.getenv("HF_TOKEN"):
        st.error(".env 파일에 HF_TOKEN을 넣어 주세요. (.env.example 참고)")
        st.stop()

    uploaded = st.file_uploader("사진을 올려주세요", type=["jpg", "jpeg", "png", "webp"])
    if uploaded:
        original = load_photo(uploaded.getvalue())
        prompt = build_prompt(STYLES[style], intensity, extra)
        # 왜: 변환 결과 아래에 원본이 한 번 더 나오므로, 결과가 있는 사진은 미리보기를 생략한다
        preview = st.empty()
        if st.session_state.get("last", (None, None, None))[2] != uploaded.name:
            preview.image(original, caption="올린 사진")

        if st.button("변환하기", type="primary"):
            try:
                with st.spinner("그리는 중... (30초~1분 걸릴 수 있어요)"):
                    result = convert(original, prompt, model)
                # 왜: CSV 열을 늘리면 기존 기록 파일과 열이 어긋나서 강도는 스타일 칸에 같이 적는다
                save_record(original, result, uploaded.name, f"{style}/{intensity}", prompt, model)
                st.session_state["last"] = (original, result, uploaded.name)
                preview.empty()
            except Exception as e:  # API 오류는 종류가 다양해서 한 곳에서 안내한다
                st.error(explain_error(e))
                with st.expander("오류 내용"):
                    st.code(str(e)[:500], language=None)

    if "last" in st.session_state:
        original, result, name = st.session_state["last"]
        left, right = st.columns(2)
        left.image(original, caption="원본")
        right.image(result, caption="변환 결과")
        right.download_button("결과 내려받기", to_jpeg_bytes(result), f"crayon_{safe_stem(name)}.jpg", "image/jpeg")

    st.divider()
    st.subheader("갤러리")
    show_gallery()


main()

import json
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from streamlit_drawable_canvas import st_canvas

# ページ初期設定
st.set_page_config(
    page_title="路線価アノテーションツール", layout="wide", initial_sidebar_state="expanded"
)

# セッション状態の初期化
if "annotations" not in st.session_state:
    st.session_state.annotations = []
if "current_points" not in st.session_state:
    st.session_state.current_points = []
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "next_id" not in st.session_state:
    st.session_state.next_id = 1

st.title("📍 路線価アノテーションツール")

# サイドバー
st.sidebar.header("📁 ファイル操作 / 設定")
uploaded_image = st.sidebar.file_uploader(
    "1. 路線価図画像をアップロード", type=["png", "jpg", "jpeg"]
)
zoom_percent = st.sidebar.slider(
    "画像表示倍率 (%)", min_value=10, max_value=300, value=100, step=10
)
zoom_scale = zoom_percent / 100.0

st.sidebar.markdown("---")
uploaded_json = st.sidebar.file_uploader("2. 既存JSONを読み込み", type=["json"])
if uploaded_json is not None:
    if st.sidebar.button("JSONデータを読み込んで復元"):
        try:
            data = json.load(uploaded_json)
            loaded = data.get("annotations", [])
            st.session_state.annotations = loaded
            st.session_state.next_id = max([a.get("id", 0) for a in loaded], default=0) + 1
            st.sidebar.success(f"JSONをロードしました。（{len(loaded)}件）")
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"JSON読み込みエラー: {e}")

st.sidebar.markdown("---")

if uploaded_image is None:
    st.info("👈 左側のサイドバーから路線価図の画像ファイルをアップロードしてください。")
else:
    image_original = Image.open(uploaded_image).convert("RGB")
    orig_w, orig_h = image_original.size
    image_name = uploaded_image.name

    disp_w = int(orig_w * zoom_scale)
    disp_h = int(orig_h * zoom_scale)

    # 背景画像の作成
    canvas_bg_orig = image_original.copy()
    draw = ImageDraw.Draw(canvas_bg_orig)

    # 既存アノテーションの描画
    for ann in st.session_state.annotations:
        ann_id = ann["id"]
        pts = [tuple(p) for p in ann["polyline"]]
        is_editing = (st.session_state.editing_id == ann_id)
        line_color = (0, 100, 255) if is_editing else (255, 0, 0)
        width = 5 if is_editing else 4

        if len(pts) > 1:
            draw.line(pts, fill=line_color, width=width)
        for pt in pts:
            draw.ellipse([pt[0]-5, pt[1]-5, pt[0]+5, pt[1]+5], fill=line_color, outline=(255, 255, 255))
        if pts:
            draw.text((pts[0][0] + 8, pts[0][1] - 8), f"ID:{ann_id}", fill=(0, 0, 0))

    # 作成中の描画
    if st.session_state.current_points:
        curr_pts = [tuple(p) for p in st.session_state.current_points]
        if len(curr_pts) > 1:
            draw.line(curr_pts, fill=(0, 200, 0), width=4)
        for pt in curr_pts:
            draw.ellipse([pt[0]-6, pt[1]-6, pt[0]+6, pt[1]+6], fill=(0, 250, 0), outline=(0, 0, 0))

    canvas_bg_resized = canvas_bg_orig.resize((disp_w, disp_h), Image.Resampling.LANCZOS)

    col_canvas, col_form = st.columns([7, 5])

    with col_canvas:
        st.subheader("🖼️ 画像描画エリア")
        
        # keyを固定してキャンバスの読み込みエラーを防止
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",
            stroke_width=2,
            stroke_color="#000000",
            background_image=canvas_bg_resized,
            update_streamlit=True,
            height=disp_h,
            width=disp_w,
            drawing_mode="point",
            key="rosenka_canvas",
        )

        if canvas_result.json_data is not None and "objects" in canvas_result.json_data:
            objects = canvas_result.json_data["objects"]
            if len(objects) > 0:
                last_obj = objects[-1]
                click_x_disp = last_obj["left"]
                click_y_disp = last_obj["top"]
                orig_x = int(round(click_x_disp / zoom_scale))
                orig_y = int(round(click_y_disp / zoom_scale))

                if not st.session_state.current_points or st.session_state.current_points[-1] != [orig_x, orig_y]:
                    st.session_state.current_points.append([orig_x, orig_y])
                    st.rerun()

        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("↩️ 1つ戻す"):
                if st.session_state.current_points:
                    st.session_state.current_points.pop()
                    st.rerun()
        with c_btn2:
            if st.button("🗑️ すべてクリア"):
                st.session_state.current_points = []
                st.rerun()

        st.write(f"**現在のポリライン点数**: {len(st.session_state.current_points)} 点")

    with col_form:
        st.subheader("📝 アノテーション入力" if st.session_state.editing_id is None else f"✏️ 修正 (ID: {st.session_state.editing_id})")

        default_price = 0
        default_symbol = ""
        default_shape = "なし"
        default_l_pattern = "なし"
        default_r_pattern = "なし"

        if st.session_state.editing_id is not None:
            edit_item = next((a for a in st.session_state.annotations if a["id"] == st.session_state.editing_id), None)
            if edit_item:
                default_price = int(edit_item.get("land_price", 0))
                default_symbol = edit_item.get("symbol", "")
                mark = edit_item.get("mark", {})
                default_shape = mark.get("shape", "なし")
                default_l_pattern = mark.get("left_pattern", "なし")
                default_r_pattern = mark.get("right_pattern", "なし")

        with st.form("annotation_form"):
            land_price = st.number_input("路線価（必須・数値）", min_value=0, value=default_price, step=1000)
            symbol_raw = st.text_input("記号 (A～Gの1文字)", value=default_symbol, max_chars=1)
            
            shape_options = ["六角形", "楕円", "八角形", "正円", "縦に潰れたひし形", "横長の長方形", "なし"]
            shape = st.selectbox("マーク形状", shape_options, index=shape_options.index(default_shape) if default_shape in shape_options else 6)

            pattern_options = ["斜線", "黒塗り", "なし"]
            left_pattern = st.selectbox("左側模様", pattern_options, index=pattern_options.index(default_l_pattern) if default_l_pattern in pattern_options else 2)
            right_pattern = st.selectbox("右側模様", pattern_options, index=pattern_options.index(default_r_pattern) if default_r_pattern in pattern_options else 2)

            submitted = st.form_submit_button("登録" if st.session_state.editing_id is None else "修正を保存")

        if submitted:
            symbol = symbol_raw.strip().upper()
            if len(st.session_state.current_points) < 2:
                st.error("❌ ポリラインは2点以上指定してください。")
            elif land_price <= 0:
                st.error("❌ 路線価を入力してください。")
            elif symbol not in ["A", "B", "C", "D", "E", "F", "G"]:
                st.error("❌ 記号は A～G の1文字で入力してください。")
            else:
                pts = st.session_state.current_points
                data = {
                    "id": st.session_state.editing_id if st.session_state.editing_id is not None else st.session_state.next_id,
                    "start": pts[0],
                    "end": pts[-1],
                    "polyline": pts,
                    "land_price": land_price,
                    "symbol": symbol,
                    "mark": {"shape": shape, "left_pattern": left_pattern, "right_pattern": right_pattern}
                }
                if st.session_state.editing_id is not None:
                    idx = next(i for i, a in enumerate(st.session_state.annotations) if a["id"] == st.session_state.editing_id)
                    st.session_state.annotations[idx] = data
                    st.session_state.editing_id = None
                else:
                    st.session_state.annotations.append(data)
                    st.session_state.next_id += 1
                
                st.session_state.current_points = []
                st.rerun()

        if st.session_state.editing_id is not None:
            if st.button("❌ 修正をキャンセル"):
                st.session_state.editing_id = None
                st.session_state.current_points = []
                st.rerun()

        st.markdown("---")
        st.subheader(f"📋 登録済み（{len(st.session_state.annotations)}件）")
        with st.container(height=300, border=True):
            for ann in st.session_state.annotations:
                st.write(f"**ID {ann['id']}** | 路線価: {ann['land_price']} | 記号: {ann['symbol']}")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("✏️ 修正", key=f"edit_{ann['id']}"):
                        st.session_state.editing_id = ann["id"]
                        st.session_state.current_points = list(ann["polyline"])
                        st.rerun()
                with c2:
                    if st.button("🗑️ 削除", key=f"del_{ann['id']}"):
                        st.session_state.annotations = [a for a in st.session_state.annotations if a["id"] != ann["id"]]
                        st.rerun()

    # JSONダウンロード
    st.sidebar.markdown("---")
    output_json = {
        "image_name": image_name,
        "image_width": orig_w,
        "image_height": orig_h,
        "annotations": st.session_state.annotations,
    }
    st.sidebar.download_button(
        label="💾 JSON保存",
        data=json.dumps(output_json, ensure_ascii=False, indent=2),
        file_name="annotations.json",
        mime="application/json",
    )

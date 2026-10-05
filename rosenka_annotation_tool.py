import streamlit as st
import streamlit.components.v1 as components

import base64
import json
import os
from datetime import datetime
from pathlib import Path
from io import BytesIO

from PIL import Image


# =========================================================
# ページ設定
# =========================================================

st.set_page_config(
    page_title="路線価図アノテーションツール",
    layout="wide"
)


# =========================================================
# カスタムコンポーネント
# =========================================================

COMPONENT_DIR = Path(__file__).parent / "rosenka_viewer"

viewer_component = components.declare_component(
    "rosenka_viewer",
    path=str(COMPONENT_DIR)
)


# =========================================================
# Session State
# =========================================================

if "image_loaded" not in st.session_state:
    st.session_state.image_loaded = False

if "image_name" not in st.session_state:
    st.session_state.image_name = None

if "image_base64" not in st.session_state:
    st.session_state.image_base64 = None

if "image_width" not in st.session_state:
    st.session_state.image_width = 0

if "image_height" not in st.session_state:
    st.session_state.image_height = 0

if "annotations" not in st.session_state:
    st.session_state.annotations = []

if "current_points" not in st.session_state:
    st.session_state.current_points = []

if "zoom" not in st.session_state:
    st.session_state.zoom = 1.0

if "scroll_left" not in st.session_state:
    st.session_state.scroll_left = 0

if "scroll_top" not in st.session_state:
    st.session_state.scroll_top = 0


# =========================================================
# JSON保存
# =========================================================

def save_json():

    if not st.session_state.image_name:
        return

    os.makedirs("annotations", exist_ok=True)

    data = {
        "image": st.session_state.image_name,
        "image_width": st.session_state.image_width,
        "image_height": st.session_state.image_height,
        "annotations": st.session_state.annotations
    }

    stem = Path(
        st.session_state.image_name
    ).stem

    save_path = (
        Path("annotations")
        / f"{stem}_annotations.json"
    )

    with open(
        save_path,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# =========================================================
# タイトル
# =========================================================

st.title("路線価図アノテーションツール")


# =========================================================
# まだ画像を読み込んでいない場合
# =========================================================

if not st.session_state.image_loaded:

    st.subheader("路線価図画像を読み込む")

    uploaded_file = st.file_uploader(
        "路線価図画像を選択してください",
        type=[
            "png",
            "jpg",
            "jpeg"
        ]
    )

    # -----------------------------------------------------
    # 画像が選択された場合
    # -----------------------------------------------------

    if uploaded_file is not None:

        st.write(
            f"選択中：**{uploaded_file.name}**"
        )

        # -------------------------------------------------
        # 読み込みボタン
        # -------------------------------------------------

        if st.button(
            "画像を読み込む",
            type="primary",
            use_container_width=True
        ):

            # 画像データ取得
            image_bytes = uploaded_file.getvalue()

            # 画像サイズ取得
            image = Image.open(
                BytesIO(image_bytes)
            )

            # Base64化
            encoded = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            # MIMEタイプ
            if uploaded_file.type:
                mime_type = uploaded_file.type
            else:
                mime_type = "image/png"

            # Session Stateへ保存
            st.session_state.image_name = (
                uploaded_file.name
            )

            st.session_state.image_base64 = (
                f"data:{mime_type};base64,{encoded}"
            )

            st.session_state.image_width = (
                image.width
            )

            st.session_state.image_height = (
                image.height
            )

            # アノテーションを初期化
            st.session_state.annotations = []

            st.session_state.current_points = []

            # ビューア初期状態
            st.session_state.zoom = 1.0

            st.session_state.scroll_left = 0

            st.session_state.scroll_top = 0

            # 読み込み完了
            st.session_state.image_loaded = True

            st.rerun()

    else:

        st.info(
            "路線価図画像を選択してください。"
        )

    # ここで処理終了
    st.stop()


# =========================================================
# ここからアノテーション画面
# =========================================================

st.success(
    f"読み込み完了："
    f"{st.session_state.image_name} "
    f"（{st.session_state.image_width} × "
    f"{st.session_state.image_height}px）"
)


# =========================================================
# レイアウト
# =========================================================

left_col, right_col = st.columns(
    [4, 1]
)


# =========================================================
# 左側：地図
# =========================================================

with left_col:

    st.subheader("路線価図")

    # -----------------------------------------------------
    # ビューア
    # -----------------------------------------------------

    viewer_result = viewer_component(

        image=st.session_state.image_base64,

        image_width=(
            st.session_state.image_width
        ),

        image_height=(
            st.session_state.image_height
        ),

        annotations=(
            st.session_state.annotations
        ),

        current_points=(
            st.session_state.current_points
        ),

        zoom=(
            st.session_state.zoom
        ),

        scroll_left=(
            st.session_state.scroll_left
        ),

        scroll_top=(
            st.session_state.scroll_top
        ),

        height=650
    )


# =========================================================
# ビューアからの結果
# =========================================================

if viewer_result is not None:

    if viewer_result.get("type") == "point":

        # 現在の点
        st.session_state.current_points = (
            viewer_result.get(
                "current_points",
                []
            )
        )

        # ズーム
        st.session_state.zoom = (
            viewer_result.get(
                "zoom",
                st.session_state.zoom
            )
        )

        # スクロール
        st.session_state.scroll_left = (
            viewer_result.get(
                "scroll_left",
                st.session_state.scroll_left
            )
        )

        st.session_state.scroll_top = (
            viewer_result.get(
                "scroll_top",
                st.session_state.scroll_top
            )
        )

        st.rerun()


# =========================================================
# 右側：操作パネル
# =========================================================

with right_col:

    st.subheader("アノテーション")


    # -----------------------------------------------------
    # 現在の点
    # -----------------------------------------------------

    st.write(
        f"現在の点数："
        f"**{len(st.session_state.current_points)}**"
    )


    # -----------------------------------------------------
    # 1点戻す
    # -----------------------------------------------------

    if st.button(
        "1点戻す",
        use_container_width=True
    ):

        if st.session_state.current_points:

            st.session_state.current_points.pop()

            st.rerun()


    # -----------------------------------------------------
    # 現在の点をクリア
    # -----------------------------------------------------

    if st.button(
        "現在の点をクリア",
        use_container_width=True
    ):

        st.session_state.current_points = []

        st.rerun()


    st.divider()


    # -----------------------------------------------------
    # 路線価
    # -----------------------------------------------------

    road_value = st.text_input(
        "路線価",
        placeholder="例：120"
    )


    # -----------------------------------------------------
    # 記号
    # -----------------------------------------------------

    symbol = st.text_input(
        "記号",
        placeholder="例：A"
    )


    # -----------------------------------------------------
    # アノテーション登録
    # -----------------------------------------------------

    if st.button(
        "アノテーション登録",
        type="primary",
        use_container_width=True
    ):

        points = st.session_state.current_points

        if len(points) < 2:

            st.warning(
                "2点以上クリックしてください。"
            )

        elif road_value == "":

            st.warning(
                "路線価を入力してください。"
            )

        else:

            annotation_id = (
                len(st.session_state.annotations) + 1
            )

            annotation = {

                "id": annotation_id,

                "road_value": road_value,

                "symbol": symbol,

                "polyline_px": points.copy(),

                "start_point_px": points[0],

                "end_point_px": points[-1],

                "created_at":
                    datetime.now().isoformat()
            }

            st.session_state.annotations.append(
                annotation
            )

            # 現在の点をリセット
            st.session_state.current_points = []

            # JSON保存
            save_json()

            st.success(
                f"ID {annotation_id} を登録しました。"
            )

            st.rerun()


    st.divider()


    # =====================================================
    # 登録済み
    # =====================================================

    st.subheader("登録済み")


    if len(st.session_state.annotations) == 0:

        st.write(
            "まだ登録されていません。"
        )

    else:

        for annotation in (
            st.session_state.annotations
        ):

            st.write(
                f"**ID {annotation['id']}**"
            )

            st.write(
                f"路線価：{annotation['road_value']}"
            )

            st.write(
                f"記号：{annotation['symbol']}"
            )

            if st.button(
                f"ID {annotation['id']} を削除",
                key=f"delete_{annotation['id']}",
                use_container_width=True
            ):

                st.session_state.annotations = [
                    a
                    for a in st.session_state.annotations
                    if a["id"] != annotation["id"]
                ]

                # IDを振り直す
                for i, a in enumerate(
                    st.session_state.annotations,
                    start=1
                ):

                    a["id"] = i

                save_json()

                st.rerun()


    st.divider()


    # =====================================================
    # JSONダウンロード
    # =====================================================

    json_data = {

        "image":
            st.session_state.image_name,

        "image_width":
            st.session_state.image_width,

        "image_height":
            st.session_state.image_height,

        "annotations":
            st.session_state.annotations
    }


    json_string = json.dumps(
        json_data,
        ensure_ascii=False,
        indent=2
    )


    st.download_button(

        "JSONをダウンロード",

        data=json_string,

        file_name=(
            Path(
                st.session_state.image_name
            ).stem
            + "_annotations.json"
        ),

        mime="application/json",

        use_container_width=True
    )

import streamlit as st
import streamlit.components.v1 as components

import base64
import json
import os
from datetime import datetime
from pathlib import Path


# =========================================================
# 基本設定
# =========================================================

st.set_page_config(
    page_title="路線価図アノテーションツール",
    layout="wide"
)

st.title("路線価図アノテーションツール")


# =========================================================
# カスタムコンポーネント
# =========================================================

COMPONENT_DIR = Path(__file__).parent / "rosenka_viewer"

viewer_component = components.declare_component(
    "rosenka_viewer",
    path=str(COMPONENT_DIR)
)


# =========================================================
# Session State 初期化
# =========================================================

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

if "image_name" not in st.session_state:
    st.session_state.image_name = None

if "image_width" not in st.session_state:
    st.session_state.image_width = 0

if "image_height" not in st.session_state:
    st.session_state.image_height = 0

if "image_base64" not in st.session_state:
    st.session_state.image_base64 = None


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

    save_path = Path(
        "annotations"
    ) / f"{stem}_annotations.json"

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
# 画像アップロード
# =========================================================

uploaded_file = st.file_uploader(
    "路線価図画像をアップロードしてください",
    type=[
        "png",
        "jpg",
        "jpeg"
    ]
)


if uploaded_file is not None:

    # -----------------------------------------------------
    # 新しい画像がアップロードされた場合
    # -----------------------------------------------------

    if (
        st.session_state.image_name
        != uploaded_file.name
    ):

        st.session_state.image_name = (
            uploaded_file.name
        )

        image_bytes = uploaded_file.getvalue()

        st.session_state.image_base64 = (
            "data:image/png;base64,"
            + base64.b64encode(
                image_bytes
            ).decode("utf-8")
        )

        # Pillowで画像サイズ取得
        from PIL import Image

        from io import BytesIO

        image = Image.open(
            BytesIO(image_bytes)
        )

        st.session_state.image_width = (
            image.width
        )

        st.session_state.image_height = (
            image.height
        )

        # 新しい画像なのでリセット
        st.session_state.annotations = []
        st.session_state.current_points = []

        st.session_state.zoom = 1.0
        st.session_state.scroll_left = 0
        st.session_state.scroll_top = 0


# =========================================================
# 画像がない場合
# =========================================================

if st.session_state.image_base64 is None:

    st.info(
        "路線価図画像をアップロードしてください。"
    )

    st.stop()


# =========================================================
# 左右レイアウト
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
    # カスタムビューア
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
# ★ クリック結果を受け取る部分
# =========================================================

if viewer_result is not None:

    # -----------------------------------------------------
    # 地図上をクリックした場合
    # -----------------------------------------------------

    if viewer_result.get("type") == "point":

        st.session_state.current_points = (
            viewer_result.get(
                "current_points",
                []
            )
        )

        # ズーム倍率を保存
        st.session_state.zoom = (
            viewer_result.get(
                "zoom",
                st.session_state.zoom
            )
        )

        # スクロール位置を保存
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
# 右側：アノテーション操作
# =========================================================

with right_col:

    st.subheader("アノテーション")


    # -----------------------------------------------------
    # 現在の点数
    # -----------------------------------------------------

    st.write(
        f"現在の点数："
        f"{len(st.session_state.current_points)}"
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
    # 現在の点をすべて削除
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
        use_container_width=True,
        type="primary"
    ):

        if len(
            st.session_state.current_points
        ) < 2:

            st.warning(
                "2点以上クリックしてください。"
            )

        elif road_value == "":

            st.warning(
                "路線価を入力してください。"
            )

        else:

            points = (
                st.session_state.current_points
            )

            annotation_id = (
                len(
                    st.session_state.annotations
                ) + 1
            )

            annotation = {

                "id": annotation_id,

                "road_value": road_value,

                "symbol": symbol,

                "polyline_px": points,

                "start_point_px": points[0],

                "end_point_px": points[-1],

                "created_at": (
                    datetime.now().isoformat()
                )
            }

            st.session_state.annotations.append(
                annotation
            )

            # 現在の入力をリセット
            st.session_state.current_points = []

            # JSON保存
            save_json()

            st.success(
                f"アノテーション "
                f"{annotation_id} を登録しました。"
            )

            st.rerun()


    st.divider()


    # =====================================================
    # 登録済みアノテーション
    # =====================================================

    st.subheader(
        "登録済み"
    )


    if not st.session_state.annotations:

        st.write(
            "まだ登録されていません。"
        )

    else:

        for annotation in (
            st.session_state.annotations
        ):

            st.write(
                f"ID {annotation['id']}  "
                f"路線価："
                f"{annotation['road_value']}  "
                f"記号："
                f"{annotation['symbol']}"
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


    # =====================================================
    # JSONダウンロード
    # =====================================================

    st.divider()

    json_data = {

        "image": (
            st.session_state.image_name
        ),

        "image_width": (
            st.session_state.image_width
        ),

        "image_height": (
            st.session_state.image_height
        ),

        "annotations": (
            st.session_state.annotations
        )
    }


    json_string = json.dumps(
        json_data,
        ensure_ascii=False,
        indent=2
    )


    st.download_button(

        label="JSONをダウンロード",

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

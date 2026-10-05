import base64
import json
from datetime import datetime
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from PIL import Image


# ============================================================
# 設定
# ============================================================

st.set_page_config(
    page_title="路線価アノテーションツール",
    page_icon="🗺️",
    layout="wide",
)


# ============================================================
# カスタムコンポーネント
# ============================================================

VIEWER_PATH = str(
    Path(__file__).parent / "rosenka_viewer"
)

rosenka_viewer = components.declare_component(
    "rosenka_viewer",
    path=VIEWER_PATH,
)


# ============================================================
# Session State
# ============================================================

if "image" not in st.session_state:
    st.session_state.image = None

if "image_name" not in st.session_state:
    st.session_state.image_name = None

if "annotations" not in st.session_state:
    st.session_state.annotations = []

if "current_points" not in st.session_state:
    st.session_state.current_points = []

if "viewer_key" not in st.session_state:
    st.session_state.viewer_key = 0

if "last_viewer_event" not in st.session_state:
    st.session_state.last_viewer_event = None


# ============================================================
# 関数
# ============================================================

def image_to_base64(image: Image.Image) -> str:

    import io

    buffer = io.BytesIO()

    image.save(
        buffer,
        format="PNG"
    )

    return base64.b64encode(
        buffer.getvalue()
    ).decode("utf-8")


def save_json():

    if st.session_state.image is None:
        return None


    data = {
        "image": st.session_state.image_name,

        "image_width":
            st.session_state.image.width,

        "image_height":
            st.session_state.image.height,

        "annotations":
            st.session_state.annotations,

    }


    json_string = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )


    # --------------------------------------------------------
    # ローカルにも保存
    # --------------------------------------------------------

    save_dir = Path("annotations")

    save_dir.mkdir(
        exist_ok=True
    )


    stem = Path(
        st.session_state.image_name
    ).stem


    save_path = (
        save_dir /
        f"{stem}_annotations.json"
    )


    save_path.write_text(
        json_string,
        encoding="utf-8",
    )


    return json_string


def undo_point():

    if st.session_state.current_points:

        st.session_state.current_points.pop()


def clear_current_points():

    st.session_state.current_points = []

    st.session_state.viewer_key += 1


def delete_annotation(annotation_id):

    st.session_state.annotations = [
        annotation
        for annotation
        in st.session_state.annotations

        if annotation["id"] != annotation_id
    ]


# ============================================================
# タイトル
# ============================================================

st.title(
    "🗺️ 路線価アノテーションツール"
)

st.caption(
    "路線価図の矢印・路線価・記号をアノテーションします。"
)


# ============================================================
# サイドバー
# ============================================================

with st.sidebar:

    st.header("画像")

    uploaded_file = st.file_uploader(
        "路線価画像をアップロード",

        type=[
            "png",
            "jpg",
            "jpeg",
            "webp",
            "tif",
            "tiff",
        ],
    )


    # --------------------------------------------------------
    # 画像読み込み
    # --------------------------------------------------------

    if uploaded_file is not None:

        if (
            st.session_state.image_name
            != uploaded_file.name
        ):

            image = Image.open(
                uploaded_file
            ).convert("RGB")


            st.session_state.image = image

            st.session_state.image_name = (
                uploaded_file.name
            )

            st.session_state.annotations = []

            st.session_state.current_points = []

            st.session_state.last_viewer_event = None

            st.session_state.viewer_key += 1


    if st.session_state.image is not None:

        st.write(
            f"**ファイル:** "
            f"{st.session_state.image_name}"
        )

        st.write(
            f"**サイズ:** "
            f"{st.session_state.image.width} × "
            f"{st.session_state.image.height} px"
        )


# ============================================================
# 画像がない場合
# ============================================================

if st.session_state.image is None:

    st.info(
        "左側から路線価画像をアップロードしてください。"
    )

    st.stop()


# ============================================================
# 操作説明
# ============================================================

st.subheader(
    "① 矢印をアノテーション"
)

st.markdown(
    """
**操作方法**

- **左クリック**：点を追加
- **左ドラッグ**：画像を移動
- **マウスホイール**：画像をスクロール
- **Ctrl + マウスホイール**：マウス位置を中心にズーム
- **ダブルクリック**：100%に戻す
- **1点戻す**：直前の点を削除
- **全点クリア**：現在作成中の矢印を削除

曲線の矢印は、

`始点 → 経由点 → 経由点 → 終点`

の順番にクリックしてください。
"""
)


# ============================================================
# 画像ビューア
# ============================================================

image_base64 = image_to_base64(
    st.session_state.image
)


event = rosenka_viewer(
    image=image_base64,

    reset_points=(
        st.session_state.viewer_key
    ),

    key="rosenka_viewer",
)


# ============================================================
# Viewerからクリック座標を受け取る
# ============================================================

if event is not None:

    event_key = json.dumps(
        event,
        sort_keys=True,
        ensure_ascii=False,
    )


    if (
        event_key
        != st.session_state.last_viewer_event
    ):

        st.session_state.last_viewer_event = (
            event_key
        )


        if event.get("type") == "point":

            x = int(event["x"])

            y = int(event["y"])


            st.session_state.current_points.append(
                [x, y]
            )


            st.rerun()


# ============================================================
# 現在のpolyline
# ============================================================

st.subheader(
    "現在の矢印"
)


col1, col2, col3 = st.columns(3)


with col1:

    st.metric(
        "現在の点数",
        len(
            st.session_state.current_points
        ),
    )


with col2:

    st.metric(
        "登録済み",
        len(
            st.session_state.annotations
        ),
    )


with col3:

    if st.button(
        "↩️ 1点戻す",
        use_container_width=True,
    ):

        undo_point()

        st.rerun()


# ============================================================
# クリア
# ============================================================

if st.button(
    "🗑️ 現在の矢印を全クリア",
    use_container_width=True,
):

    clear_current_points()

    st.rerun()


# ============================================================
# 座標表示
# ============================================================

if st.session_state.current_points:

    st.write(
        "現在のpolyline座標"
    )

    st.code(
        json.dumps(
            st.session_state.current_points,
            ensure_ascii=False,
            indent=2,
        ),
        language="json",
    )


# ============================================================
# 路線価・記号
# ============================================================

st.divider()

st.subheader(
    "② 路線価・記号"
)


col1, col2 = st.columns(2)


with col1:

    road_value = st.text_input(
        "路線価",
        placeholder="例：120",
    )


with col2:

    symbol = st.text_input(
        "路線価の記号",
        placeholder="例：A",
    )


# ============================================================
# アノテーション登録
# ============================================================

if st.button(
    "＋ アノテーションを追加",
    type="primary",
    use_container_width=True,
):

    if len(
        st.session_state.current_points
    ) < 2:

        st.error(
            "始点・終点の2点以上を指定してください。"
        )


    elif not road_value.strip():

        st.error(
            "路線価を入力してください。"
        )


    elif not symbol.strip():

        st.error(
            "路線価の記号を入力してください。"
        )


    else:

        if st.session_state.annotations:

            new_id = max(
                a["id"]
                for a
                in st.session_state.annotations
            ) + 1

        else:

            new_id = 1


        points = [
            point.copy()
            for point
            in st.session_state.current_points
        ]


        annotation = {

            "id": new_id,

            "road_value":
                road_value.strip(),

            "symbol":
                symbol.strip(),

            "polyline_px":
                points,

            "start_point_px":
                points[0],

            "end_point_px":
                points[-1],

            "created_at":
                datetime.now().isoformat(),

        }


        st.session_state.annotations.append(
            annotation
        )


        # 現在の矢印をクリア
        st.session_state.current_points = []

        st.session_state.viewer_key += 1


        # 自動保存
        save_json()


        st.success(
            f"ID {new_id} を登録しました。"
        )


        st.rerun()


# ============================================================
# 登録済みアノテーション
# ============================================================

st.divider()

st.subheader(
    "③ 登録済みアノテーション"
)


if not st.session_state.annotations:

    st.info(
        "まだアノテーションはありません。"
    )


else:

    for annotation in (
        st.session_state.annotations
    ):

        annotation_id = annotation["id"]

        points = annotation[
            "polyline_px"
        ]


        with st.expander(
            f"ID {annotation_id} ｜ "
            f"路線価 {annotation['road_value']} ｜ "
            f"記号 {annotation['symbol']} ｜ "
            f"{len(points)}点"
        ):

            st.json(
                annotation
            )


            if st.button(
                "このアノテーションを削除",
                key=f"delete_{annotation_id}",
            ):

                delete_annotation(
                    annotation_id
                )

                save_json()

                st.rerun()


# ============================================================
# JSON
# ============================================================

st.divider()

st.subheader(
    "④ JSON"
)


if st.session_state.annotations:

    json_data = {

        "image":
            st.session_state.image_name,

        "image_width":
            st.session_state.image.width,

        "image_height":
            st.session_state.image.height,

        "annotations":
            st.session_state.annotations,

    }


    json_string = json.dumps(
        json_data,
        ensure_ascii=False,
        indent=2,
    )


    st.download_button(
        "⬇️ JSONをダウンロード",

        data=json_string,

        file_name=(
            f"{Path(st.session_state.image_name).stem}"
            "_annotations.json"
        ),

        mime="application/json",

        use_container_width=True,
    )


    st.code(
        json_string,
        language="json",
    )

else:

    st.info(
        "アノテーションを登録するとJSONが表示されます。"
    )

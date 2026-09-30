import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import json
import os
import io
import math

from streamlit_image_coordinates import streamlit_image_coordinates


# ============================================================
# 設定
# ============================================================

DEFAULT_IMAGE_PATH = "/workspace/notebooks/rosenka_annotaion/kobe_chuo_stitched_trimming.png"
DEFAULT_JSON_PATH = "/workspace/notebooks/rosenka_annotaion/ground_truth.json"


# ブラウザ上で表示する最大サイズ
MAX_DISPLAY_WIDTH = 1200
MAX_DISPLAY_HEIGHT = 800

# ============================================================
# Streamlit設定
# ============================================================

st.set_page_config(
    page_title="路線価矢印 Ground Truth Annotation Tool",
    layout="wide"
)

st.title("路線価矢印 Ground Truth Annotation Tool")

st.caption(
    "路線価図上の矢印を2回クリックして、Ground Truthを作成します。"
)


# ============================================================
# セッション状態
# ============================================================

if "annotations" not in st.session_state:
    st.session_state.annotations = []

if "pending_point" not in st.session_state:
    st.session_state.pending_point = None

if "image_path" not in st.session_state:
    st.session_state.image_path = None

if "image" not in st.session_state:
    st.session_state.image = None

if "json_path" not in st.session_state:
    st.session_state.json_path = DEFAULT_JSON_PATH

if "zoom" not in st.session_state:
    st.session_state.zoom = 1.0

if "view_x" not in st.session_state:
    st.session_state.view_x = 0

if "view_y" not in st.session_state:
    st.session_state.view_y = 0


# ============================================================
# JSON保存
# ============================================================

def save_json():
    """現在のアノテーションをJSONに保存"""

    data = {
        "annotations": st.session_state.annotations
    }

    with open(
        st.session_state.json_path,
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            data,
            f,
            ensure_ascii=False,
            indent=2
        )


# ============================================================
# JSON読み込み
# ============================================================

def load_json(json_path):
    """JSONからアノテーションを読み込む"""

    if not os.path.exists(json_path):
        return False

    try:
        with open(
            json_path,
            "r",
            encoding="utf-8"
        ) as f:
            data = json.load(f)

        annotations = data.get("annotations", [])

        st.session_state.annotations = annotations

        return True

    except Exception as e:
        st.error(f"JSONの読み込みに失敗しました: {e}")
        return False


# ============================================================
# 画像読み込み
# ============================================================

def load_image(image_path):
    """画像を読み込む"""

    try:
        image = Image.open(image_path).convert("RGB")

        st.session_state.image = image
        st.session_state.image_path = image_path

        # 表示位置をリセット
        st.session_state.view_x = 0
        st.session_state.view_y = 0

        return True

    except Exception as e:
        st.error(f"画像の読み込みに失敗しました: {e}")
        return False


# ============================================================
# サイドバー
# ============================================================

with st.sidebar:

    st.header("設定")

    # --------------------------------------------------------
    # 画像
    # --------------------------------------------------------

    st.subheader("1. 画像")

    uploaded_image = st.file_uploader(
        "路線価図を選択",
        type=["png", "jpg", "jpeg", "webp"],
        key="image_uploader"
    )

    if uploaded_image is not None:

        if (
            st.session_state.image_path != uploaded_image.name
        ):
            image_bytes = uploaded_image.read()

            image = Image.open(
                io.BytesIO(image_bytes)
            ).convert("RGB")

            st.session_state.image = image
            st.session_state.image_path = uploaded_image.name

            st.session_state.view_x = 0
            st.session_state.view_y = 0


    # --------------------------------------------------------
    # JSON
    # --------------------------------------------------------

    st.subheader("2. Ground Truth JSON")

    json_file = st.file_uploader(
        "既存JSONを読み込む",
        type=["json"],
        key="json_uploader"
    )

    if json_file is not None:

        try:

            data = json.load(json_file)

            st.session_state.annotations = data.get(
                "annotations",
                []
            )

            st.success(
                f"{len(st.session_state.annotations)}件読み込みました"
            )

        except Exception as e:

            st.error(
                f"JSON読み込みエラー: {e}"
            )


    # --------------------------------------------------------
    # JSON保存先
    # --------------------------------------------------------

    st.text_input(
        "JSON保存先",
        key="json_path"
    )


    # --------------------------------------------------------
    # ズーム
    # --------------------------------------------------------

    st.subheader("3. 表示")

    zoom = st.slider(
        "ズーム",
        min_value=0.25,
        max_value=4.0,
        value=st.session_state.zoom,
        step=0.25
    )

    st.session_state.zoom = zoom


    # --------------------------------------------------------
    # Undo
    # --------------------------------------------------------

    st.subheader("4. 操作")

    col1, col2 = st.columns(2)

    with col1:

        if st.button(
            "↩ Undo",
            use_container_width=True
        ):

            if len(st.session_state.annotations) > 0:

                st.session_state.annotations.pop()

                save_json()

                st.rerun()


    with col2:

        if st.button(
            "保存",
            use_container_width=True
        ):

            save_json()

            st.success("保存しました")


    # --------------------------------------------------------
    # アノテーション削除
    # --------------------------------------------------------

    st.subheader("5. 削除")

    if len(st.session_state.annotations) > 0:

        annotation_labels = [
            f"ID {a['id']}"
            for a in st.session_state.annotations
        ]

        selected_label = st.selectbox(
            "削除するアノテーション",
            annotation_labels
        )

        selected_id = int(
            selected_label.replace("ID ", "")
        )

        if st.button(
            "選択したIDを削除",
            use_container_width=True
        ):

            st.session_state.annotations = [
                a
                for a in st.session_state.annotations
                if a["id"] != selected_id
            ]

            save_json()

            st.rerun()


# ============================================================
# 画像が読み込まれていない場合
# ============================================================

if st.session_state.image is None:

    st.info(
        "左側の「画像」から路線価図を選択してください。"
    )

    st.stop()


# ============================================================
# 元画像
# ============================================================

original_image = st.session_state.image

original_width, original_height = original_image.size


# ============================================================
# 表示範囲
# ============================================================

# ズームによって表示する元画像範囲を変更
crop_width = int(
    MAX_DISPLAY_WIDTH / st.session_state.zoom
)

crop_height = int(
    MAX_DISPLAY_HEIGHT / st.session_state.zoom
)

crop_width = min(
    crop_width,
    original_width
)

crop_height = min(
    crop_height,
    original_height
)


# ------------------------------------------------------------
# 表示位置の範囲を計算
# ------------------------------------------------------------

max_view_x = max(
    0,
    original_width - crop_width
)

max_view_y = max(
    0,
    original_height - crop_height
)


# 表示位置が範囲外にならないようにする
st.session_state.view_x = min(
    max(st.session_state.view_x, 0),
    max_view_x
)

st.session_state.view_y = min(
    max(st.session_state.view_y, 0),
    max_view_y
)


# ============================================================
# パン操作
# ============================================================

st.subheader("表示位置")

col1, col2, col3, col4, col5 = st.columns(5)

PAN_X = max(
    1,
    int(crop_width * 0.7)
)

PAN_Y = max(
    1,
    int(crop_height * 0.7)
)


with col1:

    if st.button("← 左"):

        st.session_state.view_x = max(
            0,
            st.session_state.view_x - PAN_X
        )

        st.rerun()


with col2:

    if st.button("→ 右"):

        st.session_state.view_x = min(
            max_view_x,
            st.session_state.view_x + PAN_X
        )

        st.rerun()


with col3:

    if st.button("↑ 上"):

        st.session_state.view_y = max(
            0,
            st.session_state.view_y - PAN_Y
        )

        st.rerun()


with col4:

    if st.button("↓ 下"):

        st.session_state.view_y = min(
            max_view_y,
            st.session_state.view_y + PAN_Y
        )

        st.rerun()


with col5:

    if st.button("中央"):

        st.session_state.view_x = max_view_x // 2
        st.session_state.view_y = max_view_y // 2

        st.rerun()


# ============================================================
# 画像をCrop
# ============================================================

left = st.session_state.view_x
top = st.session_state.view_y

right = min(
    left + crop_width,
    original_width
)

bottom = min(
    top + crop_height,
    original_height
)

view_image = original_image.crop(
    (
        left,
        top,
        right,
        bottom
    )
)


# ============================================================
# 表示用画像サイズ
# ============================================================

view_width, view_height = view_image.size

display_scale = min(
    MAX_DISPLAY_WIDTH / view_width,
    MAX_DISPLAY_HEIGHT / view_height,
    1.0
)

display_width = int(
    view_width * display_scale
)

display_height = int(
    view_height * display_scale
)


display_image = view_image.resize(
    (
        display_width,
        display_height
    ),
    Image.Resampling.LANCZOS
)


# ============================================================
# アノテーションを表示画像に描画
# ============================================================

draw = ImageDraw.Draw(display_image)


# フォント
try:

    font = ImageFont.truetype(
        "DejaVuSans-Bold.ttf",
        18
    )

except:

    font = ImageFont.load_default()


for annotation in st.session_state.annotations:

    polyline = annotation.get(
        "polyline_px",
        []
    )

    if len(polyline) < 2:
        continue


    # 元画像座標 → Crop内座標
    p1 = polyline[0]
    p2 = polyline[1]

    x1 = (p1[0] - left) * display_scale
    y1 = (p1[1] - top) * display_scale

    x2 = (p2[0] - left) * display_scale
    y2 = (p2[1] - top) * display_scale


    # 画像範囲外なら描画しない
    if (
        max(x1, x2) < 0
        or min(x1, x2) > display_width
        or max(y1, y2) < 0
        or min(y1, y2) > display_height
    ):
        continue


    # 矢印の線
    draw.line(
        [
            (x1, y1),
            (x2, y2)
        ],
        fill="red",
        width=3
    )


    # ID
    text = str(annotation["id"])

    text_x = x1 + 5
    text_y = y1 - 20

    draw.text(
        (text_x, text_y),
        text,
        fill="red",
        font=font
    )


# ============================================================
# 現在の始点
# ============================================================

if st.session_state.pending_point is not None:

    px, py = st.session_state.pending_point

    x = (px - left) * display_scale
    y = (py - top) * display_scale

    if (
        0 <= x <= display_width
        and 0 <= y <= display_height
    ):

        r = 6

        draw.ellipse(
            [
                x - r,
                y - r,
                x + r,
                y + r
            ],
            fill="blue"
        )


# ============================================================
# 画像表示
# ============================================================

st.subheader("路線価図")

st.caption(
    f"元画像サイズ: {original_width} × {original_height} px　"
    f"表示範囲: ({left}, {top}) - ({right}, {bottom})"
)


clicked = streamlit_image_coordinates(
    display_image,
    key="annotation_image"
)


# ============================================================
# クリック処理
# ============================================================

if clicked is not None:

    # 表示画像上の座標
    display_x = clicked["x"]
    display_y = clicked["y"]


    # 表示画像座標 → Crop画像座標
    crop_x = display_x / display_scale
    crop_y = display_y / display_scale


    # Crop画像座標 → 元画像座標
    original_x = int(
        round(left + crop_x)
    )

    original_y = int(
        round(top + crop_y)
    )


    # 範囲チェック
    original_x = max(
        0,
        min(original_x, original_width - 1)
    )

    original_y = max(
        0,
        min(original_y, original_height - 1)
    )


    current_point = [
        original_x,
        original_y
    ]


    # --------------------------------------------------------
    # 1クリック目
    # --------------------------------------------------------

    if st.session_state.pending_point is None:

        st.session_state.pending_point = current_point

        st.rerun()


    # --------------------------------------------------------
    # 2クリック目
    # --------------------------------------------------------

    else:

        start_point = st.session_state.pending_point
        end_point = current_point


        # 同じ場所をクリックした場合
        distance = math.sqrt(
            (start_point[0] - end_point[0]) ** 2
            +
            (start_point[1] - end_point[1]) ** 2
        )


        if distance < 2:

            st.warning(
                "始点と終点が近すぎます。"
            )

            st.session_state.pending_point = None

            st.rerun()


        # ----------------------------------------------------
        # 新しいID
        # ----------------------------------------------------

        if len(st.session_state.annotations) == 0:

            new_id = 1

        else:

            new_id = max(
                int(a["id"])
                for a in st.session_state.annotations
            ) + 1


        # ----------------------------------------------------
        # アノテーション登録
        # ----------------------------------------------------

        annotation = {
            "id": new_id,
            "polyline_px": [
                start_point,
                end_point
            ]
        }


        st.session_state.annotations.append(
            annotation
        )


        # 始点をリセット
        st.session_state.pending_point = None


        # 自動保存
        save_json()


        st.rerun()


# ============================================================
# 操作説明
# ============================================================

st.divider()

st.subheader("操作方法")

col1, col2 = st.columns(2)

with col1:

    st.markdown(
        """
        **矢印の登録**

        1. 矢印の始点をクリック
        2. 矢印の終点をクリック
        3. 自動的にIDが付与されます
        4. `ground_truth.json` に自動保存されます
        """
    )


with col2:

    st.markdown(
        """
        **その他**

        - `Undo`：最後の矢印を削除
        - `保存`：JSONを手動保存
        - `ズーム`：表示倍率を変更
        - `← → ↑ ↓`：表示範囲を移動
        - `中央`：画像中央へ移動
        - 既存JSONを読み込むと途中から再開できます
        """
    )


# ============================================================
# 現在のアノテーション数
# ============================================================

st.divider()

st.metric(
    "登録済み矢印数",
    len(st.session_state.annotations)
)


# ============================================================
# JSONプレビュー
# ============================================================

with st.expander("現在のJSONを確認"):

    st.json(
        {
            "annotations":
                st.session_state.annotations
        }
    )
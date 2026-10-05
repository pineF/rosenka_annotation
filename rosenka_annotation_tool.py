import json
from datetime import datetime
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image, ImageDraw, ImageFont

from streamlit_image_coordinates import streamlit_image_coordinates


# ============================================================
# 基本設定
# ============================================================

st.set_page_config(
    page_title="路線価アノテーションツール",
    page_icon="🗺️",
    layout="wide",
)


# ============================================================
# 定数
# ============================================================

MIN_ZOOM = 0.5
MAX_ZOOM = 4.0
ZOOM_STEP = 0.25

SAVE_DIR = Path("annotations")
SAVE_DIR.mkdir(exist_ok=True)


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

if "last_click_timestamp" not in st.session_state:
    st.session_state.last_click_timestamp = None

if "zoom" not in st.session_state:
    st.session_state.zoom = 1.5

if "auto_save" not in st.session_state:
    st.session_state.auto_save = True


# ============================================================
# 関数
# ============================================================

def get_font(size=18):
    """
    画像上に文字を描画するためのフォントを取得する。
    環境によって日本語フォントがない場合があるため、
    見つからなければPILのデフォルトフォントを使用する。
    """

    font_candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Regular.otf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]

    for font_path in font_candidates:
        if Path(font_path).exists():
            try:
                return ImageFont.truetype(font_path, size)
            except Exception:
                pass

    return ImageFont.load_default()


def draw_arrow(
    draw,
    points,
    line_width=4,
    point_radius=6,
):
    """
    polylineと始点・終点を画像上に描画する。
    """

    if len(points) == 0:
        return

    # --------------------------------------------------------
    # 点
    # --------------------------------------------------------

    for i, (x, y) in enumerate(points):

        draw.ellipse(
            (
                x - point_radius,
                y - point_radius,
                x + point_radius,
                y + point_radius,
            ),
            fill="red",
            outline="white",
            width=2,
        )

        # 点番号
        font = get_font(16)

        draw.text(
            (x + 8, y - 20),
            str(i + 1),
            fill="red",
            font=font,
        )

    # --------------------------------------------------------
    # 線
    # --------------------------------------------------------

    if len(points) >= 2:

        draw.line(
            points,
            fill="red",
            width=line_width,
            joint="curve",
        )

        # ----------------------------------------------------
        # 終点に矢印
        # ----------------------------------------------------

        x1, y1 = points[-2]
        x2, y2 = points[-1]

        dx = x2 - x1
        dy = y2 - y1

        length = max((dx ** 2 + dy ** 2) ** 0.5, 1)

        ux = dx / length
        uy = dy / length

        arrow_length = 25
        arrow_width = 10

        base_x = x2 - ux * arrow_length
        base_y = y2 - uy * arrow_length

        px = -uy
        py = ux

        p1 = (
            x2,
            y2,
        )

        p2 = (
            base_x + px * arrow_width,
            base_y + py * arrow_width,
        )

        p3 = (
            base_x - px * arrow_width,
            base_y - py * arrow_width,
        )

        draw.polygon(
            [p1, p2, p3],
            fill="red",
        )


def create_display_image():
    """
    現在の画像に、
    ・登録済みアノテーション
    ・現在作成中のpolyline
    を描画して、ズーム倍率に応じた画像を返す。

    座標そのものは常に元画像座標。
    """

    image = st.session_state.image

    display_image = image.copy()

    draw = ImageDraw.Draw(display_image)

    # --------------------------------------------------------
    # 登録済みアノテーション
    # --------------------------------------------------------

    for annotation in st.session_state.annotations:

        points = annotation["polyline_px"]

        if len(points) == 0:
            continue

        # 登録済みは青
        if len(points) >= 2:

            draw.line(
                points,
                fill="blue",
                width=5,
                joint="curve",
            )

            # 矢印
            x1, y1 = points[-2]
            x2, y2 = points[-1]

            dx = x2 - x1
            dy = y2 - y1

            length = max((dx ** 2 + dy ** 2) ** 0.5, 1)

            ux = dx / length
            uy = dy / length

            arrow_length = 25
            arrow_width = 10

            base_x = x2 - ux * arrow_length
            base_y = y2 - uy * arrow_length

            px = -uy
            py = ux

            draw.polygon(
                [
                    (x2, y2),
                    (
                        base_x + px * arrow_width,
                        base_y + py * arrow_width,
                    ),
                    (
                        base_x - px * arrow_width,
                        base_y - py * arrow_width,
                    ),
                ],
                fill="blue",
            )

        # ID表示
        x, y = points[0]

        font = get_font(24)

        draw.text(
            (x + 10, y + 10),
            str(annotation["id"]),
            fill="blue",
            font=font,
        )

    # --------------------------------------------------------
    # 現在作成中のpolyline
    # --------------------------------------------------------

    if st.session_state.current_points:

        draw_arrow(
            draw,
            st.session_state.current_points,
            line_width=5,
            point_radius=7,
        )

    # --------------------------------------------------------
    # ズーム
    # --------------------------------------------------------

    zoom = st.session_state.zoom

    width = int(image.width * zoom)
    height = int(image.height * zoom)

    if zoom != 1.0:

        display_image = display_image.resize(
            (width, height),
            Image.Resampling.LANCZOS,
        )

    return display_image


def save_json():
    """
    現在のアノテーションをJSONとして保存。
    """

    if st.session_state.image is None:
        return None

    data = {
        "image": st.session_state.image_name,
        "image_width": st.session_state.image.width,
        "image_height": st.session_state.image.height,
        "created_at": datetime.now().isoformat(),
        "annotations": st.session_state.annotations,
    }

    json_string = json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )

    # ローカル保存
    if st.session_state.image_name:

        image_stem = Path(
            st.session_state.image_name
        ).stem

        save_path = SAVE_DIR / f"{image_stem}.json"

        save_path.write_text(
            json_string,
            encoding="utf-8",
        )

    return json_string


def reset_current_points():
    """
    作成中のpolylineを全削除。
    """

    st.session_state.current_points = []


def undo_point():
    """
    現在作成中のpolylineの最後の1点を削除。
    """

    if st.session_state.current_points:

        st.session_state.current_points.pop()


def delete_annotation(annotation_id):
    """
    登録済みアノテーションを削除。
    """

    st.session_state.annotations = [
        annotation
        for annotation in st.session_state.annotations
        if annotation["id"] != annotation_id
    ]


# ============================================================
# タイトル
# ============================================================

st.title("🗺️ 路線価アノテーションツール")

st.caption(
    "路線価図の矢印・路線価・記号をアノテーションします。"
)


# ============================================================
# サイドバー
# ============================================================

with st.sidebar:

    st.header("画像")

    uploaded_file = st.file_uploader(
        "路線価画像を選択",
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

        # 新しい画像が選択されたか確認
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

            st.session_state.last_click_timestamp = None

    if st.session_state.image is not None:

        st.write(
            f"**画像:** {st.session_state.image_name}"
        )

        st.write(
            f"**サイズ:** "
            f"{st.session_state.image.width} × "
            f"{st.session_state.image.height} px"
        )

    st.divider()

    # ========================================================
    # ズーム
    # ========================================================

    st.header("表示設定")

    st.session_state.zoom = st.slider(
        "ズーム倍率",
        min_value=MIN_ZOOM,
        max_value=MAX_ZOOM,
        value=st.session_state.zoom,
        step=ZOOM_STEP,
    )

    st.caption(
        f"現在の倍率: {st.session_state.zoom:.2f}倍"
    )

    st.divider()

    # ========================================================
    # 自動保存
    # ========================================================

    st.session_state.auto_save = st.checkbox(
        "アノテーション追加時に自動保存",
        value=True,
    )

    st.caption(
        "JSONは annotations フォルダにも保存されます。"
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
# メイン画面
# ============================================================

image = st.session_state.image


# ============================================================
# 操作説明
# ============================================================

st.subheader("① 矢印を作成")

st.markdown(
    """
    **始点 → 経由点 → 終点** の順に画像をクリックしてください。

    - 直線：2点
    - 曲線：3点以上
    - 拡大して細かい位置をクリックできます
    - 保存される座標は元画像のピクセル座標です
    """
)


# ============================================================
# 現在の状態
# ============================================================

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "現在の点数",
        len(st.session_state.current_points),
    )

with col2:

    st.metric(
        "登録済み",
        len(st.session_state.annotations),
    )

with col3:

    st.metric(
        "ズーム",
        f"{st.session_state.zoom:.2f}×",
    )


# ============================================================
# 画像生成
# ============================================================

display_image = create_display_image()

display_width = display_image.width


# ============================================================
# 画像クリック
# ============================================================

clicked = streamlit_image_coordinates(
    display_image,
    width=display_width,
    cursor="crosshair",
    key="rosenka_image",
)


# ============================================================
# クリックされた座標を取得
# ============================================================

if clicked is not None:

    timestamp = clicked.get("timestamp")

    # 同じクリックイベントを何度も追加しない
    if timestamp != st.session_state.last_click_timestamp:

        st.session_state.last_click_timestamp = timestamp

        clicked_x = clicked["x"]
        clicked_y = clicked["y"]

        zoom = st.session_state.zoom

        # 表示画像上の座標
        # ↓
        # 元画像の座標へ変換
        original_x = round(
            clicked_x / zoom
        )

        original_y = round(
            clicked_y / zoom
        )

        # 画像範囲内に収める
        original_x = max(
            0,
            min(
                original_x,
                image.width - 1,
            ),
        )

        original_y = max(
            0,
            min(
                original_y,
                image.height - 1,
            ),
        )

        st.session_state.current_points.append(
            [
                original_x,
                original_y,
            ]
        )

        st.rerun()


# ============================================================
# 現在の点の操作
# ============================================================

st.markdown("### 現在の矢印")

col1, col2, col3 = st.columns(3)

with col1:

    if st.button(
        "↩️ 1点戻す",
        use_container_width=True,
        disabled=(
            len(
                st.session_state.current_points
            )
            == 0
        ),
    ):

        undo_point()

        st.rerun()


with col2:

    if st.button(
        "🗑️ 全点クリア",
        use_container_width=True,
        disabled=(
            len(
                st.session_state.current_points
            )
            == 0
        ),
    ):

        reset_current_points()

        st.rerun()


with col3:

    if st.button(
        "🔄 表示を更新",
        use_container_width=True,
    ):

        st.rerun()


# ============================================================
# 現在の座標表示
# ============================================================

if st.session_state.current_points:

    st.write("現在のpolyline座標:")

    st.code(
        json.dumps(
            st.session_state.current_points,
            ensure_ascii=False,
            indent=2,
        ),
        language="json",
    )


# ============================================================
# アノテーション情報
# ============================================================

st.divider()

st.subheader("② 路線価・記号を入力")


col1, col2 = st.columns(2)

with col1:

    road_value = st.text_input(
        "路線価",
        placeholder="例：120",
        key="road_value_input",
    )

with col2:

    symbol = st.text_input(
        "路線価の記号",
        placeholder="例：A",
        key="symbol_input",
    )


# ============================================================
# アノテーション追加
# ============================================================

st.subheader("③ アノテーションを登録")


if st.button(
    "＋ アノテーションを追加",
    type="primary",
    use_container_width=True,
):

    # --------------------------------------------------------
    # 入力チェック
    # --------------------------------------------------------

    if len(
        st.session_state.current_points
    ) < 2:

        st.error(
            "矢印には最低2点が必要です。"
            "始点と終点をクリックしてください。"
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

        # ----------------------------------------------------
        # ID
        # ----------------------------------------------------

        if st.session_state.annotations:

            new_id = max(
                annotation["id"]
                for annotation
                in st.session_state.annotations
            ) + 1

        else:

            new_id = 1

        # ----------------------------------------------------
        # 座標
        # ----------------------------------------------------

        points = [
            point.copy()
            for point
            in st.session_state.current_points
        ]

        # ----------------------------------------------------
        # アノテーション
        # ----------------------------------------------------

        annotation = {

            "id": new_id,

            "road_value": road_value.strip(),

            "symbol": symbol.strip(),

            "polyline_px": points,

            "start_point_px": points[0],

            "end_point_px": points[-1],

            "created_at": datetime.now().isoformat(),

        }

        st.session_state.annotations.append(
            annotation
        )

        # ----------------------------------------------------
        # 現在のpolylineをリセット
        # ----------------------------------------------------

        st.session_state.current_points = []

        # ----------------------------------------------------
        # 自動保存
        # ----------------------------------------------------

        if st.session_state.auto_save:

            save_json()

        st.success(
            f"アノテーション ID {new_id} を登録しました。"
        )

        st.rerun()


# ============================================================
# 登録済みアノテーション
# ============================================================

st.divider()

st.subheader("④ 登録済みアノテーション")


if not st.session_state.annotations:

    st.info(
        "まだアノテーションはありません。"
    )

else:

    for annotation in st.session_state.annotations:

        annotation_id = annotation["id"]

        points = annotation["polyline_px"]

        with st.expander(
            f"ID {annotation_id} ｜ "
            f"路線価: {annotation['road_value']} ｜ "
            f"記号: {annotation['symbol']} ｜ "
            f"{len(points)}点"
        ):

            col1, col2 = st.columns([4, 1])

            with col1:

                st.write(
                    f"**始点:** "
                    f"{annotation['start_point_px']}"
                )

                st.write(
                    f"**終点:** "
                    f"{annotation['end_point_px']}"
                )

                st.write(
                    f"**polyline:** "
                    f"{len(points)}点"
                )

                st.json(annotation)

            with col2:

                if st.button(
                    "削除",
                    key=f"delete_{annotation_id}",
                    use_container_width=True,
                ):

                    delete_annotation(
                        annotation_id
                    )

                    if st.session_state.auto_save:
                        save_json()

                    st.rerun()


# ============================================================
# JSON
# ============================================================

st.divider()

st.subheader("⑤ JSON")


if st.session_state.annotations:

    json_data = {
        "image": st.session_state.image_name,
        "image_width": image.width,
        "image_height": image.height,
        "annotations": st.session_state.annotations,
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


# ============================================================
# 保存状況
# ============================================================

st.divider()

st.caption(
    "アノテーションを追加すると、annotations フォルダへ "
    "JSONが自動保存されます（自動保存ONの場合）。"
)

import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import json
import io
import re


# ============================================================
# ページ設定
# ============================================================

st.set_page_config(
    page_title="路線価アノテーションツール",
    page_icon="🗺️",
    layout="wide"
)


# ============================================================
# 定数
# ============================================================

SHAPES = [
    "六角形",
    "楕円",
    "八角形",
    "正円",
    "縦に潰れたひし形",
    "横長の長方形",
    "なし"
]

PATTERNS = [
    "斜線",
    "黒塗り",
    "なし"
]


# ============================================================
# Session State 初期化
# ============================================================

if "annotations" not in st.session_state:
    st.session_state.annotations = []

if "current_points" not in st.session_state:
    st.session_state.current_points = []

if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

if "image" not in st.session_state:
    st.session_state.image = None

if "image_name" not in st.session_state:
    st.session_state.image_name = None

if "canvas_key" not in st.session_state:
    st.session_state.canvas_key = 0

if "zoom" not in st.session_state:
    st.session_state.zoom = 0.5

if "land_price" not in st.session_state:
    st.session_state.land_price = None

if "symbol" not in st.session_state:
    st.session_state.symbol = ""

if "shape" not in st.session_state:
    st.session_state.shape = "なし"

if "left_pattern" not in st.session_state:
    st.session_state.left_pattern = "なし"

if "right_pattern" not in st.session_state:
    st.session_state.right_pattern = "なし"


# ============================================================
# 関数
# ============================================================

def reset_current_annotation():
    """
    現在作成中のアノテーションをすべてクリア
    """
    st.session_state.current_points = []
    st.session_state.canvas_key += 1


def undo_last_point():
    """
    最後に追加した点を1つ削除
    """
    if st.session_state.current_points:
        st.session_state.current_points.pop()
        st.session_state.canvas_key += 1


def get_next_id():
    """
    次のアノテーションIDを取得
    """
    if not st.session_state.annotations:
        return 1

    return max(
        annotation["id"]
        for annotation in st.session_state.annotations
    ) + 1


def validate_symbol(symbol):
    """
    記号がA～Gのみか確認
    """
    if symbol == "":
        return False

    return bool(re.fullmatch(r"[A-G]", symbol))


def normalize_symbol(symbol):
    """
    記号を大文字に変換
    """
    return symbol.strip().upper()


def get_form_values():
    """
    現在の入力値を取得
    """
    return {
        "land_price": st.session_state.land_price,
        "symbol": normalize_symbol(st.session_state.symbol),
        "shape": st.session_state.shape,
        "left_pattern": st.session_state.left_pattern,
        "right_pattern": st.session_state.right_pattern
    }


def validate_annotation():
    """
    アノテーション登録前のバリデーション
    """
    errors = []

    points = st.session_state.current_points

    # polyline
    if len(points) < 2:
        errors.append(
            "polylineには2点以上のクリックが必要です。"
        )

    # 路線価
    land_price = st.session_state.land_price

    if land_price is None:
        errors.append("路線価を入力してください。")
    else:
        try:
            value = int(land_price)

            if value < 0:
                errors.append("路線価は0以上の数値を入力してください。")

        except (ValueError, TypeError):
            errors.append("路線価は数値で入力してください。")

    # 記号
    symbol = normalize_symbol(st.session_state.symbol)

    if symbol == "":
        errors.append("記号を入力してください。")
    elif not validate_symbol(symbol):
        errors.append(
            "記号はA～Gのいずれか1文字を入力してください。"
        )

    # 形
    if st.session_state.shape not in SHAPES:
        errors.append("形を選択してください。")

    # 左側模様
    if st.session_state.left_pattern not in PATTERNS:
        errors.append("左側の模様を選択してください。")

    # 右側模様
    if st.session_state.right_pattern not in PATTERNS:
        errors.append("右側の模様を選択してください。")

    return errors


def create_annotation():
    """
    現在の入力内容からアノテーションを作成
    """
    points = st.session_state.current_points

    annotation = {
        "id": get_next_id(),

        # 始点
        "start": [
            int(round(points[0][0])),
            int(round(points[0][1]))
        ],

        # 終点
        "end": [
            int(round(points[-1][0])),
            int(round(points[-1][1]))
        ],

        # polyline
        "polyline": [
            [
                int(round(point[0])),
                int(round(point[1]))
            ]
            for point in points
        ],

        # 路線価
        "land_price": int(st.session_state.land_price),

        # 記号
        "symbol": normalize_symbol(st.session_state.symbol),

        # マーク
        "mark": {
            "shape": st.session_state.shape,
            "left_pattern": st.session_state.left_pattern,
            "right_pattern": st.session_state.right_pattern
        }
    }

    return annotation


def register_annotation():
    """
    新規アノテーションを登録
    """
    errors = validate_annotation()

    if errors:
        for error in errors:
            st.error(error)

        return False

    annotation = create_annotation()

    st.session_state.annotations.append(annotation)

    reset_current_annotation()

    # 入力欄をリセット
    st.session_state.land_price = None
    st.session_state.symbol = ""
    st.session_state.shape = "なし"
    st.session_state.left_pattern = "なし"
    st.session_state.right_pattern = "なし"

    return True


def update_annotation(annotation_id):
    """
    登録済みアノテーションを更新
    """
    errors = validate_annotation()

    if errors:
        for error in errors:
            st.error(error)

        return False

    new_annotation = create_annotation()
    new_annotation["id"] = annotation_id

    for i, annotation in enumerate(st.session_state.annotations):

        if annotation["id"] == annotation_id:
            st.session_state.annotations[i] = new_annotation
            break

    reset_current_annotation()

    st.session_state.editing_id = None

    st.session_state.land_price = None
    st.session_state.symbol = ""
    st.session_state.shape = "なし"
    st.session_state.left_pattern = "なし"
    st.session_state.right_pattern = "なし"

    return True


def start_edit(annotation):
    """
    登録済みアノテーションの編集を開始
    """
    st.session_state.editing_id = annotation["id"]

    st.session_state.current_points = [
        list(point)
        for point in annotation["polyline"]
    ]

    st.session_state.land_price = annotation["land_price"]
    st.session_state.symbol = annotation["symbol"]

    st.session_state.shape = annotation["mark"]["shape"]
    st.session_state.left_pattern = annotation["mark"]["left_pattern"]
    st.session_state.right_pattern = annotation["mark"]["right_pattern"]

    st.session_state.canvas_key += 1


def delete_annotation(annotation_id):
    """
    アノテーション削除
    """
    st.session_state.annotations = [
        annotation
        for annotation in st.session_state.annotations
        if annotation["id"] != annotation_id
    ]

    # IDを詰め直さない
    # → 一度付けたIDを変更しないため


def save_json():
    """
    JSONデータを作成
    """
    if st.session_state.image is None:
        return None

    data = {
        "image_name": st.session_state.image_name,
        "image_width": st.session_state.image.width,
        "image_height": st.session_state.image.height,
        "annotations": st.session_state.annotations
    }

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=4
    )


def load_json(uploaded_json):
    """
    JSONを読み込む
    """
    try:
        data = json.load(uploaded_json)

        required_keys = [
            "image_name",
            "image_width",
            "image_height",
            "annotations"
        ]

        for key in required_keys:
            if key not in data:
                raise ValueError(
                    f"JSONに「{key}」がありません。"
                )

        st.session_state.annotations = data["annotations"]

        return True

    except Exception as e:
        st.error(f"JSONの読み込みに失敗しました: {e}")
        return False


# ============================================================
# タイトル
# ============================================================

st.title("🗺️ 路線価アノテーションツール")

st.caption(
    "画像上で路線価を表す線をクリックしてアノテーションします。"
)


# ============================================================
# サイドバー
# ============================================================

with st.sidebar:

    st.header("画像")

    uploaded_file = st.file_uploader(
        "画像をアップロード",
        type=[
            "png",
            "jpg",
            "jpeg",
            "webp"
        ]
    )

    if uploaded_file is not None:

        # ファイルが変更された場合
        if (
            st.session_state.image_name
            != uploaded_file.name
        ):

            image_bytes = uploaded_file.read()

            image = Image.open(
                io.BytesIO(image_bytes)
            ).convert("RGB")

            st.session_state.image = image
            st.session_state.image_name = uploaded_file.name

            # 新しい画像なのでアノテーションを初期化
            st.session_state.annotations = []
            st.session_state.current_points = []
            st.session_state.editing_id = None
            st.session_state.canvas_key += 1

    if st.session_state.image is not None:

        st.divider()

        st.subheader("画像情報")

        st.write(
            f"ファイル名：{st.session_state.image_name}"
        )

        st.write(
            f"サイズ："
            f"{st.session_state.image.width} × "
            f"{st.session_state.image.height} px"
        )

        st.divider()

        st.subheader("ズーム")

        st.session_state.zoom = st.slider(
            "表示倍率",
            min_value=0.10,
            max_value=2.00,
            value=st.session_state.zoom,
            step=0.10,
            format="%.1fx"
        )

        st.caption(
            "画像が画面より大きい場合は、"
            "ページをスクロールして確認できます。"
        )


# ============================================================
# 画像がない場合
# ============================================================

if st.session_state.image is None:

    st.info(
        "左側の「画像をアップロード」から"
        "路線価図をアップロードしてください。"
    )

    st.stop()


# ============================================================
# メイン画面
# ============================================================

left_col, right_col = st.columns(
    [3, 1],
    gap="large"
)


# ============================================================
# 左側：画像
# ============================================================

with left_col:

    st.subheader("画像")

    st.info(
        "始点から終点に向かう方向を基準に、"
        "左側・右側を判定します。"
    )

    st.markdown(
        """
        **左右の定義**

        ```text
                左側
                 ↓
        始点 ●────────────● 終点
                 ↑
                右側
        ```

        画像上をクリックしてpolylineを作成してください。
        """
    )

    # ========================================================
    # 表示サイズ
    # ========================================================

    original_width = st.session_state.image.width
    original_height = st.session_state.image.height

    zoom = st.session_state.zoom

    canvas_width = max(
        1,
        int(original_width * zoom)
    )

    canvas_height = max(
        1,
        int(original_height * zoom)
    )

    # ========================================================
    # 背景画像をズーム
    # ========================================================

    resized_image = st.session_state.image.resize(
        (
            canvas_width,
            canvas_height
        ),
        Image.Resampling.LANCZOS
    )

    # ========================================================
    # Canvas
    # ========================================================

    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.0)",
        stroke_width=3,
        stroke_color="#ff0000",

        background_image=resized_image,

        update_streamlit=True,

        height=canvas_height,
        width=canvas_width,

        drawing_mode="point",

        point_display_radius=6,

        key=f"canvas_{st.session_state.canvas_key}"
    )

    # ========================================================
    # Canvasからクリック点を取得
    # ========================================================

    if canvas_result.json_data is not None:

        objects = canvas_result.json_data.get(
            "objects",
            []
        )

        # canvasに存在する点を取得
        canvas_points = []

        for obj in objects:

            if obj.get("type") != "circle":
                continue

            left = obj.get("left", 0)
            top = obj.get("top", 0)

            radius = obj.get(
                "radius",
                0
            )

            scale_x = obj.get(
                "scaleX",
                1
            )

            scale_y = obj.get(
                "scaleY",
                1
            )

            # 円の中心座標
            x_display = (
                left
                + radius * scale_x
            )

            y_display = (
                top
                + radius * scale_y
            )

            # 表示座標 → 元画像座標
            x_original = x_display / zoom
            y_original = y_display / zoom

            canvas_points.append(
                [
                    x_original,
                    y_original
                ]
            )

        # Canvasから取得した点数が
        # 現在の状態より増えている場合
        if len(canvas_points) > len(
            st.session_state.current_points
        ):

            new_points = canvas_points[
                len(st.session_state.current_points):
            ]

            for point in new_points:
                st.session_state.current_points.append(
                    point
                )

            st.rerun()

    # ========================================================
    # 現在のpolylineを表示
    # ========================================================

    points = st.session_state.current_points

    st.write(
        f"現在のクリック点数：**{len(points)}点**"
    )

    if len(points) >= 1:

        st.write(
            f"始点："
            f"({points[0][0]:.0f}, "
            f"{points[0][1]:.0f})"
        )

    if len(points) >= 2:

        st.write(
            f"終点："
            f"({points[-1][0]:.0f}, "
            f"{points[-1][1]:.0f})"
        )

    # ========================================================
    # 操作ボタン
    # ========================================================

    button_col1, button_col2 = st.columns(2)

    with button_col1:

        if st.button(
            "↩ 1つ戻す",
            use_container_width=True
        ):
            undo_last_point()
            st.rerun()

    with button_col2:

        if st.button(
            "🗑 すべてクリア",
            use_container_width=True
        ):
            reset_current_annotation()
            st.rerun()


# ============================================================
# 右側：入力
# ============================================================

with right_col:

    st.subheader("アノテーション")

    if st.session_state.editing_id is not None:

        st.warning(
            f"ID {st.session_state.editing_id} を修正中です。"
        )

    # ========================================================
    # 路線価
    # ========================================================

    st.number_input(
        "路線価 *",
        min_value=0,
        step=1,
        value=st.session_state.land_price,
        key="land_price",
        help="路線価を数値で入力してください。"
    )

    # ========================================================
    # 記号
    # ========================================================

    symbol_input = st.text_input(
        "記号 *",
        value=st.session_state.symbol,
        max_chars=1,
        key="symbol"
    )

    normalized_symbol = normalize_symbol(
        symbol_input
    )

    if symbol_input != normalized_symbol:

        st.session_state.symbol = normalized_symbol

    if symbol_input:

        if validate_symbol(normalized_symbol):

            st.success(
                f"記号「{normalized_symbol}」は有効です。"
            )

        else:

            st.error(
                "記号はA～Gのいずれか1文字を入力してください。"
            )

    else:

        st.warning(
            "記号を入力してください。"
        )

    # ========================================================
    # マーク
    # ========================================================

    st.markdown("### マーク")

    st.caption(
        "形は左右共通、模様は左右別々に設定します。"
    )

    # 形
    st.selectbox(
        "形（左右共通） *",
        SHAPES,
        key="shape"
    )

    # 左側
    st.markdown("#### 左側")

    st.selectbox(
        "模様（左側） *",
        PATTERNS,
        key="left_pattern"
    )

    # 右側
    st.markdown("#### 右側")

    st.selectbox(
        "模様（右側） *",
        PATTERNS,
        key="right_pattern"
    )

    st.divider()

    # ========================================================
    # 必須項目チェック
    # ========================================================

    validation_errors = validate_annotation()

    if validation_errors:

        st.warning(
            "登録するには以下を修正してください。"
        )

        for error in validation_errors:

            st.write(
                f"・{error}"
            )

    else:

        st.success(
            "登録に必要な項目はすべて入力されています。"
        )

    # ========================================================
    # 登録 / 更新
    # ========================================================

    if st.session_state.editing_id is None:

        if st.button(
            "＋ アノテーションを登録",
            type="primary",
            use_container_width=True,
            disabled=len(validation_errors) > 0
        ):

            success = register_annotation()

            if success:

                st.success(
                    "アノテーションを登録しました。"
                )

                st.rerun()

    else:

        col_update, col_cancel = st.columns(2)

        with col_update:

            if st.button(
                "✓ 修正を保存",
                type="primary",
                use_container_width=True,
                disabled=len(validation_errors) > 0
            ):

                editing_id = (
                    st.session_state.editing_id
                )

                success = update_annotation(
                    editing_id
                )

                if success:

                    st.success(
                        "アノテーションを修正しました。"
                    )

                    st.rerun()

        with col_cancel:

            if st.button(
                "キャンセル",
                use_container_width=True
            ):

                st.session_state.editing_id = None

                reset_current_annotation()

                st.session_state.land_price = None
                st.session_state.symbol = ""
                st.session_state.shape = "なし"
                st.session_state.left_pattern = "なし"
                st.session_state.right_pattern = "なし"

                st.rerun()


# ============================================================
# 登録済みアノテーション
# ============================================================

st.divider()

st.subheader(
    f"登録済みアノテーション："
    f"{len(st.session_state.annotations)}件"
)


# ============================================================
# JSON保存・読み込み
# ============================================================

save_col, load_col = st.columns(2)

with save_col:

    json_data = save_json()

    if json_data is not None:

        st.download_button(
            label="💾 アノテーション結果をJSON保存",
            data=json_data,
            file_name=(
                f"{st.session_state.image_name}"
                ".json"
            ),
            mime="application/json",
            use_container_width=True
        )

with load_col:

    uploaded_json = st.file_uploader(
        "保存済みJSONを読み込む",
        type=["json"],
        key="json_uploader"
    )

    if uploaded_json is not None:

        if st.button(
            "JSONを読み込む",
            use_container_width=True
        ):

            success = load_json(
                uploaded_json
            )

            if success:

                st.success(
                    "JSONを読み込みました。"
                )

                st.rerun()


# ============================================================
# アノテーション一覧
# ============================================================

if not st.session_state.annotations:

    st.info(
        "まだアノテーションは登録されていません。"
    )

else:

    # --------------------------------------------------------
    # 1件表示用のスクロール領域
    # --------------------------------------------------------

    st.markdown(
        "登録済みデータ"
    )

    annotation_container = st.container(
        height=500,
        border=True
    )

    with annotation_container:

        # 新しいものから表示
        for annotation in reversed(
            st.session_state.annotations
        ):

            annotation_id = annotation["id"]

            st.markdown(
                f"### ID {annotation_id}"
            )

            info_col, button_col = st.columns(
                [4, 1]
            )

            with info_col:

                st.write(
                    f"**路線価：** "
                    f"{annotation['land_price']}"
                )

                st.write(
                    f"**記号：** "
                    f"{annotation['symbol']}"
                )

                st.write(
                    f"**形：** "
                    f"{annotation['mark']['shape']}"
                )

                st.write(
                    f"**左側の模様：** "
                    f"{annotation['mark']['left_pattern']}"
                )

                st.write(
                    f"**右側の模様：** "
                    f"{annotation['mark']['right_pattern']}"
                )

                st.write(
                    f"**始点：** "
                    f"{annotation['start']}"
                )

                st.write(
                    f"**終点：** "
                    f"{annotation['end']}"
                )

                st.write(
                    f"**polyline：** "
                    f"{len(annotation['polyline'])}点"
                )

            with button_col:

                if st.button(
                    "修正",
                    key=f"edit_{annotation_id}",
                    use_container_width=True
                ):

                    start_edit(annotation)

                    st.rerun()

                if st.button(
                    "削除",
                    key=f"delete_{annotation_id}",
                    use_container_width=True
                ):

                    delete_annotation(
                        annotation_id
                    )

                    # 編集中だった場合
                    if (
                        st.session_state.editing_id
                        == annotation_id
                    ):

                        st.session_state.editing_id = None
                        reset_current_annotation()

                    st.rerun()

            st.divider()


# ============================================================
# フッター
# ============================================================

st.caption(
    "保存される座標はすべてアップロードした元画像のピクセル座標です。"
)

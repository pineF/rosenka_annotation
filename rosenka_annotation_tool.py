import streamlit as st
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import json
import io


# ============================================================
# ページ設定
# ============================================================

st.set_page_config(
    page_title="路線価アノテーションツール",
    layout="wide"
)

st.title("路線価アノテーションツール")


# ============================================================
# Session State 初期化
# ============================================================

if "annotations" not in st.session_state:
    st.session_state.annotations = []

if "current_points" not in st.session_state:
    st.session_state.current_points = []

if "editing_id" not in st.session_state:
    st.session_state.editing_id = None

if "edit_points" not in st.session_state:
    st.session_state.edit_points = []

if "last_canvas_count" not in st.session_state:
    st.session_state.last_canvas_count = 0

if "image_name" not in st.session_state:
    st.session_state.image_name = None

if "image_width" not in st.session_state:
    st.session_state.image_width = None

if "image_height" not in st.session_state:
    st.session_state.image_height = None

if "loaded_image_key" not in st.session_state:
    st.session_state.loaded_image_key = None


# ============================================================
# 定数
# ============================================================

SHAPE_OPTIONS = [
    "六角形",
    "楕円",
    "八角形",
    "正円",
    "縦に潰れたひし形",
    "横長の長方形",
    "なし"
]

PATTERN_OPTIONS = [
    "斜線",
    "黒塗り",
    "なし"
]


# ============================================================
# 画像アップロード
# ============================================================

uploaded_file = st.file_uploader(
    "路線価図をアップロードしてください",
    type=["png", "jpg", "jpeg"]
)


if uploaded_file is not None:

    image_bytes = uploaded_file.getvalue()

    # ファイル内容を識別するためのキー
    image_key = (
        uploaded_file.name,
        len(image_bytes)
    )

    # 新しい画像がアップロードされた場合
    if st.session_state.loaded_image_key != image_key:

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        st.session_state.image_name = uploaded_file.name
        st.session_state.image_width = image.width
        st.session_state.image_height = image.height

        st.session_state.loaded_image_key = image_key

        # 画像を変更した場合は現在の作業点をリセット
        st.session_state.current_points = []
        st.session_state.last_canvas_count = 0
        st.session_state.editing_id = None
        st.session_state.edit_points = []

    else:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

else:
    image = None


# ============================================================
# 画像がアップロードされている場合
# ============================================================

if image is not None:

    original_width = image.width
    original_height = image.height

    st.info(
        f"画像サイズ：{original_width} × {original_height} px"
    )

    # ========================================================
    # ズーム設定
    # ========================================================

    st.subheader("画像表示")

    zoom = st.slider(
        "拡大・縮小",
        min_value=0.25,
        max_value=2.0,
        value=1.0,
        step=0.25
    )

    # 表示用画像サイズ
    canvas_width = max(1, int(original_width * zoom))
    canvas_height = max(1, int(original_height * zoom))

    resized_image = image.resize(
        (canvas_width, canvas_height),
        Image.Resampling.LANCZOS
    )

    # ========================================================
    # 左右の定義
    # ========================================================

    st.markdown(
        """
        ### 左右の定義

        始点から終点へ向かって見たときの左右です。

        ```
                    左側
                     ↓
        始点 ●────────────● 終点
                     ↑
                    右側
        ```
        """
    )

    # ========================================================
    # 編集中かどうか
    # ========================================================

    if st.session_state.editing_id is not None:

        editing_annotation = None

        for ann in st.session_state.annotations:
            if ann["id"] == st.session_state.editing_id:
                editing_annotation = ann
                break

        if editing_annotation is not None:

            st.warning(
                f"ID {st.session_state.editing_id} を修正中です。"
            )

            # 編集中の点を使用
            if len(st.session_state.edit_points) > 0:
                display_points = st.session_state.edit_points
            else:
                display_points = editing_annotation["polyline"]

        else:
            st.session_state.editing_id = None
            display_points = st.session_state.current_points

    else:
        display_points = st.session_state.current_points


    # ========================================================
    # キャンバス
    # ========================================================

    # 編集中の既存点をキャンバスに表示するための初期データ
    initial_drawing = None

    if len(display_points) > 0:

        objects = []

        for point in display_points:

            x_original = point[0]
            y_original = point[1]

            x_display = x_original * zoom
            y_display = y_original * zoom

            objects.append({
                "type": "circle",
                "left": x_display - 5,
                "top": y_display - 5,
                "radius": 5,
                "fill": "red",
                "stroke": "red",
                "strokeWidth": 1,
                "scaleX": 1,
                "scaleY": 1
            })

        initial_drawing = json.dumps({
            "version": "4.4.0",
            "objects": objects
        })


    # ========================================================
    # キャンバス表示
    # ========================================================

    canvas_container = st.container(
        height=700,
        border=True
    )

    with canvas_container:

        canvas_result = st_canvas(
            fill_color="rgba(255, 0, 0, 0.3)",
            stroke_width=2,
            stroke_color="#ff0000",
            background_image=resized_image,
            update_streamlit=True,
            height=canvas_height,
            width=canvas_width,
            drawing_mode="point",
            point_display_radius=5,
            key=f"canvas_{st.session_state.image_name}_{st.session_state.editing_id}_{zoom}",
            initial_drawing=initial_drawing
        )


    # ========================================================
    # キャンバス上のクリック点を取得
    # ========================================================

    if canvas_result.json_data is not None:

        objects = canvas_result.json_data.get(
            "objects",
            []
        )

        current_canvas_count = len(objects)

        # 新しく追加された点だけ取得
        if current_canvas_count > st.session_state.last_canvas_count:

            new_objects = objects[
                st.session_state.last_canvas_count:
            ]

            for obj in new_objects:

                if obj.get("type") != "circle":
                    continue

                left = obj.get("left", 0)
                top = obj.get("top", 0)

                radius = obj.get("radius", 5)

                scale_x = obj.get("scaleX", 1)
                scale_y = obj.get("scaleY", 1)

                # 円の中心位置
                x_display = (
                    left +
                    radius * scale_x
                )

                y_display = (
                    top +
                    radius * scale_y
                )

                # 表示座標 → 元画像座標
                x_original = x_display / zoom
                y_original = y_display / zoom

                # 画像範囲内に収める
                x_original = max(
                    0,
                    min(
                        original_width - 1,
                        x_original
                    )
                )

                y_original = max(
                    0,
                    min(
                        original_height - 1,
                        y_original
                    )
                )

                point = [
                    round(x_original, 2),
                    round(y_original, 2)
                ]

                if st.session_state.editing_id is not None:

                    st.session_state.edit_points.append(
                        point
                    )

                else:

                    st.session_state.current_points.append(
                        point
                    )

            st.session_state.last_canvas_count = (
                current_canvas_count
            )


    # ========================================================
    # 現在の点数表示
    # ========================================================

    if st.session_state.editing_id is not None:

        current_point_count = len(
            st.session_state.edit_points
        )

    else:

        current_point_count = len(
            st.session_state.current_points
        )

    st.write(
        f"現在のクリック点数：{current_point_count}"
    )


    # ========================================================
    # 点操作ボタン
    # ========================================================

    col1, col2, col3 = st.columns(3)

    with col1:

        if st.button(
            "1つ戻す",
            use_container_width=True
        ):

            if st.session_state.editing_id is not None:

                if len(st.session_state.edit_points) > 0:
                    st.session_state.edit_points.pop()

            else:

                if len(st.session_state.current_points) > 0:
                    st.session_state.current_points.pop()

            st.session_state.last_canvas_count = 0

            st.rerun()


    with col2:

        if st.button(
            "すべてクリア",
            use_container_width=True
        ):

            if st.session_state.editing_id is not None:

                st.session_state.edit_points = []

            else:

                st.session_state.current_points = []

            st.session_state.last_canvas_count = 0

            st.rerun()


    with col3:

        if st.session_state.editing_id is not None:

            if st.button(
                "修正をキャンセル",
                use_container_width=True
            ):

                st.session_state.editing_id = None
                st.session_state.edit_points = []
                st.session_state.last_canvas_count = 0

                st.rerun()


    # ========================================================
    # アノテーション情報入力
    # ========================================================

    st.divider()

    st.subheader("アノテーション情報")


    # 編集中のデータを取得
    editing_annotation = None

    if st.session_state.editing_id is not None:

        for ann in st.session_state.annotations:

            if ann["id"] == st.session_state.editing_id:
                editing_annotation = ann
                break


    # 初期値
    if editing_annotation is not None:

        default_land_price = editing_annotation.get(
            "land_price",
            0
        )

        default_symbol = editing_annotation.get(
            "symbol",
            ""
        )

        default_shape = editing_annotation.get(
            "mark",
            {}
        ).get(
            "shape",
            "なし"
        )

        default_left_pattern = editing_annotation.get(
            "mark",
            {}
        ).get(
            "left_pattern",
            "なし"
        )

        default_right_pattern = editing_annotation.get(
            "mark",
            {}
        ).get(
            "right_pattern",
            "なし"
        )

    else:

        default_land_price = 0
        default_symbol = ""
        default_shape = "なし"
        default_left_pattern = "なし"
        default_right_pattern = "なし"


    # --------------------------------------------------------
    # 路線価
    # --------------------------------------------------------

    land_price = st.number_input(
        "路線価",
        min_value=0,
        step=1,
        value=int(default_land_price)
    )


    # --------------------------------------------------------
    # 記号
    # --------------------------------------------------------

    symbol_input = st.text_input(
        "記号（A～G）",
        value=default_symbol,
        max_chars=1
    )

    symbol = symbol_input.strip().upper()


    # --------------------------------------------------------
    # マーク
    # --------------------------------------------------------

    st.markdown("### マーク")

    shape = st.selectbox(
        "形状",
        SHAPE_OPTIONS,
        index=SHAPE_OPTIONS.index(
            default_shape
        )
        if default_shape in SHAPE_OPTIONS
        else SHAPE_OPTIONS.index("なし")
    )


    # --------------------------------------------------------
    # 左側・右側の模様
    # --------------------------------------------------------

    col_left, col_right = st.columns(2)

    with col_left:

        left_pattern = st.selectbox(
            "左側の模様",
            PATTERN_OPTIONS,
            index=PATTERN_OPTIONS.index(
                default_left_pattern
            )
            if default_left_pattern in PATTERN_OPTIONS
            else PATTERN_OPTIONS.index("なし")
        )


    with col_right:

        right_pattern = st.selectbox(
            "右側の模様",
            PATTERN_OPTIONS,
            index=PATTERN_OPTIONS.index(
                default_right_pattern
            )
            if default_right_pattern in PATTERN_OPTIONS
            else PATTERN_OPTIONS.index("なし")
        )


    # ========================================================
    # 入力チェック
    # ========================================================

    validation_errors = []


    # 点数チェック
    if current_point_count < 2:

        validation_errors.append(
            "始点と終点を含め、2点以上クリックしてください。"
        )


    # 路線価チェック
    if land_price is None:

        validation_errors.append(
            "路線価を入力してください。"
        )


    # 記号チェック
    if symbol == "":

        validation_errors.append(
            "記号を入力してください。"
        )

    elif symbol not in list("ABCDEFG"):

        validation_errors.append(
            "記号はA～Gのいずれか1文字で入力してください。"
        )


    # エラー表示
    if len(validation_errors) > 0:

        for error in validation_errors:

            st.warning(error)


    # ========================================================
    # 登録 / 修正ボタン
    # ========================================================

    if st.session_state.editing_id is not None:

        button_text = "修正を確定"

    else:

        button_text = "アノテーションを登録"


    can_register = (
        current_point_count >= 2
        and land_price is not None
        and symbol in list("ABCDEFG")
    )


    if st.button(
        button_text,
        type="primary",
        disabled=not can_register,
        use_container_width=True
    ):

        # 現在の点を取得
        if st.session_state.editing_id is not None:

            polyline = [
                list(point)
                for point in st.session_state.edit_points
            ]

        else:

            polyline = [
                list(point)
                for point in st.session_state.current_points
            ]


        # 始点・終点
        start = list(polyline[0])
        end = list(polyline[-1])


        # アノテーションデータ
        new_data = {
            "start": start,
            "end": end,
            "polyline": polyline,
            "land_price": int(land_price),
            "symbol": symbol,
            "mark": {
                "shape": shape,
                "left_pattern": left_pattern,
                "right_pattern": right_pattern
            }
        }


        # ----------------------------------------------------
        # 修正
        # ----------------------------------------------------

        if st.session_state.editing_id is not None:

            for i, ann in enumerate(
                st.session_state.annotations
            ):

                if ann["id"] == st.session_state.editing_id:

                    st.session_state.annotations[i] = {
                        "id": ann["id"],
                        **new_data
                    }

                    break


            st.success(
                f"ID {st.session_state.editing_id} を修正しました。"
            )

            st.session_state.editing_id = None
            st.session_state.edit_points = []
            st.session_state.last_canvas_count = 0

            st.rerun()


        # ----------------------------------------------------
        # 新規登録
        # ----------------------------------------------------

        else:

            # 最大ID + 1
            if len(st.session_state.annotations) == 0:

                new_id = 1

            else:

                new_id = max(
                    ann["id"]
                    for ann in st.session_state.annotations
                ) + 1


            new_data["id"] = new_id

            st.session_state.annotations.append(
                new_data
            )

            st.session_state.current_points = []
            st.session_state.last_canvas_count = 0

            st.success(
                f"ID {new_id} を登録しました。"
            )

            st.rerun()


    # ========================================================
    # 登録済みアノテーション
    # ========================================================

    st.divider()

    st.subheader(
        f"登録済みアノテーション（{len(st.session_state.annotations)}件）"
    )


    if len(st.session_state.annotations) == 0:

        st.info(
            "まだアノテーションは登録されていません。"
        )

    else:

        # スクロール可能な領域
        registered_container = st.container(
            height=500,
            border=True
        )

        with registered_container:

            for ann in st.session_state.annotations:

                st.markdown(
                    f"### ID {ann['id']}"
                )

                st.write(
                    f"路線価：{ann['land_price']}"
                )

                st.write(
                    f"記号：{ann['symbol']}"
                )

                st.write(
                    f"形状：{ann['mark']['shape']}"
                )

                st.write(
                    f"左側の模様：{ann['mark']['left_pattern']}"
                )

                st.write(
                    f"右側の模様：{ann['mark']['right_pattern']}"
                )

                st.write(
                    f"始点：{ann['start']}"
                )

                st.write(
                    f"終点：{ann['end']}"
                )

                st.write(
                    f"ポリライン点数：{len(ann['polyline'])}"
                )


                col_edit, col_delete = st.columns(2)


                # ------------------------------------------------
                # 修正
                # ------------------------------------------------

                with col_edit:

                    if st.button(
                        "修正",
                        key=f"edit_{ann['id']}",
                        use_container_width=True
                    ):

                        st.session_state.editing_id = ann["id"]

                        st.session_state.edit_points = [
                            list(point)
                            for point in ann["polyline"]
                        ]

                        st.session_state.last_canvas_count = 0

                        st.rerun()


                # ------------------------------------------------
                # 削除
                # ------------------------------------------------

                with col_delete:

                    if st.button(
                        "削除",
                        key=f"delete_{ann['id']}",
                        use_container_width=True
                    ):

                        st.session_state.annotations = [
                            item
                            for item in st.session_state.annotations
                            if item["id"] != ann["id"]
                        ]

                        st.success(
                            f"ID {ann['id']} を削除しました。"
                        )

                        st.rerun()


                st.divider()


    # ========================================================
    # JSON保存
    # ========================================================

    st.divider()

    st.subheader("JSON保存")


    save_data = {
        "image_name": st.session_state.image_name,
        "image_width": st.session_state.image_width,
        "image_height": st.session_state.image_height,
        "annotations": st.session_state.annotations
    }


    json_string = json.dumps(
        save_data,
        ensure_ascii=False,
        indent=2
    )


    st.download_button(
        label="アノテーション結果をJSONで保存",
        data=json_string,
        file_name="annotations.json",
        mime="application/json",
        use_container_width=True
    )


    # ========================================================
    # JSON読み込み
    # ========================================================

    st.divider()

    st.subheader("JSON読み込み")


    json_file = st.file_uploader(
        "保存したJSONを選択してください",
        type=["json"],
        key="json_loader"
    )


    if json_file is not None:

        if st.button(
            "JSONを読み込む",
            use_container_width=True
        ):

            try:

                loaded_data = json.load(
                    json_file
                )


                # --------------------------------------------
                # 基本構造チェック
                # --------------------------------------------

                if "annotations" not in loaded_data:

                    st.error(
                        "JSONにannotationsがありません。"
                    )

                else:

                    # ----------------------------------------
                    # 画像情報の確認
                    # ----------------------------------------

                    json_image_name = loaded_data.get(
                        "image_name"
                    )

                    json_image_width = loaded_data.get(
                        "image_width"
                    )

                    json_image_height = loaded_data.get(
                        "image_height"
                    )


                    if (
                        json_image_width is not None
                        and json_image_height is not None
                    ):

                        if (
                            json_image_width != original_width
                            or
                            json_image_height != original_height
                        ):

                            st.warning(
                                "JSONに保存されている画像サイズと、"
                                "現在アップロードされている画像のサイズが異なります。"
                            )


                    # ----------------------------------------
                    # アノテーション読み込み
                    # ----------------------------------------

                    loaded_annotations = []

                    for ann in loaded_data["annotations"]:

                        # 最低限必要な項目
                        if "id" not in ann:
                            continue

                        if "polyline" not in ann:
                            continue

                        if "start" not in ann:
                            continue

                        if "end" not in ann:
                            continue

                        if "land_price" not in ann:
                            continue

                        if "symbol" not in ann:
                            continue

                        if "mark" not in ann:
                            continue


                        loaded_annotations.append(
                            ann
                        )


                    st.session_state.annotations = (
                        loaded_annotations
                    )

                    st.session_state.current_points = []
                    st.session_state.editing_id = None
                    st.session_state.edit_points = []
                    st.session_state.last_canvas_count = 0

                    st.success(
                        f"{len(loaded_annotations)}件のアノテーションを読み込みました。"
                    )

                    st.rerun()


            except Exception as e:

                st.error(
                    f"JSONの読み込みに失敗しました：{e}"
                )


else:

    st.info(
        "まず路線価図の画像をアップロードしてください。"
    )

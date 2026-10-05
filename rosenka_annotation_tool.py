import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
from PIL import Image, ImageDraw
from io import BytesIO
import json
import os
from pathlib import Path
from datetime import datetime


# =========================================================
# ページ設定
# =========================================================

st.set_page_config(
    page_title="路線価図アノテーションツール",
    layout="wide"
)

st.title("路線価図アノテーションツール")


# =========================================================
# Session State 初期化
# =========================================================

if "image_name" not in st.session_state:
    st.session_state.image_name = None

if "image_bytes" not in st.session_state:
    st.session_state.image_bytes = None

if "original_image" not in st.session_state:
    st.session_state.original_image = None

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

if "last_click" not in st.session_state:
    st.session_state.last_click = None

# ---------------------------------------------------------
# ボタン操作や登録直後に、
# 直前のクリックイベントが再取得された場合に
# そのクリックを無視するためのフラグ
# ---------------------------------------------------------

if "waiting_for_new_click" not in st.session_state:
    st.session_state.waiting_for_new_click = False


# =========================================================
# JSON保存
# =========================================================

def save_json():

    if st.session_state.image_name is None:
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
# 画像読み込み
# =========================================================

def load_image(uploaded_file):

    image_bytes = uploaded_file.getvalue()

    image = Image.open(
        BytesIO(image_bytes)
    ).convert("RGB")

    st.session_state.image_name = (
        uploaded_file.name
    )

    st.session_state.image_bytes = (
        image_bytes
    )

    st.session_state.original_image = (
        image
    )

    st.session_state.image_width = (
        image.width
    )

    st.session_state.image_height = (
        image.height
    )

    # アノテーション初期化
    st.session_state.annotations = []

    # 現在作成中のポリライン初期化
    st.session_state.current_points = []

    # クリック状態初期化
    st.session_state.last_click = None
    st.session_state.waiting_for_new_click = False

    # ズーム初期化
    st.session_state.zoom = 1.0


# =========================================================
# リサイズ画像
#
# 同じ画像・同じズーム率ならキャッシュを利用
# =========================================================

@st.cache_data(max_entries=20)
def resize_image(
    image_bytes,
    width,
    height,
    zoom
):

    image = Image.open(
        BytesIO(image_bytes)
    ).convert("RGB")

    new_width = max(
        1,
        int(width * zoom)
    )

    new_height = max(
        1,
        int(height * zoom)
    )

    resized = image.resize(
        (new_width, new_height),
        Image.Resampling.BILINEAR
    )

    return resized


# =========================================================
# 画像未読み込み画面
# =========================================================

if st.session_state.original_image is None:

    st.subheader(
        "路線価図画像を読み込む"
    )

    uploaded_file = st.file_uploader(
        "路線価図画像を選択してください",
        type=[
            "png",
            "jpg",
            "jpeg"
        ]
    )

    if uploaded_file is not None:

        st.write(
            f"選択中：**{uploaded_file.name}**"
        )

        if st.button(
            "画像を読み込む",
            type="primary",
            width="stretch"
        ):

            load_image(
                uploaded_file
            )

            st.rerun()

    else:

        st.info(
            "路線価図画像を選択してください。"
        )

    st.stop()


# =========================================================
# 画像情報
# =========================================================

st.caption(
    f"{st.session_state.image_name}　"
    f"{st.session_state.image_width} × "
    f"{st.session_state.image_height}px"
)


# =========================================================
# メインレイアウト
# =========================================================

map_col, control_col = st.columns(
    [4, 1]
)


# =========================================================
# 左側：画像
# =========================================================

with map_col:

    st.subheader("路線価図")


    # =====================================================
    # ズーム操作
    # =====================================================

    zoom_col1, zoom_col2, zoom_col3 = st.columns(
        [1, 2, 1]
    )


    # -----------------------------------------------------
    # ズームアウト
    # -----------------------------------------------------

    with zoom_col1:

        if st.button(
            "−",
            width="stretch"
        ):

            st.session_state.zoom = max(
                0.25,
                st.session_state.zoom - 0.25
            )

            st.rerun()


    # -----------------------------------------------------
    # ズーム率
    # -----------------------------------------------------

    with zoom_col2:

        st.markdown(
            f"""
            <div style="
                text-align:center;
                font-size:20px;
                padding-top:5px;
            ">
                <b>
                    {int(st.session_state.zoom * 100)}%
                </b>
            </div>
            """,
            unsafe_allow_html=True
        )


    # -----------------------------------------------------
    # ズームイン
    # -----------------------------------------------------

    with zoom_col3:

        if st.button(
            "＋",
            width="stretch"
        ):

            st.session_state.zoom = min(
                4.0,
                st.session_state.zoom + 0.25
            )

            st.rerun()


    # =====================================================
    # 画像をリサイズ
    # =====================================================

    display_image = resize_image(
        st.session_state.image_bytes,
        st.session_state.image_width,
        st.session_state.image_height,
        st.session_state.zoom
    ).copy()


    # =====================================================
    # 描画
    # =====================================================

    draw = ImageDraw.Draw(
        display_image
    )


    # =====================================================
    # 現在作成中のポリライン
    # =====================================================

    if len(
        st.session_state.current_points
    ) >= 1:

        display_points = [

            (
                int(
                    x *
                    st.session_state.zoom
                ),

                int(
                    y *
                    st.session_state.zoom
                )
            )

            for x, y
            in st.session_state.current_points
        ]


        # ポリライン
        if len(display_points) >= 2:

            draw.line(
                display_points,
                fill="red",
                width=max(
                    2,
                    int(
                        3 *
                        st.session_state.zoom
                    )
                )
            )


        # クリックした点
        radius = max(
            4,
            int(
                5 *
                st.session_state.zoom
            )
        )


        for x, y in display_points:

            draw.ellipse(
                (
                    x - radius,
                    y - radius,
                    x + radius,
                    y + radius
                ),
                fill="blue",
                outline="white",
                width=max(
                    1,
                    int(
                        2 *
                        st.session_state.zoom
                    )
                )
            )


    # =====================================================
    # 登録済みアノテーション
    # =====================================================

    for annotation in (
        st.session_state.annotations
    ):

        points = annotation.get(
            "polyline_px",
            []
        )

        if len(points) < 1:
            continue


        display_points = [

            (
                int(
                    x *
                    st.session_state.zoom
                ),

                int(
                    y *
                    st.session_state.zoom
                )
            )

            for x, y
            in points
        ]


        # ポリライン
        if len(display_points) >= 2:

            draw.line(
                display_points,
                fill="red",
                width=max(
                    2,
                    int(
                        3 *
                        st.session_state.zoom
                    )
                )
            )


        # 始点
        x, y = display_points[0]

        radius = max(
            5,
            int(
                6 *
                st.session_state.zoom
            )
        )


        draw.ellipse(
            (
                x - radius,
                y - radius,
                x + radius,
                y + radius
            ),
            fill="red",
            outline="white",
            width=2
        )


        # ID
        draw.text(
            (
                x + radius + 3,
                y - radius - 3
            ),
            str(
                annotation["id"]
            ),
            fill="red"
        )


    # =====================================================
    # 画像クリック
    # =====================================================

    click = streamlit_image_coordinates(
        display_image,
        key="rosenka_image"
    )


    # =====================================================
    # クリック処理
    # =====================================================

    if click is not None:

        click_x = click["x"]
        click_y = click["y"]


        # -------------------------------------------------
        # 表示画像座標
        # ↓
        # 元画像座標
        # -------------------------------------------------

        original_x = int(
            click_x /
            st.session_state.zoom
        )

        original_y = int(
            click_y /
            st.session_state.zoom
        )


        current_click = (
            original_x,
            original_y
        )


        # =================================================
        # ボタン操作・登録直後
        #
        # 直前のクリックが再取得された場合は無視
        # =================================================

        if st.session_state.waiting_for_new_click:

            # 同じクリックなら無視
            if (
                st.session_state.last_click
                == current_click
            ):

                pass

            # 新しい場所をクリックした場合
            else:

                st.session_state.waiting_for_new_click = False

                st.session_state.last_click = (
                    current_click
                )

                st.session_state.current_points.append(
                    [
                        original_x,
                        original_y
                    ]
                )

                st.rerun()


        # =================================================
        # 通常のクリック
        # =================================================

        elif (
            st.session_state.last_click
            != current_click
        ):

            st.session_state.last_click = (
                current_click
            )

            st.session_state.current_points.append(
                [
                    original_x,
                    original_y
                ]
            )

            st.rerun()


# =========================================================
# 右側：アノテーション操作
# =========================================================

with control_col:

    st.subheader(
        "アノテーション"
    )


    # =====================================================
    # 現在の点数
    # =====================================================

    st.write(
        f"現在の点数："
        f"**{len(st.session_state.current_points)}**"
    )


    # =====================================================
    # 現在の座標
    # =====================================================

    if st.session_state.current_points:

        with st.expander(
            "現在の座標",
            expanded=False
        ):

            st.json(
                st.session_state.current_points
            )


    # =====================================================
    # 1点戻す
    # =====================================================

    if st.button(
        "1点戻す",
        width="stretch"
    ):

        if st.session_state.current_points:

            # 最後の点を削除
            st.session_state.current_points.pop()

            # Streamlitの再実行時に
            # 直前のクリックを再登録しない
            st.session_state.waiting_for_new_click = True

            st.rerun()


    # =====================================================
    # 現在の点をクリア
    # =====================================================

    if st.button(
        "現在の点をクリア",
        width="stretch"
    ):

        # 全点削除
        st.session_state.current_points = []

        # 直前のクリックイベントを
        # 次の新しいクリックまで無視
        st.session_state.waiting_for_new_click = True

        st.rerun()


    st.divider()


    # =====================================================
    # 路線価
    # =====================================================

    road_value = st.text_input(
        "路線価",
        placeholder="例：120"
    )


    # =====================================================
    # 記号
    # =====================================================

    symbol = st.text_input(
        "記号",
        placeholder="例：A"
    )


    # =====================================================
    # アノテーション登録
    # =====================================================

    if st.button(
        "アノテーション登録",
        type="primary",
        width="stretch"
    ):

        points = (
            st.session_state.current_points
        )


        # -------------------------------------------------
        # 点数チェック
        # -------------------------------------------------

        if len(points) < 2:

            st.warning(
                "2点以上クリックしてください。"
            )


        # -------------------------------------------------
        # 路線価チェック
        # -------------------------------------------------

        elif road_value == "":

            st.warning(
                "路線価を入力してください。"
            )


        # -------------------------------------------------
        # 登録
        # -------------------------------------------------

        else:

            annotation_id = (
                len(
                    st.session_state.annotations
                ) + 1
            )


            annotation = {

                "id":
                    annotation_id,

                "road_value":
                    road_value,

                "symbol":
                    symbol,

                "polyline_px":
                    points.copy(),

                "start_point_px":
                    points[0],

                "end_point_px":
                    points[-1],

                "created_at":
                    datetime.now().isoformat()
            }


            # ---------------------------------------------
            # アノテーション登録
            # ---------------------------------------------

            st.session_state.annotations.append(
                annotation
            )


            # ---------------------------------------------
            # ★重要
            #
            # 次のアノテーションは0点から開始
            # ---------------------------------------------

            st.session_state.current_points = []


            # ---------------------------------------------
            # 登録直前の終点クリックが
            # 再取得されても、
            # 次の始点にしない
            # ---------------------------------------------

            st.session_state.waiting_for_new_click = True


            # ---------------------------------------------
            # 自動保存
            # ---------------------------------------------

            save_json()


            st.success(
                f"ID {annotation_id} を登録しました。"
            )


            st.rerun()


    st.divider()


    # =====================================================
    # 登録済みアノテーション
    # =====================================================

    st.subheader(
        f"登録済み（{len(st.session_state.annotations)}件）"
    )


    if not st.session_state.annotations:

        st.write(
            "まだ登録されていません。"
        )


    else:

        # -------------------------------------------------
        # 一覧をスクロール可能な枠にする
        # -------------------------------------------------

        with st.container(
            height=500,
            border=True
        ):

            for annotation in (
                st.session_state.annotations
            ):

                st.markdown(
                    f"**ID {annotation['id']}**"
                )

                st.write(
                    f"路線価："
                    f"{annotation['road_value']}"
                )

                st.write(
                    f"記号："
                    f"{annotation['symbol']}"
                )

                st.write(
                    f"点数："
                    f"{len(annotation['polyline_px'])}点"
                )


                # -----------------------------------------
                # 削除ボタン
                # -----------------------------------------

                if st.button(
                    f"ID {annotation['id']} を削除",
                    key=f"delete_{annotation['id']}",
                    width="stretch"
                ):

                    st.session_state.annotations = [

                        a

                        for a
                        in st.session_state.annotations

                        if a["id"]
                        != annotation["id"]
                    ]


                    # -------------------------------------
                    # IDを1から振り直す
                    # -------------------------------------

                    for i, a in enumerate(
                        st.session_state.annotations,
                        start=1
                    ):

                        a["id"] = i


                    # -------------------------------------
                    # JSON保存
                    # -------------------------------------

                    save_json()


                    st.rerun()


                st.divider()


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

        width="stretch"
    )


    st.divider()


    # =====================================================
    # 別の画像を読み込む
    # =====================================================

    if st.button(
        "別の画像を読み込む",
        width="stretch"
    ):

        st.session_state.image_name = None

        st.session_state.image_bytes = None

        st.session_state.original_image = None

        st.session_state.image_width = 0

        st.session_state.image_height = 0

        st.session_state.annotations = []

        st.session_state.current_points = []

        st.session_state.last_click = None

        st.session_state.waiting_for_new_click = False

        st.session_state.zoom = 1.0

        st.rerun()


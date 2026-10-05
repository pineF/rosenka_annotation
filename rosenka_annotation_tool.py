```python
import streamlit as st
from PIL import Image
import json
import io
import base64
from datetime import datetime


# ============================================================
# ページ設定
# ============================================================

st.set_page_config(
    page_title="路線価アノテーションツール",
    page_icon="🗺️",
    layout="wide"
)


# ============================================================
# CSS
# ============================================================

st.markdown(
    """
    <style>
    .annotation-info {
        padding: 10px;
        border-radius: 5px;
        background-color: #f0f2f6;
        margin-bottom: 10px;
    }

    .stButton button {
        width: 100%;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# ============================================================
# Session State 初期化
# ============================================================

if "annotations" not in st.session_state:
    st.session_state.annotations = []

if "current_points" not in st.session_state:
    st.session_state.current_points = []

if "image" not in st.session_state:
    st.session_state.image = None

if "image_name" not in st.session_state:
    st.session_state.image_name = None


# ============================================================
# タイトル
# ============================================================

st.title("🗺️ 路線価画像アノテーションツール")

st.markdown(
    """
    路線価図の画像上で、**路線価を表す矢印の位置と、それに対応する路線価・記号**
    をアノテーションするためのツールです。

    ### アノテーション方法

    1. 路線価画像をアップロード
    2. 矢印の **始点 → 経由点 → 終点** の順番にクリック
    3. 矢印に対応する **路線価** を入力
    4. **路線価の記号**を選択
    5. 「アノテーションを追加」を押す
    6. 最後にJSONをダウンロード
    """
)


# ============================================================
# サイドバー
# ============================================================

with st.sidebar:

    st.header("画像")

    uploaded_file = st.file_uploader(
        "路線価画像をアップロード",
        type=["png", "jpg", "jpeg", "webp"]
    )

    if uploaded_file is not None:

        image = Image.open(uploaded_file).convert("RGB")

        st.session_state.image = image
        st.session_state.image_name = uploaded_file.name

        st.write(f"画像サイズ: {image.width} × {image.height}")

    st.divider()

    st.header("アノテーション")

    if st.session_state.image is not None:

        st.write(
            f"登録済み: {len(st.session_state.annotations)} 件"
        )

        if st.button("現在のアノテーションを全削除"):
            st.session_state.annotations = []
            st.session_state.current_points = []
            st.rerun()

    st.divider()

    st.header("JSON")

    if st.session_state.annotations:

        json_data = {
            "image": st.session_state.image_name,
            "image_width": st.session_state.image.width,
            "image_height": st.session_state.image.height,
            "annotations": st.session_state.annotations
        }

        json_string = json.dumps(
            json_data,
            ensure_ascii=False,
            indent=2
        )

        st.download_button(
            label="JSONをダウンロード",
            data=json_string,
            file_name="rosenka_annotations.json",
            mime="application/json"
        )


# ============================================================
# 画像がアップロードされていない場合
# ============================================================

if st.session_state.image is None:

    st.info("左側のサイドバーから路線価画像をアップロードしてください。")

    st.stop()


# ============================================================
# 画像表示用HTML
# ============================================================

def image_to_base64(image):

    buffer = io.BytesIO()

    image.save(buffer, format="PNG")

    return base64.b64encode(
        buffer.getvalue()
    ).decode()


# ============================================================
# 現在のアノテーション情報
# ============================================================

st.subheader("1. 矢印をクリックして座標を指定")

st.markdown(
    """
    **直線の場合**

    `始点 → 終点`

    **カーブしている場合**

    `始点 → 経由点 → 経由点 → 終点`

    の順番でクリックしてください。
    """
)


# ============================================================
# 画像上のクリック処理
# ============================================================

image = st.session_state.image

image_b64 = image_to_base64(image)


# JavaScript + Streamlit component風のクリック処理
# ------------------------------------------------------------

component_html = f"""
<div style="width:100%;">

    <div
        id="image-container"
        style="
            position:relative;
            width:100%;
            overflow:auto;
            border:1px solid #cccccc;
            background:#eeeeee;
        "
    >

        <img
            id="main-image"
            src="data:image/png;base64,{image_b64}"
            style="
                width:100%;
                height:auto;
                display:block;
                cursor:crosshair;
            "
        />

        <canvas
            id="canvas"
            style="
                position:absolute;
                left:0;
                top:0;
                width:100%;
                height:100%;
                pointer-events:none;
            "
        >
        </canvas>

    </div>

    <div style="margin-top:10px;">
        <button
            id="clear-button"
            style="
                padding:8px 15px;
                margin-right:10px;
                cursor:pointer;
            "
        >
            現在の点をクリア
        </button>

        <span id="point-info">
            クリック待機中
        </span>
    </div>

</div>


<script>

const image = document.getElementById("main-image");
const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");
const info = document.getElementById("point-info");
const clearButton = document.getElementById("clear-button");

let points = [];


function resizeCanvas() {{

    canvas.width = image.clientWidth;
    canvas.height = image.clientHeight;

    draw();

}}


function draw() {{

    ctx.clearRect(
        0,
        0,
        canvas.width,
        canvas.height
    );

    if (points.length === 0) {{
        return;
    }}

    // 線を描画
    ctx.beginPath();

    ctx.moveTo(
        points[0].x * canvas.width,
        points[0].y * canvas.height
    );

    for (let i = 1; i < points.length; i++) {{

        ctx.lineTo(
            points[i].x * canvas.width,
            points[i].y * canvas.height
        );

    }}

    ctx.strokeStyle = "red";
    ctx.lineWidth = 3;
    ctx.stroke();


    // 点を描画
    for (let i = 0; i < points.length; i++) {{

        const x = points[i].x * canvas.width;
        const y = points[i].y * canvas.height;

        ctx.beginPath();

        ctx.arc(
            x,
            y,
            5,
            0,
            Math.PI * 2
        );

        ctx.fillStyle = "blue";
        ctx.fill();

        ctx.strokeStyle = "white";
        ctx.lineWidth = 2;
        ctx.stroke();

        // 番号
        ctx.fillStyle = "black";
        ctx.font = "bold 14px Arial";

        ctx.fillText(
            i + 1,
            x + 8,
            y - 8
        );
    }}

    info.innerText =
        points.length + " 点選択中";

}}


image.addEventListener("load", resizeCanvas);

window.addEventListener("resize", resizeCanvas);


image.addEventListener("click", function(event) {{

    const rect = image.getBoundingClientRect();

    const x = event.clientX - rect.left;
    const y = event.clientY - rect.top;

    // 画像サイズに対する割合
    const normalizedX = x / rect.width;
    const normalizedY = y / rect.height;

    points.push({{
        x: normalizedX,
        y: normalizedY
    }});

    draw();

}});


clearButton.addEventListener("click", function() {{

    points = [];

    draw();

    info.innerText = "現在の点をクリアしました";

}});


resizeCanvas();

</script>
"""


# Streamlit HTML表示
st.components.v1.html(
    component_html,
    height=700,
    scrolling=True
)


# ============================================================
# 座標入力
# ============================================================

st.subheader("2. 矢印の座標")

st.warning(
    """
    現在のバージョンでは、画像上のクリック座標を
    ブラウザ側で取得して表示する基本機能を実装しています。
    """
)


# ============================================================
# 手動座標入力
# ============================================================

st.markdown("### 座標を入力")

st.caption(
    "画像左上を (0, 0)、右下を (画像幅, 画像高さ) とするピクセル座標です。"
)


if "manual_points" not in st.session_state:
    st.session_state.manual_points = []


col1, col2 = st.columns(2)

with col1:

    x = st.number_input(
        "X座標",
        min_value=0,
        max_value=image.width,
        value=0,
        step=1
    )

with col2:

    y = st.number_input(
        "Y座標",
        min_value=0,
        max_value=image.height,
        value=0,
        step=1
    )


if st.button("座標を追加"):

    st.session_state.manual_points.append(
        [int(x), int(y)]
    )

    st.rerun()


if st.session_state.manual_points:

    st.write("現在の座標")

    for i, point in enumerate(
        st.session_state.manual_points
    ):

        st.write(
            f"{i + 1}: ({point[0]}, {point[1]})"
        )


    if st.button("座標をすべてクリア"):

        st.session_state.manual_points = []

        st.rerun()


# ============================================================
# 路線価情報
# ============================================================

st.divider()

st.subheader("3. 路線価情報")

col1, col2 = st.columns(2)


with col1:

    road_value = st.text_input(
        "路線価",
        placeholder="例：120"
    )


with col2:

    symbol = st.selectbox(
        "路線価の記号",
        [
            "なし",
            "A",
            "B",
            "C",
            "D",
            "E",
            "F",
            "G",
            "H",
            "その他"
        ]
    )


if symbol == "その他":

    symbol_other = st.text_input(
        "記号を入力"
    )

else:

    symbol_other = ""


# ============================================================
# アノテーション追加
# ============================================================

st.divider()

st.subheader("4. アノテーションを登録")


if st.button(
    "アノテーションを追加",
    type="primary"
):

    if not road_value:

        st.error("路線価を入力してください。")

    elif len(st.session_state.manual_points) < 2:

        st.error(
            "矢印には最低2点（始点・終点）が必要です。"
        )

    else:

        final_symbol = (
            symbol_other
            if symbol == "その他"
            else symbol
        )

        points = st.session_state.manual_points

        annotation = {

            "id": len(
                st.session_state.annotations
            ) + 1,

            "road_value": road_value,

            "symbol": final_symbol,

            "polyline_px": points,

            "start_point_px": points[0],

            "end_point_px": points[-1],

            "created_at": datetime.now().isoformat()

        }


        st.session_state.annotations.append(
            annotation
        )


        # 次のアノテーションに備えてクリア
        st.session_state.manual_points = []


        st.success(
            f"アノテーション {annotation['id']} を登録しました。"
        )

        st.rerun()


# ============================================================
# 登録済みアノテーション
# ============================================================

st.divider()

st.subheader("5. 登録済みアノテーション")


if not st.session_state.annotations:

    st.info(
        "まだアノテーションは登録されていません。"
    )

else:

    for annotation in st.session_state.annotations:

        with st.expander(
            f"ID {annotation['id']} "
            f"｜ 路線価 {annotation['road_value']} "
            f"｜ 記号 {annotation['symbol']}"
        ):

            st.json(annotation)


# ============================================================
# JSONプレビュー
# ============================================================

st.divider()

st.subheader("JSONプレビュー")


if st.session_state.annotations:

    output_data = {

        "image": st.session_state.image_name,

        "image_width": image.width,

        "image_height": image.height,

        "annotations":
            st.session_state.annotations

    }


    st.json(output_data)

else:

    st.info(
        "アノテーションを登録するとJSONが表示されます。"
    )
```

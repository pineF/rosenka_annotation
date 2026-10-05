import json
import streamlit as st
from PIL import Image, ImageDraw, ImageFont
from streamlit_drawable_canvas import st_canvas

# ------------------------------------------------------------------------------
# 1. ページ初期設定 & セッション状態の初期化
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="路線価アノテーションツール", layout="wide", initial_sidebar_state="expanded"
)

if "annotations" not in st.session_state:
    st.session_state.annotations = []  # アノテーションリスト
if "current_points" not in st.session_state:
    st.session_state.current_points = []  # 現在描画中のポリライン（元画像座標系 [[x, y], ...]）
if "editing_id" not in st.session_state:
    st.session_state.editing_id = None  # 修正中のアノテーションID
if "next_id" not in st.session_state:
    st.session_state.next_id = 1  # 新規アノテーションIDカウンタ
if "json_load_warning" not in st.session_state:
    st.session_state.json_load_warning = None

st.title("📍 路線価アノテーションツール")

# ------------------------------------------------------------------------------
# 2. サイドバー：画像・JSONのアップロード、拡大縮小、JSONダウンロード
# ------------------------------------------------------------------------------
st.sidebar.header("📁 ファイル操作 / 設定")

# 画像アップロード
uploaded_image = st.sidebar.file_uploader(
    "1. 路線価図画像をアップロード", type=["png", "jpg", "jpeg"]
)

# ズーム倍率設定（デフォルト 100%）
zoom_percent = st.sidebar.slider(
    "画像表示倍率 (%)", min_value=10, max_value=300, value=100, step=10
)
zoom_scale = zoom_percent / 100.0

st.sidebar.markdown("---")

# JSONの読み込み機能
uploaded_json = st.sidebar.file_uploader("2. 既存JSONを読み込み", type=["json"])
if uploaded_json is not None:
    if st.sidebar.button("JSONデータを読み込んで復元"):
        try:
            data = json.load(uploaded_json)
            loaded_annotations = data.get("annotations", [])
            if not isinstance(loaded_annotations, list):
                raise ValueError("annotations は配列である必要があります。")
            st.session_state.annotations = loaded_annotations

            # 次のIDの決定
            if loaded_annotations:
                max_id = max(ann.get("id", 0) for ann in loaded_annotations)
                st.session_state.next_id = max_id + 1
            else:
                st.session_state.next_id = 1

            # 画像サイズのチェック
            st.session_state.json_load_warning = None
            if uploaded_image is not None:
                img_temp = Image.open(uploaded_image)
                w_orig, h_orig = img_temp.size
                if data.get("image_width") != w_orig or data.get(
                    "image_height"
                ) != h_orig:
                    st.session_state.json_load_warning = (
                        "⚠️ 警告: JSON内の画像サイズとアップロード中の画像サイズが異なります。"
                    )

            st.sidebar.success(
                f"JSONをロードしました。（{len(loaded_annotations)}件）"
            )
            st.rerun()
        except Exception as e:
            st.sidebar.error(f"JSON読み込みエラー: {e}")

st.sidebar.markdown("---")

# 画像がロードされている場合のみ動作
if uploaded_image is not None:
    # 画像取得と元サイズ保持
    image_original = Image.open(uploaded_image).convert("RGB")
    orig_w, orig_h = image_original.size
    image_name = uploaded_image.name
    if st.session_state.json_load_warning:
        st.warning(st.session_state.json_load_warning)

    # 表示用サイズ
    disp_w = int(orig_w * zoom_scale)
    disp_h = int(orig_h * zoom_scale)

    # --------------------------------------------------------------------------
    # 3. Canvas背景画像の生成（既存アノテーションの「線描画」含む）
    # --------------------------------------------------------------------------
    # 元画像コピーに既存線を描画（元画像座標で高解像度描画）
    canvas_bg_orig = image_original.copy()
    draw = ImageDraw.Draw(canvas_bg_orig)

    # フォント設定（簡易的なフォント）
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for ann in st.session_state.annotations:
        ann_id = ann["id"]
        pts = [tuple(p) for p in ann["polyline"]]

        # 修正対象は「青線」、その他登録済みは「赤線」
        if (
            st.session_state.editing_id is not None
            and ann_id == st.session_state.editing_id
        ):
            line_color = (0, 100, 255)  # 青
            width = 5
        else:
            line_color = (255, 0, 0)  # 赤
            width = 4

        # ポリラインと頂点の描画
        if len(pts) > 1:
            draw.line(pts, fill=line_color, width=width)
        for pt in pts:
            r = 5
            draw.ellipse(
                [pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r],
                fill=line_color,
                outline=(255, 255, 255),
            )

        # IDのテキスト表示
        if pts:
            start_p = pts[0]
            draw.text(
                (start_p[0] + 8, start_p[1] - 8),
                f"ID:{ann_id}",
                fill=(0, 0, 0),
                font=font,
            )

    # 現在修正中・作成中のポリラインを一時描画
    if st.session_state.current_points:
        curr_pts = [tuple(p) for p in st.session_state.current_points]
        current_color = (
            (0, 100, 255)
            if st.session_state.editing_id is not None
            else (0, 200, 0)
        )
        if len(curr_pts) > 1:
            draw.line(curr_pts, fill=current_color, width=4)
        for pt in curr_pts:
            r = 6
            draw.ellipse(
                [pt[0] - r, pt[1] - r, pt[0] + r, pt[1] + r],
                fill=current_color,
                outline=(0, 0, 0),
            )

    # 表示用に縮小・拡大リサイズ
    canvas_bg_resized = canvas_bg_orig.resize(
        (disp_w, disp_h), Image.Resampling.LANCZOS
    )

    # --------------------------------------------------------------------------
    # 4. メインレイアウト（左：画像・描画領域 / 右：属性入力 & データ管理）
    # --------------------------------------------------------------------------
    col_canvas, col_form = st.columns([7, 5])

    with col_canvas:
        st.subheader("🖼️ 画像描画エリア")
        st.caption(
            "画像上をクリックしてポリラインを作成します。（ズーム時はスクロールして閲覧可能）"
        )

        # 大きな画像でも表示領域からはみ出した部分を確認できるようにする。
        with st.container(height=700, border=True):
            canvas_result = st_canvas(
                fill_color="rgba(255, 165, 0, 0.3)",
                stroke_width=2,
                stroke_color="#000000",
                background_image=canvas_bg_resized,
                update_streamlit=True,
                height=disp_h,
                width=disp_w,
                drawing_mode="point",
                # クリックのたびにkeyを変えるとキャンバスが再生成され、
                # ズーム時のスクロール位置が先頭に戻るため、表示条件だけで固定する。
                key=f"canvas_{zoom_percent}_{st.session_state.editing_id}",
            )

        # キャンバスクリック時の点の検出と座標変換（表示座標 -> 元画像座標）
        if (
            canvas_result.json_data is not None
            and "objects" in canvas_result.json_data
        ):
            objects = canvas_result.json_data["objects"]
            if len(objects) > 0:
                last_obj = objects[-1]
                click_x_disp = last_obj["left"]
                click_y_disp = last_obj["top"]

                # 元画像座標に逆算変換
                orig_x = int(round(click_x_disp / zoom_scale))
                orig_y = int(round(click_y_disp / zoom_scale))

                # 重複登録を防ぐ処理（最後の点と極端に同じでなければ追加）
                if (
                    not st.session_state.current_points
                    or st.session_state.current_points[-1] != [orig_x, orig_y]
                ):
                    st.session_state.current_points.append([orig_x, orig_y])
                    st.rerun()

        # ポリライン作成操作用ボタン
        c_btn1, c_btn2 = st.columns(2)
        with c_btn1:
            if st.button("↩️ 1つ戻す（最後の点を削除）"):
                if st.session_state.current_points:
                    st.session_state.current_points.pop()
                    st.rerun()
        with c_btn2:
            if st.button("🗑️ すべてクリア"):
                st.session_state.current_points = []
                st.rerun()

        # クリックポイント一覧表示
        st.write(
            f"**現在のポリライン点数**: {len(st.session_state.current_points)} 点"
        )
        if st.session_state.current_points:
            st.json(st.session_state.current_points)

    with col_form:
        st.subheader(
            "📝 アノテーション入力"
            if st.session_state.editing_id is None
            else f"✏️ アノテーション修正 (ID: {st.session_state.editing_id})"
        )

        # 左右定義ガイド表示
        st.info(
            """
        **左右の定義**（始点から終点へ向かって見たときの左右）:  
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **左側**  
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ↓  
        **始点** ●────────────● **終点**  
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; ↑  
        &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; **右側**
        """
        )

        # 修正モード時の初期値設定
        default_price = 0
        default_symbol = ""
        default_shape = "なし"
        default_l_pattern = "なし"
        default_r_pattern = "なし"

        if st.session_state.editing_id is not None:
            edit_item = next(
                (
                    item
                    for item in st.session_state.annotations
                    if item["id"] == st.session_state.editing_id
                ),
                None,
            )
            if edit_item:
                default_price = int(edit_item.get("land_price", 0))
                default_symbol = edit_item.get("symbol", "")
                mark_info = edit_item.get("mark", {})
                default_shape = mark_info.get("shape", "なし")
                default_l_pattern = mark_info.get("left_pattern", "なし")
                default_r_pattern = mark_info.get("right_pattern", "なし")

        # 入力フォーム
        form_key = (
            f"annotation_form_edit_{st.session_state.editing_id}"
            if st.session_state.editing_id is not None
            else "annotation_form_new"
        )
        with st.form(form_key):
            land_price = st.number_input(
                "路線価（必須・数値）", min_value=0, value=default_price, step=1000
            )

            symbol_raw = st.text_input(
                "記号 (A～Gの1文字)",
                value=default_symbol,
                max_chars=1,
                help="小文字は自動で大文字化されます",
            )

            shape_options = [
                "六角形",
                "楕円",
                "八角形",
                "正円",
                "縦に潰れたひし形",
                "横長の長方形",
                "なし",
            ]
            shape_idx = (
                shape_options.index(default_shape)
                if default_shape in shape_options
                else 6
            )
            shape = st.selectbox("マーク形状", shape_options, index=shape_idx)

            pattern_options = ["斜線", "黒塗り", "なし"]

            l_idx = (
                pattern_options.index(default_l_pattern)
                if default_l_pattern in pattern_options
                else 2
            )
            left_pattern = st.selectbox(
                "左側模様", pattern_options, index=l_idx
            )

            r_idx = (
                pattern_options.index(default_r_pattern)
                if default_r_pattern in pattern_options
                else 2
            )
            right_pattern = st.selectbox(
                "右側模様", pattern_options, index=r_idx
            )

            btn_label = (
                "登録"
                if st.session_state.editing_id is None
                else "修正を保存"
            )
            submitted = st.form_submit_button(btn_label)

        # 登録・保存処理
        if submitted:
            symbol = symbol_raw.strip().upper()
            valid = True

            # バリデーションチェック
            if len(st.session_state.current_points) < 2:
                st.error(
                    "❌ ポリラインは2点以上指定する必要があります（クリックして点を追加してください）。"
                )
                valid = False

            if land_price <= 0:
                st.error("❌ 路線価を入力してください（0より大きい数値）。")
                valid = False

            if symbol not in ["A", "B", "C", "D", "E", "F", "G"]:
                st.error("❌ 記号は A～G の1文字である必要があります。")
                valid = False

            if valid:
                pts = st.session_state.current_points
                start_pt = pts[0]
                end_pt = pts[-1]

                annotation_data = {
                    "id": (
                        st.session_state.editing_id
                        if st.session_state.editing_id is not None
                        else st.session_state.next_id
                    ),
                    "start": start_pt,
                    "end": end_pt,
                    "polyline": pts,
                    "land_price": land_price,
                    "symbol": symbol,
                    "mark": {
                        "shape": shape,
                        "left_pattern": left_pattern,
                        "right_pattern": right_pattern,
                    },
                }

                if st.session_state.editing_id is not None:
                    # 修正適用
                    idx = next(
                        i
                        for i, a in enumerate(st.session_state.annotations)
                        if a["id"] == st.session_state.editing_id
                    )
                    st.session_state.annotations[idx] = annotation_data
                    st.success(
                        f"ID:{st.session_state.editing_id} のアノテーションを更新しました！"
                    )
                    st.session_state.editing_id = None
                else:
                    # 新規追加
                    st.session_state.annotations.append(annotation_data)
                    st.session_state.next_id += 1
                    st.success("アノテーションを登録しました！")

                # 入力リセット
                st.session_state.current_points = []
                st.rerun()

        if st.session_state.editing_id is not None:
            if st.button("❌ 修正をキャンセル"):
                st.session_state.editing_id = None
                st.session_state.current_points = []
                st.rerun()

        st.markdown("---")

        # ----------------------------------------------------------------------
        # 5. 登録済みアノテーション一覧表示 & 修正/削除ボタン
        # ----------------------------------------------------------------------
        count = len(st.session_state.annotations)
        st.subheader(f"📋 登録済みアノテーション（{count}件）")

        # スクロール可能領域の構成
        with st.container(height=350, border=True):
            if count == 0:
                st.info("登録済みのデータはありません。")
            else:
                for ann in st.session_state.annotations:
                    with st.expander(
                        f"ID: {ann['id']} | 路線価: {ann['land_price']} | 記号: {ann['symbol']}",
                        expanded=True,
                    ):
                        col_a, col_b = st.columns([3, 2])
                        with col_a:
                            st.write(f"**ID**: {ann['id']}")
                            st.write(f"**路線価**: {ann['land_price']}")
                            st.write(f"**記号**: {ann['symbol']}")
                            st.write(f"**形状**: {ann['mark']['shape']}")
                            st.write(
                                f"**左側模様**: {ann['mark']['left_pattern']}"
                            )
                            st.write(
                                f"**右側模様**: {ann['mark']['right_pattern']}"
                            )
                            st.write(f"**始点**: {ann['start']}")
                            st.write(f"**終点**: {ann['end']}")
                            st.write(
                                f"**ポリライン点数**: {len(ann['polyline'])} 点"
                            )

                        with col_b:
                            if st.button("✏️ 修正", key=f"edit_{ann['id']}"):
                                st.session_state.editing_id = ann["id"]
                                st.session_state.current_points = list(
                                    ann["polyline"]
                                )
                                st.rerun()

                            if st.button("🗑️ 削除", key=f"del_{ann['id']}"):
                                st.session_state.annotations = [
                                    a
                                    for a in st.session_state.annotations
                                    if a["id"] != ann["id"]
                                ]
                                if (
                                    st.session_state.editing_id == ann["id"]
                                ):  # 修正中のものが削除された場合
                                    st.session_state.editing_id = None
                                    st.session_state.current_points = []
                                st.rerun()

    # --------------------------------------------------------------------------
    # 6. JSON保存ボタン（サイドバーまたは最下部）
    # --------------------------------------------------------------------------
    st.sidebar.markdown("---")
    output_json_data = {
        "image_name": image_name,
        "image_width": orig_w,
        "image_height": orig_h,
        "annotations": st.session_state.annotations,
    }

    json_str = json.dumps(output_json_data, ensure_ascii=False, indent=2)

    st.sidebar.download_button(
        label="💾 JSONとして保存（ダウンロード）",
        data=json_str,
        file_name="annotations.json",
        mime="application/json",
    )

else:
    st.info(
        "👈 左側のサイドバーから路線価図の画像ファイルをアップロードしてください。"
    )

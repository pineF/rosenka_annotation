import base64
import io
import json
from typing import Any

import folium
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
import streamlit as st
from streamlit.errors import StreamlitInvalidLayoutContextError
from streamlit_folium import st_folium


IMAGE_TILE_SIZE = 1024
IMAGE_PREVIEW_MAX_DIMENSION = 6144


def rerun_fragment() -> None:
    """Use a fragment rerun where supported, with a safe fallback."""
    try:
        st.rerun(scope="fragment")
    except StreamlitInvalidLayoutContextError:
        st.rerun()


@st.cache_data(show_spinner=False)
def load_image(
    image_bytes: bytes,
) -> tuple[bytes, int, int]:
    """Load image with PIL and create a high-quality anti-aliased preview."""
    with Image.open(io.BytesIO(image_bytes)) as img:
        width, height = img.size
        scale = max(
            1,
            (width + IMAGE_PREVIEW_MAX_DIMENSION - 1) // IMAGE_PREVIEW_MAX_DIMENSION,
            (height + IMAGE_PREVIEW_MAX_DIMENSION - 1) // IMAGE_PREVIEW_MAX_DIMENSION,
        )
        if scale > 1:
            preview_w = max(1, width // scale)
            preview_h = max(1, height // scale)
            # 2値画像（1-bit）はグレースケール変換してBOXリサンプルすることで細い線が消失しない
            if img.mode == "1":
                img_conv = img.convert("L")
                preview = img_conv.resize((preview_w, preview_h), Image.Resampling.BOX)
            else:
                preview = img.resize((preview_w, preview_h), Image.Resampling.BILINEAR)
        else:
            preview = img

        output = io.BytesIO()
        preview.save(output, format="PNG", optimize=True)
        return output.getvalue(), width, height


def _png_size(image_bytes: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(image_bytes)) as img:
        return img.size


def crop_highres_region(
    image_bytes: bytes,
    wld_vals: list[float],
    crop_bounds: tuple[float, float, float, float],
) -> tuple[bytes | None, tuple[float, float, float, float] | None]:
    """Crop a sub-region at original 100% resolution for crisp annotation."""
    a, d, b, e, c, f = wld_vals
    south, west, north, east = crop_bounds

    col_1 = int((west - c) / a + 0.5)
    col_2 = int((east - c) / a + 0.5)
    row_1 = int((north - f) / e + 0.5)
    row_2 = int((south - f) / e + 0.5)

    col_min, col_max = max(0, min(col_1, col_2)), max(col_1, col_2)
    row_min, row_max = max(0, min(row_1, row_2)), max(row_1, row_2)

    with Image.open(io.BytesIO(image_bytes)) as img:
        col_max = min(img.width, col_max)
        row_max = min(img.height, row_max)
        if col_max - col_min < 20 or row_max - row_min < 20:
            return None, None
        # 安全のため最大切り出しサイズを4096px四方に制限
        if (col_max - col_min) > 4096 or (row_max - row_min) > 4096:
            mid_c = (col_min + col_max) // 2
            mid_r = (row_min + row_max) // 2
            col_min = max(0, mid_c - 2048)
            col_max = min(img.width, mid_c + 2048)
            row_min = max(0, mid_r - 2048)
            row_max = min(img.height, mid_r + 2048)

        crop = img.crop((col_min, row_min, col_max, row_max))
        act_west = c + a * (col_min - 0.5)
        act_east = c + a * (col_max - 0.5)
        act_north = f + e * (row_min - 0.5)
        act_south = f + e * (row_max - 0.5)

        buf = io.BytesIO()
        crop.save(buf, format="PNG", optimize=True)
        bounds = (
            min(act_west, act_east),
            min(act_south, act_north),
            max(act_west, act_east),
            max(act_south, act_north),
        )
        return buf.getvalue(), bounds


@st.cache_data(show_spinner=False)
def transform_bounds_to_wgs84(
    bounds: tuple[float, float, float, float], source_crs: str
) -> list[float]:
    """Transform four source-CRS bounds into WGS84."""
    try:
        from rasterio.warp import transform_bounds
    except ImportError as error:
        raise ValueError(
            "EPSG:6673の変換には rasterio が必要です。"
            " requirements.txt の依存関係をインストールしてください。"
        ) from error

    return list(transform_bounds(source_crs, "EPSG:4326", *bounds))


def _bounds_from_world_file(
    world_file_bytes: bytes,
    width: int,
    height: int,
    source_crs: str,
) -> list[float]:
    values = [
        float(line.strip())
        for line in world_file_bytes.decode("utf-8-sig").splitlines()
        if line.strip()
    ]
    if len(values) != 6:
        raise ValueError("World file は6行（A,D,B,E,C,F）で指定してください。")

    a, d, b, e, c, f = values
    corners = [
        (
            c + a * (col - 0.5) + b * (row - 0.5),
            f + d * (col - 0.5) + e * (row - 0.5),
        )
        for col, row in ((0, 0), (width, 0), (0, height), (width, height))
    ]
    bounds = (
        min(point[0] for point in corners),
        min(point[1] for point in corners),
        max(point[0] for point in corners),
        max(point[1] for point in corners),
    )
    return transform_bounds_to_wgs84(bounds, source_crs)


def _feature_to_annotation(geometry: dict[str, Any], annotation_id: int) -> dict[str, Any]:
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") == "Polygon":
        coordinates = coordinates[0] if coordinates else []
    if geometry.get("type") != "LineString" or len(coordinates) < 2:
        raise ValueError("ポリラインを2点以上含むジオメトリを描画してください。")
    points = [[float(point[1]), float(point[0])] for point in coordinates]
    return {
        "id": annotation_id,
        "geometry": {"type": "LineString", "coordinates": coordinates},
        "start": points[0],
        "end": points[-1],
        "polyline": points,
        "land_price": 0,
        "symbol": "",
        "mark": {"shape": "なし", "left_pattern": "なし", "right_pattern": "なし"},
    }


def build_map(
    preview_image_bytes: bytes,
    bounds: tuple[float, float, float, float],
    opacity: float,
    annotations_json: str,
    highres_image_bytes: bytes | None = None,
    highres_bounds: tuple[float, float, float, float] | None = None,
) -> folium.Map:
    west, south, east, north = bounds
    center = [(south + north) / 2, (west + east) / 2]
    map_object = folium.Map(location=center, zoom_start=15, control_scale=True)
    # ベース画像（全体プレビュー）
    image_data_uri = (
        "data:image/png;base64,"
        + base64.b64encode(preview_image_bytes).decode("ascii")
    )
    folium.raster_layers.ImageOverlay(
        image=image_data_uri,
        bounds=[[south, west], [north, east]],
        opacity=opacity,
        interactive=True,
        cross_origin=False,
        name="全体路線価図 (縮小プレビュー)",
        zindex=1,
    ).add_to(map_object)

    # 作業エリア（原寸大高解像度レイヤー）
    if highres_image_bytes and highres_bounds:
        hr_w, hr_s, hr_e, hr_n = highres_bounds
        hr_uri = (
            "data:image/png;base64,"
            + base64.b64encode(highres_image_bytes).decode("ascii")
        )
        folium.raster_layers.ImageOverlay(
            image=hr_uri,
            bounds=[[hr_s, hr_w], [hr_n, hr_e]],
            opacity=opacity,
            interactive=True,
            cross_origin=False,
            name="🔍 作業エリア (原寸100%高画質)",
            zindex=2,
        ).add_to(map_object)

    annotations = json.loads(annotations_json)
    feature_collection = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": annotation["id"],
                    "land_price": annotation.get("land_price", 0),
                    "symbol": annotation.get("symbol", ""),
                },
                "geometry": annotation["geometry"],
            }
            for annotation in annotations
            if annotation.get("geometry")
        ],
    }
    if feature_collection["features"]:
        folium.GeoJson(
            feature_collection,
            name="保存済みアノテーション",
            style_function=lambda _: {
                "color": "#ff0000",
                "weight": 4,
                "opacity": 0.9,
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["id", "land_price", "symbol"],
                aliases=["ID", "路線価", "記号"],
            ),
        ).add_to(map_object)

    folium.LayerControl().add_to(map_object)
    from folium.plugins import Draw

    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": True,
            "polygon": False,
            "rectangle": False,
            "circle": False,
            "circlemarker": False,
            "marker": False,
        },
        edit_options={"edit": False, "remove": True},
    ).add_to(map_object)
    return map_object


def _init_state() -> None:
    defaults = {
        "annotations": [],
        "editing_id": None,
        "next_id": 1,
        "pending_geometry": None,
        "json_load_warning": None,
        "last_drawing_signature": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


st.set_page_config(
    page_title="路線価アノテーションツール",
    layout="wide",
    initial_sidebar_state="expanded",
)
_init_state()
st.title("📍 路線価アノテーションツール")
st.sidebar.header("📁 ファイル操作 / 設定")

uploaded_image = st.sidebar.file_uploader(
    "1. 表示用PNG画像をアップロード",
    type=["png"],
)
opacity = st.sidebar.slider("画像の透過度", 0.0, 1.0, 0.7, 0.05)

st.sidebar.markdown("### ジオリファレンス")
georef_bounds: list[float] | None = None
source_crs = st.sidebar.selectbox(
    "座標系",
    ["EPSG:4326（WGS84）", "EPSG:6673（兵庫県など）"],
)
source_crs_code = source_crs.split("（", 1)[0]
georef_type = st.sidebar.radio(
    "座標情報の入力方法",
    ["Boundsを入力", "World fileをアップロード"],
)
if georef_type == "Boundsを入力":
    st.sidebar.caption("入力値は選択した座標系の単位です。6673はメートルです。")
    west_input = st.sidebar.number_input("西端 / X最小", value=139.0, format="%.8f")
    south_input = st.sidebar.number_input("南端 / Y最小", value=35.0, format="%.8f")
    east_input = st.sidebar.number_input("東端 / X最大", value=139.1, format="%.8f")
    north_input = st.sidebar.number_input("北端 / Y最大", value=35.1, format="%.8f")
    if uploaded_image is not None:
        try:
            georef_bounds = transform_bounds_to_wgs84(
                (west_input, south_input, east_input, north_input),
                source_crs_code,
            )
        except ValueError as error:
            st.sidebar.error(f"Bounds変換エラー: {error}")
else:
    uploaded_world_file = st.sidebar.file_uploader(
        "World fileをアップロード",
        type=["pgw", "jgw", "tfw", "wld"],
    )
    if uploaded_image is not None and uploaded_world_file is not None:
        try:
            image_bytes = uploaded_image.getvalue()
            width, height = _png_size(image_bytes)
            wld_raw = uploaded_world_file.getvalue()
            st.session_state.wld_vals = [
                float(line.strip())
                for line in wld_raw.decode("utf-8-sig").splitlines()
                if line.strip()
            ]
            georef_bounds = _bounds_from_world_file(
                wld_raw,
                width,
                height,
                source_crs_code,
            )
        except (ValueError, OSError) as error:
            st.sidebar.error(f"World file読込エラー: {error}")

uploaded_json = st.sidebar.file_uploader(
    "2. 既存JSON/GeoJSONを読み込み", type=["json", "geojson"]
)
if uploaded_json is not None and st.sidebar.button("データを読み込んで復元"):
    try:
        data = json.load(uploaded_json)
        loaded_annotations = data.get("annotations", [])
        if data.get("type") == "FeatureCollection":
            loaded_annotations = [
                {
                    "id": feature["properties"].get("id", index + 1),
                    "geometry": feature["geometry"],
                    "land_price": feature["properties"].get("land_price", 0),
                    "symbol": feature["properties"].get("symbol", ""),
                    "mark": feature["properties"].get("mark", {}),
                    "start": [
                        feature["geometry"]["coordinates"][0][1],
                        feature["geometry"]["coordinates"][0][0],
                    ],
                    "end": [
                        feature["geometry"]["coordinates"][-1][1],
                        feature["geometry"]["coordinates"][-1][0],
                    ],
                    "polyline": [
                        [point[1], point[0]]
                        for point in feature["geometry"]["coordinates"]
                    ],
                }
                for index, feature in enumerate(data.get("features", []))
            ]
        if not isinstance(loaded_annotations, list):
            raise ValueError("annotations は配列である必要があります。")
        st.session_state.annotations = loaded_annotations
        st.session_state.next_id = (
            max((annotation.get("id", 0) for annotation in loaded_annotations), default=0)
            + 1
        )
        st.session_state.pending_geometry = None
        st.sidebar.success(f"データをロードしました。（{len(loaded_annotations)}件）")
        st.rerun()
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        st.sidebar.error(f"JSON/GeoJSON読み込みエラー: {error}")

if uploaded_image is not None:
    try:
        preview_image_bytes, orig_w, orig_h = load_image(uploaded_image.getvalue())
        st.info(
            f"PNGは地図表示用に最大{IMAGE_PREVIEW_MAX_DIMENSION}pxへ縮小しています。"
            f"元画像: {orig_w:,} × {orig_h:,} pixels"
        )
    except (OSError, ValueError) as error:
        st.error(f"画像読込エラー: {error}")
        st.stop()
else:
    st.info("👈 PNG画像をアップロードしてください。")
    st.stop()

if georef_bounds is None:
    st.warning("BoundsまたはWorld fileを指定すると地図を表示できます。")
    st.stop()

west, south, east, north = georef_bounds
if not west < east or not south < north:
    st.error("Boundsは west < east かつ south < north になるよう指定してください。")
    st.stop()

# 緯度35度付近での概算距離（m）
approx_lat_m = (north - south) * 111_000
approx_lon_m = (east - west) * 91_400
st.sidebar.caption(
    f"🗺️ 画像範囲: 東西 約{approx_lon_m/1000:.2f}km × 南北 約{approx_lat_m/1000:.2f}km"
)

st.session_state.json_load_warning = None
# 高解像度切り出しの準備
st.sidebar.markdown("---")
st.sidebar.markdown("### 🔍 高解像度アノテーション表示")
enable_highres = st.sidebar.checkbox(
    "作業エリアを原寸大（100%解像度）で重ねる",
    value=True,
    help="ズームインした街区や作業中のエリアを、文字がくっきり読める元画像の100%解像度で切り出してオーバーレイ表示します。",
)

highres_bytes = None
highres_bounds = None
wld_vals = getattr(st.session_state, "wld_vals", None)

if enable_highres and wld_vals and len(wld_vals) == 6 and source_crs_code == "EPSG:4326":
    # 前回の地図viewportまたは中心周辺を原寸大クロップ
    last_map_data = st.session_state.get("last_map_data")
    vp = last_map_data.get("bounds") if last_map_data else None
    if vp and "_southWest" in vp and "_northEast" in vp:
        s_crop = vp["_southWest"]["lat"]
        w_crop = vp["_southWest"]["lng"]
        n_crop = vp["_northEast"]["lat"]
        e_crop = vp["_northEast"]["lng"]
    else:
        # 初回は中心付近の約800m四方
        c_lat = (south + north) / 2
        c_lon = (west + east) / 2
        s_crop = c_lat - 0.0035
        n_crop = c_lat + 0.0035
        w_crop = c_lon - 0.0045
        e_crop = c_lon + 0.0045

    try:
        highres_bytes, highres_bounds = crop_highres_region(
            uploaded_image.getvalue(),
            wld_vals,
            (s_crop, w_crop, n_crop, e_crop),
        )
        if highres_bounds:
            st.sidebar.success("✅ 作業エリアの原寸高解像度画像を適用中")
    except Exception as e:
        st.sidebar.warning(f"高解像度クロップ待機中: {e}")

annotations_json = json.dumps(st.session_state.annotations, ensure_ascii=False, sort_keys=True)
map_object = build_map(
    preview_image_bytes,
    (west, south, east, north),
    opacity,
    annotations_json,
    highres_image_bytes=highres_bytes,
    highres_bounds=highres_bounds,
)
map_data = st_folium(
    map_object,
    height=700,
    width=None,
    key="annotation_map",
    returned_objects=["last_active_drawing", "bounds", "zoom"],
)
if map_data:
    st.session_state["last_map_data"] = map_data
active_drawing = map_data.get("last_active_drawing") if map_data else None
if active_drawing and active_drawing.get("geometry"):
    signature = json.dumps(active_drawing["geometry"], sort_keys=True)
    if signature != st.session_state.last_drawing_signature:
        st.session_state.pending_geometry = active_drawing["geometry"]
        st.session_state.last_drawing_signature = signature

col_form, col_list = st.columns([4, 5])
with col_form:
    st.subheader(
        "📝 アノテーション入力"
        if st.session_state.editing_id is None
        else f"✏️ アノテーション修正 (ID: {st.session_state.editing_id})"
    )
    geometry = st.session_state.pending_geometry
    if st.session_state.editing_id is not None:
        edit_item = next(
            item
            for item in st.session_state.annotations
            if item["id"] == st.session_state.editing_id
        )
        geometry = edit_item["geometry"]
    if geometry is None:
        st.info("地図上のDrawツールでポリラインを描画してください。")

    edit_item = next(
        (
            item
            for item in st.session_state.annotations
            if item["id"] == st.session_state.editing_id
        ),
        {},
    )
    mark = edit_item.get("mark", {})
    with st.form("annotation_form"):
        land_price = st.number_input(
            "路線価（必須・数値）", min_value=0, value=int(edit_item.get("land_price", 0)), step=1000
        )
        symbol = st.text_input(
            "記号 (A～Gの1文字)",
            value=edit_item.get("symbol", ""),
            max_chars=1,
        ).strip().upper()
        shape = st.selectbox(
            "マーク形状",
            ["六角形", "楕円", "八角形", "正円", "縦に潰れたひし形", "横長の長方形", "なし"],
            index=["六角形", "楕円", "八角形", "正円", "縦に潰れたひし形", "横長の長方形", "なし"].index(
                mark.get("shape", "なし")
            )
            if mark.get("shape", "なし") in ["六角形", "楕円", "八角形", "正円", "縦に潰れたひし形", "横長の長方形", "なし"]
            else 6,
        )
        left_pattern = st.selectbox("左側模様", ["斜線", "黒塗り", "なし"], index=["斜線", "黒塗り", "なし"].index(mark.get("left_pattern", "なし")) if mark.get("left_pattern", "なし") in ["斜線", "黒塗り", "なし"] else 2)
        right_pattern = st.selectbox("右側模様", ["斜線", "黒塗り", "なし"], index=["斜線", "黒塗り", "なし"].index(mark.get("right_pattern", "なし")) if mark.get("right_pattern", "なし") in ["斜線", "黒塗り", "なし"] else 2)
        submitted = st.form_submit_button("修正を保存" if st.session_state.editing_id else "登録")

    if submitted:
        if not geometry or geometry.get("type") != "LineString" or len(geometry.get("coordinates", [])) < 2:
            st.error("❌ 地図上で2点以上のポリラインを描画してください。")
        elif land_price <= 0 or symbol not in list("ABCDEFG"):
            st.error("❌ 路線価は0より大きく、記号はA～Gの1文字で指定してください。")
        else:
            annotation = _feature_to_annotation(geometry, st.session_state.editing_id or st.session_state.next_id)
            annotation.update({
                "land_price": land_price,
                "symbol": symbol,
                "mark": {"shape": shape, "left_pattern": left_pattern, "right_pattern": right_pattern},
            })
            if st.session_state.editing_id is None:
                st.session_state.annotations.append(annotation)
                st.session_state.next_id += 1
            else:
                index = next(i for i, item in enumerate(st.session_state.annotations) if item["id"] == st.session_state.editing_id)
                st.session_state.annotations[index] = annotation
                st.session_state.editing_id = None
            st.session_state.pending_geometry = None
            st.session_state.last_drawing_signature = None
            st.rerun()

with col_list:
    st.subheader(f"📋 登録済みアノテーション（{len(st.session_state.annotations)}件）")
    for annotation in st.session_state.annotations:
        with st.expander(f"ID: {annotation['id']} | 路線価: {annotation['land_price']} | 記号: {annotation['symbol']}"):
            st.write(f"**始点 (Lat, Lon)**: {annotation['start']}")
            st.write(f"**終点 (Lat, Lon)**: {annotation['end']}")
            edit_col, delete_col = st.columns(2)
            if edit_col.button("✏️ 修正", key=f"edit_{annotation['id']}"):
                st.session_state.editing_id = annotation["id"]
                st.session_state.pending_geometry = annotation["geometry"]
                st.rerun()
            if delete_col.button("🗑️ 削除", key=f"delete_{annotation['id']}"):
                st.session_state.annotations = [
                    item for item in st.session_state.annotations if item["id"] != annotation["id"]
                ]
                st.rerun()

st.sidebar.markdown("---")
geojson_data = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "id": annotation["id"],
                "land_price": annotation["land_price"],
                "symbol": annotation["symbol"],
                "mark": annotation["mark"],
            },
            "geometry": annotation["geometry"],
        }
        for annotation in st.session_state.annotations
    ],
}
st.sidebar.download_button(
    "💾 GeoJSONとして保存（緯度経度）",
    data=json.dumps(geojson_data, ensure_ascii=False, indent=2),
    file_name="annotations.geojson",
    mime="application/geo+json",
)

import base64
import io
import json
from typing import Any

import folium
import png
import streamlit as st
from streamlit.errors import StreamlitInvalidLayoutContextError
from streamlit_folium import st_folium


IMAGE_TILE_SIZE = 1024
IMAGE_PREVIEW_MAX_DIMENSION = 4096


def rerun_fragment() -> None:
    """Use a fragment rerun where supported, with a safe fallback."""
    try:
        st.rerun(scope="fragment")
    except StreamlitInvalidLayoutContextError:
        st.rerun()


@st.cache_data(show_spinner=False)
def load_image(
    image_bytes: bytes,
) -> tuple[list[dict[str, Any]], int, int]:
    """Stream a PNG and create one bounded preview for the map overlay."""
    reader = png.Reader(bytes=image_bytes)
    width, height, rows, metadata = reader.read()
    bitdepth = int(metadata.get("bitdepth", 8))
    if bitdepth not in (1, 2, 4, 8, 16):
        raise ValueError("PNGのビット深度（1/2/4/8/16）に対応していません。")
    palette = metadata.get("palette")
    greyscale = bool(metadata.get("greyscale")) and palette is None
    alpha = bool(metadata.get("alpha"))
    source_channels = (
        (2 if alpha else 1)
        if greyscale
        else 1 if palette else (4 if alpha else 3)
    )
    scale = max(
        1,
        (width + IMAGE_PREVIEW_MAX_DIMENSION - 1) // IMAGE_PREVIEW_MAX_DIMENSION,
        (height + IMAGE_PREVIEW_MAX_DIMENSION - 1) // IMAGE_PREVIEW_MAX_DIMENSION,
    )
    preview_width = (width + scale - 1) // scale
    preview_height = (height + scale - 1) // scale
    preview_rows: list[list[int]] = []
    source_max = (1 << bitdepth) - 1

    for row_index, row in enumerate(rows):
        if row_index % scale != 0:
            continue
        values = list(row)
        sampled: list[int] = []
        for column in range(0, width, scale):
            start = column * source_channels
            pixel = values[start : start + source_channels]
            if palette:
                sampled.extend(list(palette[pixel[0]][:3]))
            elif greyscale:
                value = round(pixel[0] * 255 / source_max)
                sampled.extend([value, value, value])
            else:
                sampled.extend(
                    round(value * 255 / source_max) for value in pixel[:3]
                )
        preview_rows.append(sampled)

    output = io.BytesIO()
    png.Writer(
        preview_width,
        preview_height,
        bitdepth=8,
        greyscale=False,
    ).write(output, preview_rows)
    return [
        {
            "image": output.getvalue(),
            "x": 0,
            "y": 0,
            "width": preview_width,
            "height": preview_height,
        }
    ], width, height


def _png_size(image_bytes: bytes) -> tuple[int, int]:
    width, height, _, _ = png.Reader(bytes=image_bytes).read()
    return width, height


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
        (c + a * col + b * row, f + d * col + e * row)
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


@st.cache_data(show_spinner=False)
def build_map(
    image_tiles: list[dict[str, Any]],
    image_width: int,
    image_height: int,
    bounds: tuple[float, float, float, float],
    opacity: float,
    annotations_json: str,
) -> folium.Map:
    west, south, east, north = bounds
    center = [(south + north) / 2, (west + east) / 2]
    map_object = folium.Map(location=center, zoom_start=15, control_scale=True)
    for tile in image_tiles:
        tile_west = west + (east - west) * tile["x"] / image_width
        tile_east = west + (east - west) * (
            tile["x"] + tile["width"]
        ) / image_width
        tile_north = north - (north - south) * tile["y"] / image_height
        tile_south = north - (north - south) * (
            tile["y"] + tile["height"]
        ) / image_height
        image_data_uri = (
            "data:image/png;base64,"
            + base64.b64encode(tile["image"]).decode("ascii")
        )
        folium.raster_layers.ImageOverlay(
            image=image_data_uri,
            bounds=[[tile_south, tile_west], [tile_north, tile_east]],
            opacity=opacity,
            interactive=True,
            cross_origin=False,
            zindex=1,
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
            georef_bounds = _bounds_from_world_file(
                uploaded_world_file.getvalue(),
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
        image_tiles, orig_w, orig_h = load_image(uploaded_image.getvalue())
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

st.session_state.json_load_warning = None
annotations_json = json.dumps(st.session_state.annotations, ensure_ascii=False, sort_keys=True)
map_object = build_map(
    image_tiles,
    orig_w,
    orig_h,
    (west, south, east, north),
    opacity,
    annotations_json,
)
map_data = st_folium(
    map_object,
    height=700,
    width=None,
    key="annotation_map",
    returned_objects=["last_active_drawing"],
)
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

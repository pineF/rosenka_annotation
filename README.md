# rosenka_annotation

## 地図オーバーレイ版アノテーションツール

`rosenka_annotation_tool.py` は、画像を WGS84（EPSG:4326）の地図上に重ねて表示し、
地図上で描画したポリラインを緯度経度の GeoJSON として保存します。

### 使い方

1. サイドバーで表示用PNG画像をアップロードします。
2. 座標系を選択し、Boundsを入力するかWorld file（`.pgw`、`.jgw`、
   `.tfw`、`.wld`）をアップロードします。EPSG:4326またはEPSG:6673を
   受け付け、地図表示時にEPSG:4326へ変換します。
3. 透過度を調整し、Folium の Draw ツールでポリラインを描画します。
4. 路線価・記号などを入力して登録し、サイドバーから `annotations.geojson` を
   ダウンロードします。GeoJSON の座標は `[longitude, latitude]` です。

EPSG:6673からEPSG:4326への変換には `rasterio` が必要です。大きなPNGは
行単位で読み込み、1024ピクセル四方のタイルに分割します。依存関係は
`pip install -r requirements.txt` でインストールできます。
# rosenka_annotation

## 地図オーバーレイ版アノテーションツール

`rosenka_annotation_tool.py` は、画像を WGS84（EPSG:4326）の地図上に重ねて表示し、
地図上で描画したポリラインを緯度経度の GeoJSON として保存します。

### 使い方

1. サイドバーで表示用PNG画像をアップロードします。
2. ジオリファレンス用GeoTIFFをアップロードします。EPSG:4326または
   EPSG:6673を受け付け、地図表示時にEPSG:4326へ変換します。
3. 透過度を調整し、Folium の Draw ツールでポリラインを描画します。
4. 路線価・記号などを入力して登録し、サイドバーから `annotations.geojson` を
   ダウンロードします。GeoJSON の座標は `[longitude, latitude]` です。

GeoTIFFのBounds読込には `rasterio` が必要です。GeoTIFFは表示画像ではなく
座標情報としてのみ使用し、大きなPNGは行単位で読み込み、
1024ピクセル四方のタイルに分割します。依存関係は
`pip install -r requirements.txt` でインストールできます。
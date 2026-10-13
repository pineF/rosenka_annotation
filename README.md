# rosenka_annotation

## 地図オーバーレイ版アノテーションツール

`rosenka_annotation_tool.py` は、画像を WGS84（EPSG:4326）の地図上に重ねて表示し、
地図上で描画したポリラインを緯度経度の GeoJSON として保存します。

### 使い方

1. サイドバーでPNG画像をアップロードします。
2. ジオリファレンス方法を選びます。
   - **Boundsを入力**: `west, south, east, north` を十進度で入力します。
   - **World file**: `.pgw`、`.jgw`、`.tfw`、`.wld` を画像と一緒に指定します。
   - **GeoTIFFから自動取得**: EPSG:4326 の GeoTIFF を指定します。
3. 透過度を調整し、Folium の Draw ツールでポリラインを描画します。
4. 路線価・記号などを入力して登録し、サイドバーから `annotations.geojson` を
   ダウンロードします。GeoJSON の座標は `[longitude, latitude]` です。

GeoTIFF の自動読込には `rasterio` が必要です。依存関係は
`pip install -r requirements.txt` でインストールできます。
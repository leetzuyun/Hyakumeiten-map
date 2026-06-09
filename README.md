# 🍜 日本百名店地圖 — 使用說明

## 📂 檔案結構
```
hyakumeiten_app/
├── index.html            ← 主要 app（手機瀏覽器直接開啟）
├── sw.js                 ← Service Worker（離線支援）
├── manifest.json         ← PWA 設定
├── export_to_json.py     ← 把你的 parquet 轉成 JSON
└── restaurants_data.json ← 你的真實資料（跑完腳本後放在這）
```

---

## 🚀 使用步驟

### Step 1：轉換資料
把 `gourmet_cache.parquet` 和 `export_to_json.py` 放在同一個資料夾，然後：
```bash
pip install pandas pyarrow
python export_to_json.py
```
會產生 `restaurants_data.json`，把它複製到 `hyakumeiten_app/` 資料夾內。

### Step 2：在手機上使用

**方法 A：本機 Wi-Fi（最簡單）**
1. 電腦上啟動一個簡單伺服器：
   ```bash
   cd hyakumeiten_app
   python -m http.server 8080
   ```
2. 查看電腦的本機 IP（例如 `192.168.1.5`）
3. 手機與電腦連同一個 Wi-Fi
4. 手機瀏覽器開啟 `http://192.168.1.5:8080`

**方法 B：直接從電腦傳到手機（離線使用）**
- 把整個 `hyakumeiten_app/` 資料夾傳到手機
- Android：用 Chrome 開啟 `index.html`（需要 file server，建議用 [Simple HTTP Server app](https://play.google.com/store/apps/details?id=com.phlox.simpleserver)）
- iOS：用 Files app 存，或直接用 AirDrop 傳 HTML 開啟

**方法 C：部署到免費靜態網站（最方便）**
1. 上傳到 [Netlify Drop](https://app.netlify.com/drop)（直接拖曳資料夾）
2. 得到一個 URL，手機書籤即可
3. iOS Safari：點「分享」→「加入主畫面」，變成 app 圖示

---

## 📱 功能介紹

| 功能 | 說明 |
|------|------|
| 🗺️ 地圖瀏覽 | OpenStreetMap，支援縮放、拖曳 |
| 📍 GPS 定位 | 點右下藍色按鈕，顯示你目前位置並依距離排序 |
| 🔍 搜尋 | 搜尋店名或地址，即時篩選 |
| 🏷️ 分類篩選 | 上方 chip 按鈕，按料理類型篩選 |
| 📋 列表面板 | 下方可上拉的列表，點擊跳到地圖位置 |
| 🧭 導航 | 彈窗內「導航」按鈕，開啟 Google Maps 導航 |
| 📖 Tabelog | 彈窗內直接連到 Tabelog 頁面 |
| 🔌 離線使用 | 首次開啟後，地圖圖磚與資料均被快取 |

---

## ⚠️ 注意事項
- 第一次使用需要連網，Service Worker 會自動快取地圖圖磚
- 之後走到日本去，瀏覽過的地區地圖可以離線看
- `restaurants_data.json` 找不到時，app 會顯示 15 間示範餐廳

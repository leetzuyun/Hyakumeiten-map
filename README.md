# 日本百名店地圖 — 使用說明

## 📂 檔案結構
```
hyakumeiten_app/
├── scripts/
├      ├── edit_data.py              ← 用於手動更改 parquet 檔
├      ├── export_to_json.py         ← 手動跑完腳本後再一起更新至資料夾外的 restaurants_data.json 檔
├      ├── refresh_google_ratings.py ← 手動更新 Google 資料 (評分、評論數)
├      ├                               # 可選參數:
├      ├                               #   --only-zero   只重打評分或評論數為 0 的店（省 API 額度）
├      ├                               #   --dry-run     只顯示哪些會被更新，不實際打 API
├      └── tabelog_url_fix.py        ← 捕抓 "tabelog_url" 顯示為 nan (in parquet) 的資料
├
├── requirements.txt      ← 跑腳本所需模組 & 環境版本
├── updater.py            ← 用於更新 restaurants_data.json 檔：
├                           Tabelog 頁面上的店名
├                              → 名稱驗證（排除廢項）
├                                 → 加入 scraped_names
├                                       → 需要重爬？→ 爬 Tabelog + Google
├                                       → 不需要？  → 檢查座標有沒有缺，有就補抓
├                           全部跑完後
├                               → cache 有但 scraped_names 沒有 → 刪除
├── index.html            ← 主要 app 介面
├── sw.js                 ← Service Worker（離線支援）
├── manifest.json         ← PWA 設定
├── gourmet_cache.parquet ← 我先存成這個
└── restaurants_data.json ← 之後才轉成 json 處理
```

---

## 🚀 使用步驟

### Step 1：更新網站資料
初次使用先安裝環境
1. 建立虛擬環境(非必要)
   ```
   python -m .venv .venv
   ```
2. 使用本機環境就跳過步驟一直接安裝
   ```
   pip install -r requirements.txt
   ```
然後：
```bash
python updater.py
```
會產生 `restaurants_data.json`，更新資料庫。

*可以視情況使用 scripts/ 底下的腳本做更精確的更新
跑完的腳本幾乎都需要再 export_to_json.py 才會真的更新到資料*

接下來再記得 commit 到這個 repo 來才能保持在最新的資料庫

### Step 2：在手機上使用
1. 連線到 https://hakyumeiten.netlify.app/
2. iOS Safari：點「分享」→「加入主畫面」，變成 app 圖示
3. 大功告成！
---

## 📱 功能介紹

| 功能 | 說明 |
|------|------|
| 地圖瀏覽 | 支援縮放、拖曳 |
| GPS 定位 | 點擊📍可以取得所在位置(需允許)，定位後會變成藍色按鈕，點擊會顯示你目前位置附近的餐廳並依距離排序 |
| 搜尋 | 左上角搜尋店名或地址 |
| 分類篩選 | 左上方下拉式選單，按料理類型篩選得獎百名店 |
| 列表面板 | 下方可上拉的列表，點擊跳到地圖位置 |
| Google Maps 導航 | 彈窗內「導航」按鈕，開啟 Google Maps 導航 |
| Tabelog | 彈窗內直接連到 Tabelog 頁面 |
| 離線使用 | 首次開啟後，地圖圖磚與資料均被快取 |

---

## ⚠️ 注意事項
- 第一次使用需要連網，Service Worker 會自動快取地圖圖磚
- 之後走到日本去，瀏覽過的地區地圖可以離線看

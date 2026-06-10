"""
export_to_json.py
把 gourmet_cache.parquet 轉成 app 使用的 restaurants_data.json
用法: python export_to_json.py
輸出: restaurants_data.json (放在同一個資料夾)
"""

import pandas as pd
import json
import math
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PARQUET_FILE = os.path.join(BASE_DIR, 'gourmet_cache.parquet')
# OUTPUT_FILE  = os.path.join(BASE_DIR, 'restaurants_data.json')
OUTPUT_FILE  = os.path.join(BASE_DIR, 'scripts', 'restaurants_data.json')

def is_valid(val):
    """過濾掉 NaN / None"""
    if val is None:
        return False
    try:
        return not math.isnan(float(val))
    except (TypeError, ValueError):
        return True

def export():
    if not os.path.exists(PARQUET_FILE):
        print(f"找不到 {PARQUET_FILE}，請確認路徑正確。")
        return

    df = pd.read_parquet(PARQUET_FILE)
    
    # 如果 name 是 index，先 reset
    if 'name' not in df.columns:
        df = df.reset_index()

    records = []
    skipped = 0

    for _, row in df.iterrows():
        lat = row.get('lat')
        lng = row.get('lng')

        # 必須有座標才放進地圖
        if not is_valid(lat) or not is_valid(lng):
            skipped += 1
            continue

        # 分類：從 category_url 末段取得
        category_url = str(row.get('category_url', ''))
        category = str(row.get('category', category_url.rstrip('/').split('/')[-1] if category_url else '其他'))

        records.append({
            'name':           str(row.get('name', '')),
            'lat':            float(lat),
            'lng':            float(lng),
            'tabelog_score':  str(row.get('tabelog_score', '無')),
            'google_rating':  str(row.get('google_rating', '無')),
            'reviews':        int(row.get('reviews', 0)) if is_valid(row.get('reviews')) else 0,
            'address':        str(row.get('tabelog_address', '')),
            'category':       category,
            'tabelog_url':    str(row.get('tabelog_url', '')),
        })

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"✅ 完成！共匯出 {len(records)} 筆，略過 {skipped} 筆（無座標）。")
    print(f"   輸出檔案：{OUTPUT_FILE}")
    print(f"\n下一步：把 {OUTPUT_FILE} 放在與 index.html 相同的資料夾。")

if __name__ == '__main__':
    export()

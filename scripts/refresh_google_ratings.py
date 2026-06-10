# refresh_google_ratings.py
# 重新抓取所有店家的 Google 評分與評論數，不動座標
# 用法: uv run scripts/refresh_google_ratings.py
# 可選參數:
#   --only-zero   只重打評分或評論數為 0 的店（省 API 額度）
#   --dry-run     只顯示哪些會被更新，不實際打 API

import os
import sys
import time
import math
import unicodedata
import pandas as pd
import googlemaps
from dotenv import load_dotenv

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE_PQ = os.path.join(BASE_DIR, 'gourmet_cache.parquet')

load_dotenv(os.path.join(BASE_DIR, '.env'))
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    print("❌ 找不到 GOOGLE_API_KEY，請確認 .env 設定。")
    sys.exit(1)

gmaps = googlemaps.Client(key=GOOGLE_API_KEY)

def zen_to_han(text):
    if not isinstance(text, str): return text
    return unicodedata.normalize('NFKC', text)

def is_valid(val):
    if val is None: return False
    try: return not math.isnan(float(val))
    except (TypeError, ValueError): return True

def save_local_data(data_dict):
    flat_list = []
    for name, info in data_dict.items():
        row = info.copy()
        row['name'] = name
        flat_list.append(row)
    df = pd.DataFrame(flat_list)
    df.to_parquet(DATA_FILE_PQ, engine='pyarrow', compression='snappy', index=False)

def refresh_google_ratings(only_zero=False, dry_run=False):
    df = pd.read_parquet(DATA_FILE_PQ)
    cache = df.set_index('name').to_dict(orient='index')

    # 只處理有座標的店（沒座標的交給 updater.py fill_coords）
    candidates = {
        name: info for name, info in cache.items()
        if is_valid(info.get('lat'))
    }

    if only_zero:
        # 只打評分或評論數為 0 的
        targets = {
            name: info for name, info in candidates.items()
            if float(info.get('google_rating') or 0) == 0
            or int(info.get('reviews') or 0) == 0
        }
        print(f"📋 --only-zero 模式：共 {len(targets)} 筆評分/評論為 0（總共 {len(candidates)} 筆有座標）")
    else:
        targets = candidates
        print(f"📋 全量模式：共 {len(targets)} 筆有座標的店家")

    if dry_run:
        print("🔍 --dry-run 模式，以下店家會被重打：")
        for i, (name, info) in enumerate(list(targets.items())[:20]):
            print(f"  {name}  目前評分={info.get('google_rating')}  評論數={info.get('reviews')}")
        if len(targets) > 20:
            print(f"  ... 共 {len(targets)} 筆（只顯示前 20）")
        return

    updated = 0
    no_change = 0
    failed = 0

    for i, (name, info) in enumerate(targets.items()):
        address = str(info.get('tabelog_address', ''))
        old_rating  = float(info.get('google_rating') or 0)
        old_reviews = int(info.get('reviews') or 0)

        print(f"  [{i+1}/{len(targets)}] {name}", end=' ... ')

        # 有座標 → 只查 rating，不查 geometry（節省費用）
        search_queries = [
            zen_to_han(f"{address} {name}"),
            zen_to_han(f"日本 {name} 餐廳"),
        ]

        new_rating, new_reviews = None, None
        for query in search_queries:
            try:
                res = gmaps.find_place(
                    input=query,
                    input_type='textquery',
                    fields=['rating', 'user_ratings_total'],
                )
                if res['status'] == 'OK' and res['candidates']:
                    place = res['candidates'][0]
                    new_rating  = place.get('rating', 0)
                    new_reviews = place.get('user_ratings_total', 0)
                    break
            except Exception as e:
                print(f"\n    ⚠️ API 錯誤: {e}")
                continue

        if new_rating is None:
            print("❌ 查無結果")
            failed += 1
        elif new_rating == old_rating and new_reviews == old_reviews:
            print(f"— 無變化 ({old_rating}, {old_reviews})")
            no_change += 1
        else:
            cache[name]['google_rating'] = new_rating
            cache[name]['reviews']       = new_reviews
            print(f"✅ 更新  評分 {old_rating}→{new_rating}  評論 {old_reviews}→{new_reviews}")
            updated += 1

        # 每 20 筆存一次
        if (i + 1) % 20 == 0:
            save_local_data(cache)
            print(f"  💾 進度已儲存 ({i+1}/{len(targets)})")

        time.sleep(1.0)

    save_local_data(cache)
    print(f"\n✅ 完成！更新 {updated} 筆，無變化 {no_change} 筆，失敗 {failed} 筆。")
    print(f"   請接著跑 export_to_json.py 產生新的 restaurants_data.json")


if __name__ == '__main__':
    only_zero = '--only-zero' in sys.argv
    dry_run   = '--dry-run'   in sys.argv
    refresh_google_ratings(only_zero=only_zero, dry_run=dry_run)

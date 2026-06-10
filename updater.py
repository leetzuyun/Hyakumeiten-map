import os
import re
import json
import math
import time
import unicodedata
import requests
import pandas as pd
import googlemaps
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.poolmanager import PoolManager
from datetime import datetime, timezone, timedelta
import ssl

# --- 強制 TLS 1.2+ 的設定 ---
class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_version=ssl.PROTOCOL_TLSv1_2
        )

# --- 設定區 ---
load_dotenv()
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    print("⚠️ 警告：未讀取到 GOOGLE_API_KEY，請確認 .env 檔案設定。")

gmaps = googlemaps.Client(key=GOOGLE_API_KEY) if GOOGLE_API_KEY else None
BASE_URL = 'https://award.tabelog.com/hyakumeiten'
DATA_FILE_PQ = 'gourmet_cache.parquet'
OUTPUT_FILE  = 'restaurants_data.json'

session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
session.mount('https://', TLSAdapter(max_retries=retries))

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 資料處理輔助函數 ---
def zen_to_han(text):
    if not isinstance(text, str): return text
    return unicodedata.normalize('NFKC', text)

def load_local_data():
    """從 Parquet 讀取資料並轉回 dict"""
    if os.path.exists(DATA_FILE_PQ):
        try:
            df = pd.read_parquet(DATA_FILE_PQ)
            return df.set_index('name').to_dict(orient='index')
        except Exception as e:
            print(f"讀取 Parquet 失敗: {e}")
            return {}
    return {}

def save_local_data(data_dict):
    """將 dict 轉成 DataFrame 並儲存為 Parquet"""
    if not data_dict: return
    
    # 確保資料夾存在
    directory = os.path.dirname(DATA_FILE_PQ)
    if directory:
        os.makedirs(directory, exist_ok=True)
    
    flat_list = []
    for name, info in data_dict.items():
        row = info.copy()
        row['name'] = name
        flat_list.append(row)
    
    df = pd.DataFrame(flat_list)
    df.to_parquet(DATA_FILE_PQ, engine='pyarrow', compression='snappy', index=False)

def get_google_data(name, address, cache, force=False):
    if not gmaps:
        return None, None, None, None
        
    if not force and name in cache and 'lat' in cache[name] and not pd.isna(cache[name].get('lat')) and cache[name].get('google_rating'):
        return cache[name]['lat'], cache[name]['lng'], cache[name]['google_rating'], cache[name].get('reviews', 0)

    search_strategies = [f"{address} {name}", f"日本 {name} 餐廳"]
    for query in search_strategies:
        try:
            res = gmaps.find_place(input=zen_to_han(query), input_type='textquery', 
                                   fields=['geometry', 'rating', 'user_ratings_total'])
            if res['status'] == 'OK' and res['candidates']:
                place = res['candidates'][0]
                lat, lng = place['geometry']['location']['lat'], place['geometry']['location']['lng']
                rating, reviews = place.get('rating', 0), place.get('user_ratings_total', 0)
                if name not in cache: cache[name] = {}
                cache[name].update({'lat': lat, 'lng': lng, 'google_rating': rating, 'reviews': reviews})
                return lat, lng, rating, reviews
        except Exception: continue
    return None, None, None, None


# --- JSON 匯出輔助函數 ---
def is_valid(val):
    """過濾掉 NaN / None"""
    if val is None:
        return False
    try:
        return not math.isnan(float(val))
    except (TypeError, ValueError):
        return True

def export_to_json():
    """將更新後的 Parquet 轉成前端用的 JSON"""
    if not os.path.exists(DATA_FILE_PQ):
        print(f"❌ 找不到 {DATA_FILE_PQ}，無法匯出 JSON。")
        return

    print(f"\n📦 開始將 Parquet 轉換為 JSON...")
    df = pd.read_parquet(DATA_FILE_PQ)
    
    if 'name' not in df.columns:
        df = df.reset_index()

    records = []
    skipped = 0

    for _, row in df.iterrows():
        lat = row.get('lat')
        lng = row.get('lng')

        if not is_valid(lat) or not is_valid(lng):
            skipped += 1
            continue

        category_url = str(row.get('category_url', ''))
        category = str(row.get('category', category_url.rstrip('/').split('/')[-1] if category_url else '其他'))
        # 🟢 增加這一段：確保 URL 是有效的字串，若為空則給予預設值
        t_url = row.get('tabelog_url')
        # 如果不是字串，或者它是 'nan' 字串，直接賦予預設值
        if pd.isna(t_url) or str(t_url).lower() == 'nan' or not str(t_url).startswith('http'):
            final_t_url = 'https://tabelog.com/'
        else:
            final_t_url = str(t_url)

        records.append({
            'name':           str(row.get('name', '')),
            'lat':            float(lat),
            'lng':            float(lng),
            'tabelog_score':  str(row.get('tabelog_score', '無')),
            'google_rating':  str(row.get('google_rating', '無')),
            'reviews':        int(row.get('reviews', 0)) if is_valid(row.get('reviews')) else 0,
            'address':        str(row.get('tabelog_address', '')),
            'category':       category,
            'tabelog_url':    final_t_url,
        })

    JST = timezone(timedelta(hours=9))
    updated_str = datetime.now(JST).strftime('%Y/%m/%d %H:%M JST')

    output = {
        'updated': updated_str,
        'records': records,
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ JSON 轉換完成！共匯出 {len(records)} 筆，略過 {skipped} 筆（無座標）。")
    print(f"   更新時間：{updated_str}")
    print(f"   輸出檔案：{OUTPUT_FILE}")


# --- 主程式：爬蟲與更新 ---
def run_crawler(force=False):
    cache = load_local_data()
    print(f"🚀 開始爬蟲任務 (強制更新: {force})")
    
    scraped_names = set()

    try:
        resp = session.get(BASE_URL, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        urls = list(set([urljoin(BASE_URL, a['href']) for a in soup.find_all('a', href=True) if '/hyakumeiten/' in a['href']]))
        
        for idx, url in enumerate(urls):
            cat_name = url.rstrip('/').split('/')[-1]
            print(f"--- 掃描分類 [{idx+1}/{len(urls)}]: {cat_name} ---")
            
            cat_resp = session.get(url, headers=headers, timeout=15)
            cat_soup = BeautifulSoup(cat_resp.text, 'html.parser')

            name_tags = cat_soup.select('.hyakumeiten-shop__name')

            for name_tag in name_tags:
                raw_name = name_tag.get_text(strip=True)
                name = zen_to_han(raw_name)
                if not name or "百名店" in name or len(name) < 2: 
                    continue
                
                scraped_names.add(name)
                needs_tabelog = force or name not in cache or not cache[name].get('tabelog_address')
                
                if needs_tabelog:
                    try:
                        a_tag = name_tag.find_parent('a')

                        if a_tag and a_tag.has_attr('href'):
                            target_url = a_tag['href']
                            print(f"  > 爬取 Tabelog: {name}")
                            d_resp = session.get(target_url, headers=headers, timeout=15)
                            d_soup = BeautifulSoup(d_resp.text, 'html.parser')
                            
                            score = "無"
                            score_tag = d_soup.find(class_=re.compile(r'rating.*score.*val', re.I))
                            if score_tag: 
                                m = re.search(r'\d\.\d{2}', score_tag.text)
                                if m: score = m.group()
                            
                            addr = "無地址"
                            addr_tag = d_soup.find('p', class_='rstinfo-table__address')
                            if addr_tag: addr = zen_to_han(addr_tag.get_text(strip=True))
                            
                            if name not in cache: cache[name] = {}
                            cache[name].update({
                                'tabelog_score': score,
                                'tabelog_address': addr,
                                'category_url': url,
                                'tabelog_url': urljoin(BASE_URL, target_url) 
                            })
                            
                            print(f"  > 🔍 同步搜尋 Google Maps 資訊...")
                            get_google_data(name, addr, cache, force=force)
                            
                            save_local_data(cache)
                            time.sleep(1.2)
                    except Exception as e:
                        print(f"  > ⚠️ 處理店家 {name} 時發生錯誤: {e}")
                        continue
                else:
                    if 'lat' not in cache[name] or pd.isna(cache[name]['lat']):
                        print(f"  > 📍 補抓 Google 座標: {name}")
                        get_google_data(name, cache[name].get('tabelog_address', ''), cache, force=force)
                        save_local_data(cache)

        # 檢查已過期（落榜）的店家
        EXPECTED_MIN_COUNT = 50 
        if len(scraped_names) > EXPECTED_MIN_COUNT:
            stale = [n for n in list(cache.keys()) if n not in scraped_names]
            if stale:
                print(f"\n🗑️ 發現 {len(stale)} 間已從百名店移除的店家：")
                for n in stale:
                    print(f"  - {n}")
                    del cache[n]
                save_local_data(cache)
                print(f"  已從快取清除 {len(stale)} 筆。")
            else:
                print("✅ 快取無過期資料，無需移除。")
        else:
            print(f"⚠️ 警告：本次僅抓取到 {len(scraped_names)} 家店，低於安全門檻，跳過清除落榜名單以保護快取！")

        print("✅ 所有新資料與座標已蒐集完畢！")

    except Exception as e:
        print(f"❌ 發生核心錯誤: {str(e)}")


if __name__ == "__main__":
    # 若需要強制重新抓取可改為 run_crawler(force=True)
    run_crawler(force=False)
    
    export_to_json()
    
    print("\n🎉 執行完畢！你現在可以將 restaurants_data.json commit 並 push 到 git 上，讓 Netlify 自動更新了。")
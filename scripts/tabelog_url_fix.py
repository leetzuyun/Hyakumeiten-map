# fix_tabelog_url.py
import os
import re
import time
import math
import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from urllib3.poolmanager import PoolManager
import ssl
import unicodedata

class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_version=ssl.PROTOCOL_TLSv1_2
        )

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_FILE_PQ = os.path.join(BASE_DIR, 'gourmet_cache.parquet')

session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
session.mount('https://', TLSAdapter(max_retries=retries))
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def zen_to_han(text):
    if not isinstance(text, str): return text
    return unicodedata.normalize('NFKC', text)

def search_tabelog_url(name, address):
    """用店名 + 地址前段去 Tabelog 搜尋，回傳第一筆結果的 URL"""
    # 取地址的都道府縣（前3~4字）作為關鍵字
    prefecture = address[:3] if address and address != '無地址' else ''
    query = zen_to_han(f"{prefecture} {name}").strip()
    
    search_url = f"https://tabelog.com/search/?vs=1&sa={requests.utils.quote(query)}&sw={requests.utils.quote(name)}"
    
    try:
        resp = session.get(search_url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 搜尋結果第一筆店家連結
        result = soup.select_one('.list-rst__rst-name-target')
        if result and result.has_attr('href'):
            url = result['href']
            if url.startswith('https://tabelog.com/'):
                return url
    except Exception as e:
        print(f"    ⚠️ 搜尋失敗: {e}")
    
    return None

def save_local_data(data_dict):
    flat_list = []
    for name, info in data_dict.items():
        row = info.copy()
        row['name'] = name
        flat_list.append(row)
    df = pd.DataFrame(flat_list)
    df.to_parquet(DATA_FILE_PQ, engine='pyarrow', compression='snappy', index=False)

def fix_missing_urls():
    df = pd.read_parquet(DATA_FILE_PQ)
    cache = df.set_index('name').to_dict(orient='index')
    
    # 找出 URL 是 NaN 的店家
    missing = df[df['tabelog_url'].isna() | (df['tabelog_url'].astype(str) == 'nan')]
    total = len(missing)
    print(f"📋 共 {total} 筆需要補抓 URL")
    
    fixed = 0
    failed = 0
    
    for i, (_, row) in enumerate(missing.iterrows()):
        name    = row['name']
        address = str(row.get('tabelog_address', ''))
        
        print(f"  [{i+1}/{total}] {name}", end=' ... ')
        
        url = search_tabelog_url(name, address)
        
        if url:
            cache[name]['tabelog_url'] = url
            print(f"✅ {url}")
            fixed += 1
        else:
            print(f"❌ 找不到")
            failed += 1
        
        # 每 10 筆存一次
        if (i + 1) % 10 == 0:
            save_local_data(cache)
            print(f"  💾 已儲存進度 ({i+1}/{total})")
        
        time.sleep(1.0)
    
    # 最後存一次
    save_local_data(cache)
    print(f"\n✅ 完成！成功補回 {fixed} 筆，失敗 {failed} 筆。")

if __name__ == '__main__':
    fix_missing_urls()
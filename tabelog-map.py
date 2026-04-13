import requests
from bs4 import BeautifulSoup
import googlemaps
import folium
import time
from urllib.parse import urljoin
import os
import re
import unicodedata
import tkinter as tk
from tkinter import messagebox, scrolledtext
from threading import Thread
from folium.plugins import MarkerCluster, LocateControl
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import ssl
from urllib3.poolmanager import PoolManager

# --- 強制 TLS 1.2+ 的設定 ---
class TLSAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        self.poolmanager = PoolManager(
            num_pools=connections, maxsize=maxsize,
            block=block, ssl_version=ssl.PROTOCOL_TLSv1_2
        )

# --- 設定區 ---
GOOGLE_API_KEY = 'AIzaSyDzsm-oyyVjgE_CpePetKPvA-MXlNaWRsQ'
gmaps = googlemaps.Client(key=GOOGLE_API_KEY)
BASE_URL = 'https://award.tabelog.com/hyakumeiten'
DATA_FILE_PQ = 'gourmet_cache.parquet'

session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[500, 502, 503, 504])
session.mount('https://', TLSAdapter(max_retries=retries))

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def zen_to_han(text):
    if not isinstance(text, str): return text
    return unicodedata.normalize('NFKC', text)

def load_local_data():
    """從 Parquet 讀取資料並轉回 dict """
    if os.path.exists(DATA_FILE_PQ):
        try:
            df = pd.read_parquet(DATA_FILE_PQ)
            # 將 'name' 欄位設回 index 並轉成 dict
            return df.set_index('name').to_dict(orient='index')
        except Exception as e:
            print(f"讀取 Parquet 失敗: {e}")
            return {}
    return {}

def save_local_data(data_dict):
    """將 dict 轉成 DataFrame 並儲存為 Parquet"""
    if not data_dict: return
    flat_list = []
    for name, info in data_dict.items():
        row = info.copy()
        row['name'] = name
        flat_list.append(row)
    
    df = pd.DataFrame(flat_list)
    df.to_parquet(DATA_FILE_PQ, engine='pyarrow', compression='snappy', index=False)

def get_google_data(name, address, cache, force=False):
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


class GourmetApp:
    def __init__(self, root):
        self.root = root
        self.root.title("日本百名店地圖助手")
        self.root.geometry("600x500")

        tk.Label(root, text="Tabelog 百名店資料管理 (Parquet 儲存)", font=('Arial', 14, 'bold')).pack(pady=10)
        
        self.force_update_var = tk.BooleanVar(value=False)
        tk.Checkbutton(root, text="強制重新爬取 (忽略快取)", variable=self.force_update_var).pack()

        btn_frame = tk.Frame(root)
        btn_frame.pack(pady=10)

        tk.Button(btn_frame, text="1. 蒐集/更新資料", command=self.start_crawl_thread, bg="#4CAF50", fg="white", width=20).grid(row=0, column=0, padx=5)
        tk.Button(btn_frame, text="2. 生成地圖", command=self.generate_map, bg="#2196F3", fg="white", width=20).grid(row=0, column=1, padx=5)

        self.log_area = scrolledtext.ScrolledText(root, width=70, height=20)
        self.log_area.pack(pady=10)

    def log(self, message):
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)

    def start_crawl_thread(self):
        Thread(target=self.run_crawler, daemon=True).start()

    def run_crawler(self):
        cache = load_local_data()
        force = self.force_update_var.get()
        self.log(f"開始任務 (強制更新: {force})")
        
        try:
            resp = session.get(BASE_URL, headers=headers, timeout=15)
            soup = BeautifulSoup(resp.text, 'html.parser')
            urls = list(set([urljoin(BASE_URL, a['href']) for a in soup.find_all('a', href=True) if '/hyakumeiten/' in a['href']]))
            
            for idx, url in enumerate(urls):
                cat_name = url.rstrip('/').split('/')[-1]
                self.log(f"--- 掃描分類 [{idx+1}/{len(urls)}]: {cat_name} ---")
                
                cat_resp = session.get(url, headers=headers, timeout=15)
                cat_soup = BeautifulSoup(cat_resp.text, 'html.parser')
                imgs = cat_soup.find_all('img', alt=True)
                
                for img in imgs:
                    name = zen_to_han(img['alt'].strip())
                    if not name or "百名店" in name or len(name) < 2: continue
                    
                    # 判斷是否需要處理這家店
                    needs_tabelog = force or name not in cache or not cache[name].get('tabelog_address')
                    
                    if needs_tabelog:
                        try:
                            a_tag = img.find_parent('a')
                            if a_tag and a_tag.has_attr('href'):
                                self.log(f"  > 爬取 Tabelog: {name}")
                                d_resp = session.get(a_tag['href'], headers=headers, timeout=15)
                                d_soup = BeautifulSoup(d_resp.text, 'html.parser')
                                
                                # 抓 Tabelog 分數與地址
                                score = "無"
                                score_tag = d_soup.find(class_=re.compile(r'rating.*score.*val', re.I))
                                if score_tag: 
                                    m = re.search(r'\d\.\d{2}', score_tag.text)
                                    if m: score = m.group()
                                
                                addr = "無地址"
                                addr_tag = d_soup.find('p', class_='rstinfo-table__address')
                                if addr_tag: addr = zen_to_han(addr_tag.text.strip())
                                
                                # 更新 Tabelog 資訊
                                if name not in cache: cache[name] = {}
                                cache[name].update({
                                    'tabelog_score': score,
                                    'tabelog_address': addr,
                                    'category_url': url,
                                    'tabelog_url': urljoin(BASE_URL, a_tag['href'])
                                })
                                
                                self.log(f"  > 🔍 同步搜尋 Google Maps 資訊...")
                                get_google_data(name, addr, cache, force=force)
                                
                                # 每完成一家店就存一次 Parquet，確保資料不遺失
                                save_local_data(cache)
                                time.sleep(1.2)
                        except Exception as e:
                            self.log(f"  > ⚠️ 處理店家 {name} 時發生錯誤: {e}")
                            continue
                    else:
                        # 如果不需要抓 Tabelog，檢查是否需要補抓 Google 資料
                        if 'lat' not in cache[name] or pd.isna(cache[name]['lat']):
                            self.log(f"  > 📍 補抓 Google 座標: {name}")
                            get_google_data(name, cache[name].get('tabelog_address', ''), cache, force=force)
                            save_local_data(cache)

            self.log("✅ 所有新資料與座標已蒐集完畢！")
            messagebox.showinfo("完成", "新店家的 Tabelog 與 Google 資料已同步更新！")
        except Exception as e:
            self.log(f"❌ 發生核心錯誤: {str(e)}")

    def generate_map(self):
        cache = load_local_data()
        if not cache:
            messagebox.showwarning("警告", "沒有資料可以生成地圖！")
            return
        
        self.log(f"📍 正在從 Parquet 生成地圖 (共 {len(cache)} 筆)...")
        m = folium.Map(location=[35.6895, 139.6917], zoom_start=6, tiles='CartoDB positron')
        category_layers = {}
        categories_to_process = []

        # 收集所有類別
        for name, info in cache.items():
            lat, lng = info.get('lat'), info.get('lng')
            if pd.notna(lat) and pd.notna(lng):
                url = info.get('category_url', 'others')
                food_category = info.get('category', url.rstrip('/').split('/')[-1])
                if food_category not in category_layers:
                    category_layers[food_category] = []
                    categories_to_process.append(food_category)
        
        # 按字母排序
        categories_to_process.sort()
        for food_category in categories_to_process:
            feature_group = folium.FeatureGroup(name=f"🍴 {food_category}", show=False).add_to(m)
            category_layers[food_category] = MarkerCluster().add_to(feature_group)
        
        # 加入標記
        for name, info in cache.items():
            lat, lng = info.get('lat'), info.get('lng')
            if pd.notna(lat) and pd.notna(lng):
                url = info.get('category_url', 'others')
                food_category = info.get('category', url.rstrip('/').split('/')[-1])

                safe_name = name.replace("'", "&#39;").replace('"', '&quot;')
                safe_addr = info.get('tabelog_address', '').replace("'", "&#39;").replace('"', '&quot;')
                safe_category = str(food_category).replace("'", "&#39;").replace('"', '&quot;')
                tabelog_url = info.get('tabelog_url', info.get('category_url', ''))
                tabelog_link = f'<p><a href="{tabelog_url}" target="_blank" style="text-decoration:none;color:#1565C0;">檢視 Tabelog 詳細頁</a></p>' if tabelog_url else ''
                
                popup_html = f"""
                <div style="font-family: Arial; width:240px;">
                    <h4 style="color:#d32f2f; margin:0 0 5px 0;">{safe_name}</h4>
                    <p style="font-size:11px; margin:0 0 5px 0;">📍 {safe_addr}</p>
                    <p style="font-size:12px; margin:0 0 5px 0;"><b>食物種類：</b>{safe_category}</p>
                    <hr style="margin:5px 0;">
                    <p style="margin:0 0 5px 0;"><b>Tabelog 評分：</b>⭐ {info.get('tabelog_score','無')}</p>
                    <p style="margin:0 0 5px 0;"><b>Google 評分：</b>⭐ {info.get('google_rating','無')} ({info.get('reviews',0)})</p>
                    {tabelog_link}
                </div>
                """
                folium.Marker(
                    location=[lat, lng],
                    popup=folium.Popup(folium.IFrame(popup_html, width=260, height=190)),
                    tooltip=safe_name,
                    icon=folium.Icon(color='orange', icon='cutlery')
                ).add_to(category_layers[food_category])

        folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', attr='Google', name='Google 街景').add_to(m)
        folium.TileLayer(tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Google 衛星').add_to(m)
        LocateControl().add_to(m)
        folium.LayerControl(collapsed=False).add_to(m)
        
        m.save("japan_hyakumeiten_map.html")
        self.log("地圖生成完畢！")

if __name__ == "__main__":
    root = tk.Tk()
    app = GourmetApp(root)
    root.mainloop()
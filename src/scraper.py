import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
import re
import unicodedata
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import os

# --- CONFIGURATION ---
BASE_URL = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=060&bs=040&ta=27&sc=27128&sc=27102&cb=0.0&ct=9999999&et=9999999&cn=9999999&mb=0&mt=9999999&shkr1=03&shkr2=03&shkr3=03&shkr4=03&fw2=&srch_navi=1"
DATA_DIR = "../data"
OUTPUT_FILE = os.path.join(DATA_DIR, "osaka_listings.csv")
CACHE_FILE = os.path.join(DATA_DIR, "address_cache.csv")

# Rotate these to avoid detection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
]

def get_header():
    return {"User-Agent": random.choice(USER_AGENTS), "Referer": "https://suumo.jp/"}

def normalize_japanese(text):
    if not text: return ""
    return unicodedata.normalize('NFKC', text).strip()

def clean_money(text):
    text = normalize_japanese(text)
    if text == '-' or text == '': return 0
    try:
        match = re.search(r'(\d+\.?\d*)', text)
        if match:
            val = float(match.group(1))
            if '万' in text: return int(val * 10000)
            return int(val)
    except:
        return 0
    return 0

# --- SMART GEOCODING CACHE ---
def load_cache():
    if os.path.exists(CACHE_FILE):
        return pd.read_csv(CACHE_FILE, index_col=0).to_dict(orient='index')
    return {}

def save_cache(cache_dict):
    df = pd.DataFrame.from_dict(cache_dict, orient='index')
    df.to_csv(CACHE_FILE)

def run_osaka_miner(max_pages=5, status_placeholder=None, progress_bar=None):
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # 1. SCRAPING PHASE
    data = []
    if status_placeholder: status_placeholder.info(f"⛏️  Initializing Deep Scrape ({max_pages} Pages)...")
    
    for page in range(1, max_pages + 1):
        url = f"{BASE_URL}&page={page}"
        
        # UI Feedback
        if status_placeholder: status_placeholder.text(f"Scanning Page {page}/{max_pages}...")
        if progress_bar: progress_bar.progress((page / max_pages) * 0.4) # 0% to 40%
        
        try:
            time.sleep(random.uniform(2, 5)) # Respectful delay
            res = requests.get(url, headers=get_header(), timeout=20)
            res.encoding = res.apparent_encoding
            
            if res.status_code != 200:
                print(f"Blocked on page {page}. Waiting 10s...")
                time.sleep(10)
                continue

            soup = BeautifulSoup(res.text, 'html.parser')
            items = soup.find_all('div', class_='cassetteitem')

            for item in items:
                # Building Data
                try:
                    name = normalize_japanese(item.find('div', class_='cassetteitem_content-title').text)
                    address = normalize_japanese(item.find('li', class_='cassetteitem_detail-col1').text)
                    age_text = normalize_japanese(item.find('li', class_='cassetteitem_detail-col3').text)
                    age = 0
                    if '新築' not in age_text:
                        age_match = re.search(r'(\d+)', age_text)
                        age = int(age_match.group(1)) if age_match else 0
                except: continue

                # Unit Data
                tbody = item.find('table', class_='cassetteitem_other')
                if not tbody: continue
                
                for row in tbody.find_all('tr'):
                    tds = row.find_all('td')
                    if len(tds) < 9: continue
                    
                    try:
                        # Parsing logic
                        img_tag = tds[1].find('img')
                        img_url = img_tag.get('rel') if img_tag and img_tag.get('rel') else (img_tag.get('src') if img_tag else "")
                        
                        floor_text = normalize_japanese(tds[2].text)
                        floor = int(re.search(r'(\d+)', floor_text).group(1)) if re.search(r'(\d+)', floor_text) else 1
                        
                        rent = clean_money(tds[3].find('span', class_='cassetteitem_price--rent').text)
                        admin = clean_money(tds[3].find('span', class_='cassetteitem_price--administration').text)
                        
                        key_money = clean_money(tds[4].find('span', class_='cassetteitem_price--gratuity').text)
                        deposit = clean_money(tds[4].find('span', class_='cassetteitem_price--deposit').text)
                        
                        size_raw = normalize_japanese(tds[5].find('span', class_='cassetteitem_menseki').text)
                        size = float(re.search(r'(\d+\.?\d*)', size_raw).group(1))
                        layout = normalize_japanese(tds[5].find('span', class_='cassetteitem_madori').text)
                        
                        link = "https://suumo.jp" + tds[8].find('a')['href']

                        data.append({
                            'name': name, 'address': address, 'age': age, 'floor': floor,
                            'layout': layout, 'size_m2': size, 'total_rent': rent + admin,
                            'key_money': key_money, 'deposit': deposit, 'image_url': img_url, 'link': link
                        })
                    except: continue

        except Exception as e:
            print(f"Error page {page}: {e}")

    # 2. GEOCODING PHASE (UNLIMITED + CACHED)
    df = pd.DataFrame(data)
    if df.empty: return df

    # Save raw first
    df.to_csv(OUTPUT_FILE, index=False)
    
    unique_addresses = df['address'].unique()
    cache = load_cache()
    
    # Initialize Geocoder
    geolocator = Nominatim(user_agent=f"osaka_pro_miner_{random.randint(10000,99999)}")
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=1.2) # REQUIRED for reliability
    
    total_addr = len(unique_addresses)
    
    if status_placeholder: 
        status_placeholder.info(f"🗺️  Mapping {total_addr} locations. This allows for precision analytics.")

    new_cache_entries = 0
    
    for i, addr in enumerate(unique_addresses):
        # Update Progress (40% to 100%)
        if progress_bar:
            progress = 0.4 + (i / total_addr) * 0.6
            progress_bar.progress(progress)

        # Check Cache First
        if addr in cache:
            continue # Already have it
        
        # If not in cache, fetch it
        try:
            query = f"Osaka, {addr}" if "大阪" not in addr else addr
            loc = geocode(query)
            if loc:
                cache[addr] = {'lat': loc.latitude, 'lon': loc.longitude}
                new_cache_entries += 1
                # Save periodically
                if new_cache_entries % 10 == 0:
                    save_cache(cache)
        except Exception as e:
            print(f"Geocode fail {addr}: {e}")

    # Save final cache
    if new_cache_entries > 0:
        save_cache(cache)

    # Map addresses to lat/lon
    df['lat'] = df['address'].map(lambda x: cache.get(x, {}).get('lat', None))
    df['lon'] = df['address'].map(lambda x: cache.get(x, {}).get('lon', None))
    
    df.to_csv(OUTPUT_FILE, index=False)
    
    if progress_bar: progress_bar.progress(1.0)
    return df
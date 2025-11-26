import requests
from bs4 import BeautifulSoup
import unicodedata
import re
import pandas as pd

# 1. Target URL (Osaka)
URL = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=060&bs=040&ta=27&sc=27128&sc=27102&cb=0.0&ct=9999999&et=9999999&cn=9999999&mb=0&mt=9999999&shkr1=03&shkr2=03&shkr3=03&shkr4=03&fw2=&srch_navi=1"

# 2. Headers (Pretend to be Chrome)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

def normalize_japanese(text):
    """
    Crucial for Japan: Converts '１０００' (Full width) to '1000' (Half width).
    Also removes newlines and spaces.
    """
    if not text: return ""
    # NFKC normalization converts full-width chars to standard ASCII
    return unicodedata.normalize('NFKC', text).strip()

def clean_money(text):
    text = normalize_japanese(text)
    if text == '-' or text == '': return 0
    
    # Extract all numbers
    nums = re.findall(r'(\d+\.?\d*)', text)
    if not nums: return 0
    
    val = float(nums[0])
    if '万' in text:
        return int(val * 10000)
    return int(val)

print("[-] Contacting Suumo...")
res = requests.get(URL, headers=HEADERS)
res.encoding = res.apparent_encoding # Force correct Japanese encoding

if res.status_code != 200:
    print(f"[!] Critical: Blocked by Suumo (Status {res.status_code})")
    exit()

soup = BeautifulSoup(res.text, 'html.parser')
items = soup.find_all('div', class_='cassetteitem')

print(f"[-] Found {len(items)} buildings. analyzing structure of the FIRST one...")

if len(items) == 0:
    print("[!] No buildings found. Suumo changed the layout or we are IP blocked.")
    exit()

# --- DEEP DIVE INTO THE FIRST ITEM ---
item = items[0]
name = item.find('div', class_='cassetteitem_content-title').text.strip()
print(f"   > Building Name: {name}")

# Get the table of units
tbody = item.find('table', class_='cassetteitem_other').find('tbody')
rows = tbody.find_all('tr')
print(f"   > Found {len(rows)} units in this building.")

# Process ONLY the first row without error handling to see the crash
first_row = rows[0]

# 1. Floor
# The 3rd 'td' is usually the floor.
tds = first_row.find_all('td')
# Debug: Print all columns
# for i, td in enumerate(tds):
#     print(f"     [Col {i}] {normalize_japanese(td.text)}")

floor_text = normalize_japanese(tds[2].text)
print(f"   > Raw Floor Text: {floor_text}")

# 2. Price
rent_text = first_row.find('span', class_='cassetteitem_other-emphasisui').text
admin_text = first_row.find('span', class_='cassetteitem_price--administration').text
print(f"   > Raw Rent: {rent_text} | Raw Admin: {admin_text}")

clean_rent = clean_money(rent_text)
clean_admin = clean_money(admin_text)
print(f"   > Parsed Rent: {clean_rent} + {clean_admin} = {clean_rent + clean_admin}")

# 3. Size/Layout
col_layout = tds[5] # Usually column 5
col_size = tds[6]   # Usually column 6
layout = normalize_japanese(col_layout.text)
size_text = normalize_japanese(col_size.text)
print(f"   > Layout: {layout} | Size: {size_text}")

print("\n[SUCCESS] The selectors are working! If you see values above, the logic is correct.")
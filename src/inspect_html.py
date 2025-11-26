import requests
from bs4 import BeautifulSoup

# Target Osaka
URL = "https://suumo.jp/jj/chintai/ichiran/FR301FC001/?ar=060&bs=040&ta=27&sc=27128&sc=27102&cb=0.0&ct=9999999&et=9999999&cn=9999999&mb=0&mt=9999999&shkr1=03&shkr2=03&shkr3=03&shkr4=03&fw2=&srch_navi=1"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
}

print("[-] Connecting to Suumo...")
res = requests.get(URL, headers=HEADERS)
res.encoding = res.apparent_encoding

soup = BeautifulSoup(res.text, 'html.parser')
items = soup.find_all('div', class_='cassetteitem')

if not items:
    print("[!] BLOCKED. No items found.")
    exit()

print(f"[-] Found {len(items)} buildings. Inspecting the first one...")

# Get the first building
item = items[0]
name = item.find('div', class_='cassetteitem_content-title').text.strip()
print(f"TARGET BUILDING: {name}")

# Get the first unit row
tbody = item.find('table', class_='cassetteitem_other').find('tbody')
rows = tbody.find_all('tr')
first_row = rows[0]

print("\n" + "="*50)
print("RAW HTML OF THE FIRST ROW (Copy this output!)")
print("="*50)
# This prints the actual HTML tags Suumo sent us
print(first_row.prettify()) 
print("="*50 + "\n")

# Also print what we THINK the columns are
tds = first_row.find_all('td')
print(f"Row has {len(tds)} columns.")
for i, td in enumerate(tds):
    print(f"COLUMN [{i}]: {td.get_text(strip=True)}")
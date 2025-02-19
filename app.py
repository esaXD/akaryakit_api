import requests
from bs4 import BeautifulSoup
from flask import Flask, jsonify

app = Flask(__name__)

def parse_fuel_cell(td):
    """
    Bir <td> içinde <span class="with-tax"> ve <span class="without-tax"> değerlerini bulur.
    Örnek HTML:
      <td>
        <span class="with-tax">48.10</span>
        <span class="without-tax">40.09</span>
        <sup class="without-tax">%KDV</sup>
      </td>
    Döndürdüğü sözlük:
      {"with_tax": 48.10, "without_tax": 40.09}
    """
    with_tax_el = td.find("span", {"class": "with-tax"})
    without_tax_el = td.find("span", {"class": "without-tax"})
    
    def to_float(text):
        """ '48.10' veya '40,09' gibi metni float'a çevirir, yoksa None döner. """
        if not text:
            return None
        text = text.strip().replace(",", ".")
        # İçinde rakamlardan başka karakter varsa temizleyelim (TL/LT gibi)
        import re
        match = re.search(r"\d+(\.\d+)?", text)
        if match:
            return float(match.group(0))
        return None
    
    with_tax = to_float(with_tax_el.get_text(strip=True) if with_tax_el else "")
    without_tax = to_float(without_tax_el.get_text(strip=True) if without_tax_el else "")
    
    return {
        "with_tax": with_tax,
        "without_tax": without_tax
    }

def fetch_kayseri_fiyatlari():
    url = "https://www.petrolofisi.com.tr/akaryakit-fiyatlari/kayseri-akaryakit-fiyatlari"
    
    # Bazı siteler user-agent ister, ekleyelim
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/90.0.4430.93 Safari/537.36"
        )
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
    except Exception as e:
        print(f"İstek hatası: {e}")
        return None
    
    if response.status_code != 200:
        print(f"HTTP Hatası: {response.status_code}")
        return None
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # 1) İlgili tabloyu bul
    table = soup.find("table", {"class": "table-prices"})
    if not table:
        print("Tablo bulunamadı (table-prices).")
        return None
    
    tbody = table.find("tbody")
    if not tbody:
        print("Tablonun <tbody> bölümü bulunamadı.")
        return None
    
    # 2) Tüm satırları çek (ör. <tr class="price-row district-xxxxx" ...>)
    rows = tbody.find_all("tr", {"class": lambda c: c and "price-row" in c})
    if not rows:
        print("Fiyat satırları bulunamadı. (price-row)")
        return None
    
    results = []
    
    for row in rows:
        # <tr class="price-row district-03801" data-district-id="03801" data-district-name="AKKISLA">
        district_id = row.get("data-district-id", "").strip()
        district_name = row.get("data-district-name", "").strip()
        
        # Tüm sütunları alalım
        tds = row.find_all("td")
        # Beklenen yapı: 4 sütun
        # 0 --> İlçe Adı
        # 1 --> V/Max Kurşunsuz 95
        # 2 --> V/Max Diesel
        # 3 --> PO/gaz Otogaz
        if len(tds) < 4:
            continue
        
        # İlçe adı, bazen tds[0].get_text(strip=True) ile de alınabilir;
        # ancak "data-district-name" meta bilgisini kullandığımız için opsiyonel.
        # city_name = tds[0].get_text(strip=True)
        
        # Her yakıt türü için parse_fuel_cell fonksiyonunu çağıralım
        kursunsuz_95_data = parse_fuel_cell(tds[1])
        diesel_data = parse_fuel_cell(tds[2])
        otogaz_data = parse_fuel_cell(tds[3])
        
        # Sonuç sözlüğü
        row_data = {
            "district_id": district_id,
            "district_name": district_name,
            "kursunsuz_95": kursunsuz_95_data,
            "diesel": diesel_data,
            "otogaz": otogaz_data
        }
        
        results.append(row_data)
    
    return results

@app.route("/api/akaryakit-fiyatlari/kayseri", methods=["GET"])
def get_kayseri_fiyatlari():
    data = fetch_kayseri_fiyatlari()
    if not data:
        return jsonify({"error": "Veriler çekilemedi veya sayfa yapısında değişiklik var."}), 500
    return jsonify(data)

if __name__ == "__main__":
    app.run(debug=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from shapely.geometry import Point, LineString
import uvicorn
import json
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

class Koordinat(BaseModel):
    lat: float
    lon: float

class RotaIstegi(BaseModel):
    rota_noktalari: List[Koordinat]

# BAŞLANGIÇTA VERİTABANLARINI YÜKLE (IN-MEMORY)
with open("giseler.json", "r", encoding="utf-8") as f:
    tum_giseler = json.load(f)
    # Geofencing motoru için düz bir sözlük oluşturuyoruz
    giseler_db = tum_giseler["Anadolu_Otoyolu"]

with open("fiyatlar.json", "r", encoding="utf-8") as f:
    fiyat_matrisi = json.load(f)

@app.post("/hesapla")
def ucret_hesapla(istek: RotaIstegi):
    rota_cizgisi = LineString([(nokta.lon, nokta.lat) for nokta in istek.rota_noktalari])
    temas_edilen_giseler = []
    TOLERANS = 0.001 

    # Geofencing: 34 Gişenin tamamını tarar
    for gise_adi, koordinat in giseler_db.items():
        lat, lon = koordinat
        gise_noktasi = Point(lon, lat)
        if rota_cizgisi.intersects(gise_noktasi.buffer(TOLERANS)):
            mesafe_sirasi = rota_cizgisi.project(gise_noktasi)
            temas_edilen_giseler.append((mesafe_sirasi, gise_adi))

    if len(temas_edilen_giseler) >= 2:
        temas_edilen_giseler.sort()
        giris = temas_edilen_giseler[0][1]
        cikis = temas_edilen_giseler[-1][1]
        
        # Hata Ayıklama (Loglama) İçin
        print(f"Giriş: {giris}, Çıkış: {cikis}")
        
        try:
            # Önce A'dan B'ye bak, yoksa B'den A'ya bak (Dönüş yolu matrisi için)
            ucret = fiyat_matrisi.get(giris, {}).get(cikis)
            if ucret is None:
                ucret = fiyat_matrisi.get(cikis, {}).get(giris)
                
            if ucret is not None:
                return {"durum": "basarili", "giris": giris, "cikis": cikis, "tutar": ucret}
            else:
                return {"durum": "hata", "mesaj": f"Gişeler tespit edildi ({giris} -> {cikis}) ancak fiyat veritabanında yok."}
        except Exception as e:
            return {"durum": "hata", "mesaj": "Sistem hatası: Fiyat hesaplanamadı."}
    else:
        return {"durum": "hata", "mesaj": "Rota üzerinde gişe tespit edilmedi."}

if __name__ == "__main__":
    import os
    # Render'ın verdiği portu al, yoksa 8000 kullan
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

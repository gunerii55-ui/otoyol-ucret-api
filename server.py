from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from shapely.geometry import Point, LineString
import uvicorn
import json
import os

app = FastAPI()

# CORS Ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

# Veri Modelleri
class Koordinat(BaseModel):
    lat: float
    lon: float

class RotaIstegi(BaseModel):
    rota_noktalari: List[Koordinat]
    arac_sinifi: str

# Veritabanlarını Yükle
with open("giseler.json", "r", encoding="utf-8") as f:
    giseler_db = json.load(f)["Anadolu_Otoyolu"]

with open("fiyatlar.json", "r", encoding="utf-8") as f:
    fiyat_matrisi = json.load(f)

@app.post("/hesapla")
def ucret_hesapla(istek: RotaIstegi):
    try:
        # Rota Çizgisi Oluştur
        rota_cizgisi = LineString([(n.lon, n.lat) for n in istek.rota_noktalari])
        temas_edilen_giseler = []
        TOLERANS = 0.001 

        # Geofencing Taraması
        for gise_adi, koordinat in giseler_db.items():
            gise_noktasi = Point(koordinat[1], koordinat[0])
            if rota_cizgisi.intersects(gise_noktasi.buffer(TOLERANS)):
                mesafe_sirasi = rota_cizgisi.project(gise_noktasi)
                temas_edilen_giseler.append((mesafe_sirasi, gise_adi))

        if len(temas_edilen_giseler) >= 2:
            temas_edilen_giseler.sort()
            giris = temas_edilen_giseler[0][1]
            cikis = temas_edilen_giseler[-1][1]
            
        # Fiyat Matrisi Sorgusu
            gise_verisi = fiyat_matrisi.get(giris, {}).get(cikis)
            if not gise_verisi:
                gise_verisi = fiyat_matrisi.get(cikis, {}).get(giris)
            
            # BURASI KRİTİK: gise_verisi artık bir sayı değil, bir sözlük olmalı
            if gise_verisi and isinstance(gise_verisi, dict):
                ucret = gise_verisi.get(istek.arac_sinifi)
                if ucret:
                    return {
                        "durum": "basarili", 
                        "giris": giris, 
                        "cikis": cikis, 
                        "tutar": ucret, 
                        "sinif": istek.arac_sinifi
                    }
            
            return {"durum": "hata", "mesaj": f"Fiyat bulunamadı: {giris} - {cikis}"}
        
        return {"durum": "hata", "mesaj": "Rota üzerinde gişe tespit edilmedi."}

    except Exception as e:
        return {"durum": "hata", "mesaj": f"Sistem Hatası: {str(e)}"}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

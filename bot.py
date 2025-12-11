import requests
import pandas as pd
import schedule
import time
import asyncio
import os
from datetime import datetime, timedelta
from telegram import Bot

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "TOKEN_DARI_COOLIFY")
CHAT_ID = os.getenv("CHAT_ID", "ID_DARI_COOLIFY")
GOAPI_KEY = os.getenv("GOAPI_KEY", "KEY_DARI_COOLIFY")

# --- FUNGSI 1: AMBIL DAFTAR SAHAM OTOMATIS ---
def get_dynamic_tickers():
    """
    Mengambil daftar saham LQ45 atau IDX80 agar list selalu update.
    Menggunakan Index LQ45 biar aman & likuid (Value > 5M pasti lolos).
    """
    print("🔄 Mengambil daftar saham terbaru (LQ45)...")
    
    # Endpoint Index GoAPI
    url = f"https://api.goapi.io/stock/idx/index/LQ45" 
    params = {"api_key": GOAPI_KEY}
    
    try:
        res = requests.get(url, params=params, timeout=10).json()
        
        if res.get('status') == 'success' and 'data' in res and 'results' in res['data']:
            # Ambil hanya simbol sahamnya
            tickers = [item['symbol'] for item in res['data']['results']]
            print(f"✅ Berhasil dapat {len(tickers)} saham likuid.")
            
            # Tambahan Manual: Saham favorit BSJP yang kadang keluar masuk LQ45
            favorites = ["BUMI", "DEWA", "ENRG", "BRMS"]
            for fav in favorites:
                if fav not in tickers:
                    tickers.append(fav)
            
            return tickers
            
    except Exception as e:
        print(f"❌ Gagal ambil list otomatis: {e}")
        # Fallback: Kalau API error, pakai list darurat ini
        return ["BBRI", "BBCA", "BMRI", "TLKM", "ASII", "ADRO", "UNTR", "GOTO", "EMTK", "AMMN"]

    return []

# --- FUNGSI 2: KIRIM TELEGRAM ---
async def send_telegram(message):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"Gagal kirim telegram: {e}")

# --- FUNGSI 3: AMBIL DATA HISTORIS ---
def get_goapi_data(ticker):
    # Ambil data 6 bulan terakhir cukup
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")
    
    url = f"https://api.goapi.io/stock/idx/{ticker}/historical"
    params = {
        "api_key": GOAPI_KEY,
        "from": start_date,
        "to": end_date
    }
    
    try:
        res = requests.get(url, params=params, timeout=10).json()
        if res.get('status') == 'success' and 'results' in res['data']:
            df = pd.DataFrame(res['data']['results'])
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date') 
            return df
    except Exception as e:
        print(f"Error {ticker}: {e}")
    
    return None

# --- FUNGSI UTAMA: SCREENER ---
def screener_engine():
    # 1. Ambil List Saham Dulu (Dinamis)
    saham_list = get_dynamic_tickers()
    
    print(f"🚀 Memulai Screening untuk {len(saham_list)} saham...")
    laporan = []

    for ticker in saham_list:
        df = get_goapi_data(ticker)
        
        # Skip jika data kosong/pendek
        if df is None or len(df) < 20: 
            time.sleep(0.2)
            continue

        try:
            # --- RUMUS PDF STOCKBIT ---
            df['MA5'] = df['close'].rolling(window=5).mean()
            df['VolMA20'] = df['volume'].rolling(window=20).mean()
            
            # Cari High 52 Minggu (Setahun)
            # Jika data < 250 hari, pakai max dari data yang ada
            window_high = 250 if len(df) >= 250 else len(df)
            df['High52W'] = df['high'].rolling(window=window_high).max()

            last = df.iloc[-1]
            prev = df.iloc[-2]

            # RULES
            # 1. Harga > 50 (Bukan gocap mati)
            rule_price = last['close'] > 50
            
            # 2. Transaksi Liquid (Value > 5 Miliar)
            rule_value = (last['close'] * last['volume']) > 5_000_000_000
            
            # 3. Uptrend (Harga > MA5)
            rule_uptrend = last['close'] > last['MA5']
            
            # 4. Volume Spike (> 2x Rata-rata)
            rule_volume = last['volume'] > (2 * last['VolMA20'])
            
            # 5. Harga Hijau (Naik dari kemarin)
            rule_green = last['close'] > prev['close']
            
            # 6. Posisi Harga (Dekat High - minimal 70% dari pucuk)
            high_val = last['High52W'] if not pd.isna(last['High52W']) else df['high'].max()
            rule_posisi = last['close'] > (high_val * 0.7)

            if rule_price and rule_value and rule_uptrend and rule_volume and rule_green and rule_posisi:
                spike = last['volume'] / last['VolMA20']
                buy = int(last['close'])
                tp = int(buy * 1.03)
                sl = int(buy * 0.98)

                msg = (
                    f"💎 **{ticker}**\n"
                    f"Harga: {buy}\n"
                    f"Vol Spike: {spike:.1f}x 🚀\n"
                    f"TP: {tp} | SL: {sl}"
                )
                laporan.append(msg)
                
        except Exception as e:
            pass

        # Jeda biar API GoAPI gak marah (Rate Limit)
        # LQ45 ada 45 saham x 0.5 detik = 22 detik selesai. Masih aman.
        time.sleep(0.5)

    return laporan

# --- SCHEDULER ---
def job_harian():
    print("⏰ Waktunya Screening BSJP (14:50 WIB)")
    hasil = screener_engine()
    
    if hasil:
        pesan_final = "🚨 **SINYAL BSJP OTOMATIS** 🚨\n(List LQ45 + Favorit)\n\n" + "\n\n".join(hasil)
        asyncio.run(send_telegram(pesan_final))
    else:
        asyncio.run(send_telegram("😴 Zonk. Tidak ada saham LQ45 yang lolos kriteria BSJP hari ini."))

# Jalankan setiap hari pukul 14:50 WIB
schedule.every().day.at("14:50").do(job_harian)

print("🤖 Bot Auto-List Berjalan... Menunggu 14:50 WIB...")
asyncio.run(send_telegram("✅ Bot BSJP Auto-List Aktif!"))

while True:
    schedule.run_pending()
    time.sleep(60)
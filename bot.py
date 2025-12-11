import requests
import pandas as pd
import pandas_ta as ta
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

# --- FUNGSI BANTUAN ---

def get_dynamic_tickers():
    """Mengambil daftar saham LQ45 + Favorit"""
    url = f"https://api.goapi.io/stock/idx/index/LQ45" 
    params = {"api_key": GOAPI_KEY}
    try:
        res = requests.get(url, params=params, timeout=10).json()
        if res.get('status') == 'success':
            tickers = [item['symbol'] for item in res['data']['results']]
            # Tambahan saham yang sering volatile
            favorites = ["BUMI", "DEWA", "ENRG", "BRMS", "GOTO", "ANTM", "DKFT", "PSAB"]
            for fav in favorites:
                if fav not in tickers: tickers.append(fav)
            return tickers
    except:
        # Fallback jika API error
        return ["BBRI", "BBCA", "BMRI", "TLKM", "ASII", "ADRO", "UNTR", "GOTO", "EMTK"]
    return []

async def send_telegram(message):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"Gagal kirim telegram: {e}")

def get_data(ticker):
    # Ambil data historis (cukup 300 candle untuk MA200)
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d") # Diperpanjang biar MA200 aman
    url = f"https://api.goapi.io/stock/idx/{ticker}/historical"
    params = {"api_key": GOAPI_KEY, "from": start, "to": end}
    
    try:
        res = requests.get(url, params=params, timeout=10).json()
        if res.get('status') == 'success' and 'results' in res['data']:
            df = pd.DataFrame(res['data']['results'])
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            return df
    except:
        pass
    return None

# ===========================
# 1. STRATEGI BSJP (STRICT MODE > 75% WR)
# ===========================
def strategy_bsjp(df):
    df['MA5'] = df['close'].rolling(5).mean()
    df['VolMA20'] = df['volume'].rolling(20).mean()
    last = df.iloc[-1]
    
    # Filter: Candle Solid (Anti Jarum Suntik)
    upper_wick = last['high'] - last['close']
    total_range = last['high'] - last['low']
    
    # Hindari error pembagian nol (jika saham tidak bergerak)
    if total_range == 0: return None
    
    wick_ratio = upper_wick / total_range
    val = last['close'] * last['volume']
    
    # RULES:
    # 1. Volume Meledak > 2x Rata-rata
    # 2. Harga di atas MA5 (Uptrend)
    # 3. Ekor atas < 30% (Tidak ada tekanan jual masif)
    # 4. Transaksi > 10 Miliar (Liquid only)
    
    if (last['volume'] > (2 * last['VolMA20']) and 
        last['close'] > last['MA5'] and
        wick_ratio < 0.3 and 
        val > 10_000_000_000):
        
        spike = last['volume'] / last['VolMA20']
        buy = int(last['close'])
        tp = int(buy * 1.03) 
        sl = int(buy * 0.98) 
        
        return (f"💎 *{last['symbol']}* (BSJP PREMIUM)\n"
                f"✅ Candle Solid (No Wick)\n"
                f"📈 Buy: {buy}\n"
                f"🎯 TP: {tp} | 🛑 SL: {sl}\n"
                f"Vol Spike: {spike:.1f}x 🚀")
    return None

# ===========================
# 2. STRATEGI SWING (STRICT MODE)
# ===========================
def strategy_swing(df):
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    
    # Filter: Tren Besar (MA200)
    df['MA200'] = df['close'].rolling(200).mean()
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    if pd.isna(last['MA200']): return None # Data kurang untuk MA200

    # RULES:
    # 1. MACD Golden Cross
    # 2. Harga WAJIB di atas MA200 (Hanya saham Uptrend Jangka Panjang)
    
    if (last['MACD_12_26_9'] > last['MACDs_12_26_9'] and 
        prev['MACD_12_26_9'] <= prev['MACDs_12_26_9'] and
        last['close'] > last['MA200']): 
        
        buy = int(last['close'])
        tp = int(buy * 1.10)
        sl = int(buy * 0.95)
        
        return (f"🌊 *{last['symbol']}* (SWING PRO)\n"
                f"✅ Trend: Bullish (> MA200)\n"
                f"📈 Buy Area: {buy}\n"
                f"🎯 TP: {tp} | 🛑 SL: {sl}\n"
                f"Sinyal: MACD Golden Cross")
    return None

# ===========================
# 3. STRATEGI SCALPING (STRICT MODE)
# ===========================
def strategy_scalping(df):
    df['RSI'] = df.ta.rsi(length=14)
    last = df.iloc[-1]
    
    # RULES:
    # 1. RSI Oversold < 30
    # 2. Candle Hijau (Close > Open) -> Konfirmasi pantulan
    # 3. Liquid (> 2 Miliar)
    
    if (last['RSI'] < 30 and 
        last['close'] > last['open'] and 
        (last['close'] * last['volume']) > 2_000_000_000):
        
        buy = int(last['close'])
        tp = int(buy * 1.02)
        sl = int(buy * 0.99)
        
        return (f"⚡ *{last['symbol']}* (SCALPING SNIPER)\n"
                f"✅ Konfirmasi Rebound (Hijau)\n"
                f"📈 Buy: {buy}\n"
                f"🎯 TP: {tp} | 🛑 SL: {sl}\n"
                f"RSI: {last['RSI']:.1f}")
    return None

# --- ENGINE UTAMA ---
def run_scanner(mode="BSJP"):
    tickers = get_dynamic_tickers()
    print(f"🔎 Scanning {len(tickers)} saham untuk mode {mode}...")
    laporan = []
    
    for ticker in tickers:
        df = get_data(ticker)
        if df is None or len(df) < 50: 
            time.sleep(0.2)
            continue
        
        df['symbol'] = ticker
        msg = None
        
        if mode == "BSJP": msg = strategy_bsjp(df)
        elif mode == "SWING": msg = strategy_swing(df)
        elif mode == "SCALPING": msg = strategy_scalping(df)
            
        if msg: laporan.append(msg)
        time.sleep(0.5) # Jeda API
        
    if laporan:
        header = f"🚀 **SINYAL {mode}** 🚀\n\n"
        asyncio.run(send_telegram(header + "\n\n".join(laporan)))
    elif mode == "BSJP": 
        # Hanya BSJP yang lapor kalau kosong, scalping jangan berisik
        asyncio.run(send_telegram(f"😴 Mode {mode}: Tidak ada sinyal (Strict Filter)."))

# --- JADWAL KERJA ---

# 1. BSJP: Jam 14:50
schedule.every().day.at("14:50").do(run_scanner, mode="BSJP")

# 2. SWING: Jam 16:15
schedule.every().day.at("16:15").do(run_scanner, mode="SWING")

# 3. SCALPING: Setiap 30 Menit (Jam 9-15)
def job_scalping_intraday():
    jam = datetime.now().hour 
    if 9 <= jam < 15: 
        run_scanner(mode="SCALPING")

schedule.every(30).minutes.do(job_scalping_intraday)

print("🤖 Super Bot (STRICT MODE) Aktif!")
asyncio.run(send_telegram("✅ Super Bot (Strict Mode) Aktif!\nFilter diperketat untuk Winrate Tinggi."))

while True:
    schedule.run_pending()
    time.sleep(60)

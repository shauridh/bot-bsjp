import matplotlib
matplotlib.use('Agg') 
import mplfinance as mpf
import requests
import pandas as pd
import pandas_ta as ta
import time
import asyncio
import os
import io
from datetime import datetime, timedelta, timezone
from telegram import Bot

# --- KONFIGURASI ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "TOKEN_DARI_COOLIFY")
CHAT_ID = os.getenv("CHAT_ID", "ID_DARI_COOLIFY")
GOAPI_KEY = os.getenv("GOAPI_KEY", "KEY_DARI_COOLIFY")

# --- CHARTING ---
def generate_chart(df, ticker, buy, tp, sl, title_p):
    try:
        subset = df.tail(60).copy()
        mc = mpf.make_marketcolors(up='#2ebd85', down='#f6465d', edge='inherit', volume='in')
        s = mpf.make_mpf_style(marketcolors=mc, style='nightclouds')
        
        buf = io.BytesIO()
        title = f"{ticker} ({title_p})\nBuy:{buy} TP:{tp} SL:{sl}"
        
        mpf.plot(
            subset, type='candle', style=s, title=title,
            ylabel='Harga', volume=True,
            hlines=dict(hlines=[buy, tp, sl], colors=['cyan', 'lime', 'red'], linewidths=[1,1,1], linestyle='-.'),
            savefig=dict(fname=buf, dpi=80, bbox_inches='tight'),
            tight_layout=True
        )
        buf.seek(0)
        return buf
    except:
        return None

# --- TELEGRAM ---
async def send_signal(message, chart_buffer=None):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        if chart_buffer:
            await bot.send_photo(chat_id=CHAT_ID, photo=chart_buffer, caption=message, parse_mode='Markdown')
        else:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ Gagal kirim: {e}")

# --- DATA ---
def get_dynamic_tickers():
    url = f"https://api.goapi.io/stock/idx/index/LQ45" 
    params = {"api_key": GOAPI_KEY}
    try:
        res = requests.get(url, params=params, timeout=10).json()
        if res.get('status') == 'success':
            tickers = [item['symbol'] for item in res['data']['results']]
            # Tambah saham volatil favorit
            favorites = ["BUMI", "DEWA", "ENRG", "BRMS", "GOTO", "ANTM", "PSAB", "ADRO"]
            for fav in favorites:
                if fav not in tickers: tickers.append(fav)
            return tickers
    except:
        return ["BBRI", "BBCA", "BMRI", "TLKM", "ASII", "ADRO", "GOTO", "EMTK"]
    return []

def get_data(ticker):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
    url = f"https://api.goapi.io/stock/idx/{ticker}/historical"
    params = {"api_key": GOAPI_KEY, "from": start, "to": end}
    try:
        res = requests.get(url, params=params, timeout=10).json()
        if res.get('status') == 'success' and 'results' in res['data']:
            df = pd.DataFrame(res['data']['results'])
            cols = ['open', 'high', 'low', 'close', 'volume']
            df[cols] = df[cols].apply(pd.to_numeric)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            return df.sort_index()
    except:
        pass
    return None

# --- STRATEGI BARU (SESI 1 & 2) ---

def check_session_momentum(df, ticker, sesi):
    """Strategi Momentum untuk Sesi 1 & 2 (Cari yang lagi Hype)"""
    df['MA5'] = df['close'].rolling(5).mean()
    df['VolMA5'] = df['volume'].rolling(5).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. Harga Naik > 1% hari ini
    change_pct = (last['close'] - prev['close']) / prev['close']
    
    # 2. Volume kuat (> Rata2 5 hari)
    vol_strong = last['volume'] > last['VolMA5']
    
    # 3. Uptrend jangka pendek (Diatas MA5)
    uptrend = last['close'] > last['MA5']
    
    if change_pct > 0.01 and vol_strong and uptrend:
        buy = int(last['close'])
        tp = int(buy * 1.03) # TP 3%
        sl = int(buy * 0.98) # SL 2%
        
        icon = "☀️" if sesi == 1 else "🌤️"
        msg = (f"{icon} *{ticker}* (PICK SESI {sesi})\n"
               f"✅ Momentum: Naik {change_pct*100:.1f}%\n"
               f"📈 Buy: {buy}\n"
               f"🎯 TP: {tp} | 🛑 SL: {sl}")
        return msg, generate_chart(df, ticker, buy, tp, sl, f"SESI {sesi}")
    
    return None, None

def check_bsjp(df, ticker):
    """Beli Sore Jual Pagi"""
    df['MA5'] = df['close'].rolling(5).mean()
    df['VolMA20'] = df['volume'].rolling(20).mean()
    last = df.iloc[-1]
    
    if (last['volume'] > (2 * last['VolMA20']) and 
        last['close'] > last['MA5']):
        buy = int(last['close'])
        msg = (f"💎 *{ticker}* (BSJP)\n📈 Buy: {buy}\n🎯 TP: {int(buy*1.03)} | 🛑 SL: {int(buy*0.98)}\nVol Spike 🚀")
        return msg, generate_chart(df, ticker, buy, int(buy*1.03), int(buy*0.98), "BSJP")
    return None, None

def run_scanner(mode="MOMENTUM", sesi=1):
    tickers = get_dynamic_tickers()
    print(f"🔎 Scanning {len(tickers)} saham.. Mode: {mode} Sesi {sesi}")
    
    count = 0
    for ticker in tickers:
        df = get_data(ticker)
        if df is None or len(df) < 20: 
            time.sleep(0.1)
            continue
        
        msg, chart = None, None
        
        if mode == "MOMENTUM":
            msg, chart = check_session_momentum(df, ticker, sesi)
        elif mode == "BSJP":
            msg, chart = check_bsjp(df, ticker)
            
        if msg:
            asyncio.run(send_signal(msg, chart))
            count += 1
            time.sleep(1) # Jeda kirim
        
        time.sleep(0.2) # Jeda API
    
    if count == 0:
        print("   -> Nihil (Tidak ada sinyal)")

# --- MAIN LOOP (SCHEDULER MANUAL) ---
print("🤖 Super Bot (Session Picks) Aktif!")
asyncio.run(send_signal("✅ Bot Aktif! Siap kirim Picks Sesi 1 & 2."))

last_run_minute = -1

while True:
    # 1. Ambil Waktu WIB Terkini
    now_utc = datetime.now(timezone.utc)
    now_wib = now_utc + timedelta(hours=7)
    jam = now_wib.hour
    menit = now_wib.minute
    hari = now_wib.weekday() # 0=Senin, 4=Jumat, 5=Sabtu, 6=Minggu
    
    # Cek Log setiap menit baru
    if menit != last_run_minute:
        print(f"⏳ Jam WIB: {now_wib.strftime('%H:%M')} | Menunggu Jadwal...")
        last_run_minute = menit
        
        # --- JADWAL EKSEKUSI ---
        # Hanya jalan Senin-Jumat
        if hari < 5:
            
            # SESI 1 PICKS (Jam 09:15 & 10:00)
            if (jam == 9 and menit == 15) or (jam == 10 and menit == 0):
                run_scanner(mode="MOMENTUM", sesi=1)
                
            # SESI 2 PICKS (Jam 13:45 & 14:15)
            elif (jam == 13 and menit == 45) or (jam == 14 and menit == 15):
                run_scanner(mode="MOMENTUM", sesi=2)
                
            # BSJP (Jam 14:50)
            elif jam == 14 and menit == 50:
                run_scanner(mode="BSJP")
                
            # FORCE CHECK (Buat tes sekarang)
            # Anda bisa hapus ini nanti.
            # Jika jam sekarang = 10:45 (misal), dia akan jalan.
    
    time.sleep(10) # Cek waktu setiap 10 detik

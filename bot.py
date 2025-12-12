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
def generate_chart(df, ticker, buy, tp, sl, title_extra=""):
    try:
        subset = df.tail(60).copy()
        mc = mpf.make_marketcolors(up='#2ebd85', down='#f6465d', edge='inherit', volume='in')
        s = mpf.make_mpf_style(marketcolors=mc, style='nightclouds')
        
        buf = io.BytesIO()
        title = f"{ticker} {title_extra}\nBuy:{buy} TP:{tp} SL:{sl}"
        
        mpf.plot(
            subset, type='candle', style=s, title=title,
            ylabel='Harga', volume=True,
            hlines=dict(hlines=[buy, tp, sl], colors=['cyan', 'lime', 'red'], linewidths=[1.5,1.5,1.5], linestyle='-.'),
            savefig=dict(fname=buf, dpi=80, bbox_inches='tight'),
            tight_layout=True
        )
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"Gagal Chart: {e}")
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
def get_data(ticker):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
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

# --- LOGIKA BSJP ---
def check_bsjp_screener(df, ticker, is_test=False):
    # Hitung Indikator
    df['MA5'] = df['close'].rolling(5).mean()
    df['VolMA20'] = df['volume'].rolling(20).mean()
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Logic Perhitungan
    year_high = df['high'].tail(250).max()
    near_high_ratio = last['close'] / year_high
    vol_change = last['volume'] / prev['volume'] if prev['volume'] > 0 else 0
    
    # SYARAT (Rule)
    cond1 = vol_change > 1.0 
    cond2 = last['close'] > 50
    cond3 = near_high_ratio > 0.7
    cond4 = (last['close'] * last['volume']) > 5_000_000_000
    cond5 = last['close'] > last['MA5']
    cond6 = last['volume'] > (2 * last['VolMA20'])
    cond7 = last['close'] >= last['open']

    # Jika ini Mode TEST, kita paksa True agar sinyal terkirim
    if is_test:
        print(f"🧪 {ticker}: Mode Test aktif. Memaksa sinyal dikirim...")
        cond1=cond2=cond3=cond4=cond5=cond6=cond7=True

    if cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7:
        buy = int(last['close'])
        tp = int(buy * 1.03) 
        sl = int(buy * 0.97) 
        
        label = "(TEST MODE)" if is_test else "(BSJP ELITE)"
        
        msg = (f"💎 *{ticker}* {label}\n"
               f"✅ Vol Spike: {last['volume']/last['VolMA20']:.1f}x Rata2\n"
               f"✅ Near High: {near_high_ratio*100:.0f}%\n"
               f"📈 Buy: {buy}\n"
               f"🎯 TP: {tp} | 🛑 SL: {sl}")
        
        return msg, generate_chart(df, ticker, buy, tp, sl, label)
        
    return None, None

# --- FUNGSI SIMULASI DUMMY ---
def run_simulation():
    ticker_dummy = "BBRI" # Kita pakai BBRI sebagai kelinci percobaan
    print(f"🧪 Memulai Simulasi Dummy Data pada {ticker_dummy}...")
    
    df = get_data(ticker_dummy)
    
    if df is not None:
        # --- REKAYASA DATA (DUMMY) ---
        # Kita ubah baris terakhir seolah-olah BBRI hari ini meledak
        last_idx = df.index[-1]
        
        # 1. Bikin harga naik di atas MA5
        df.at[last_idx, 'close'] = df.at[last_idx, 'open'] * 1.05 # Naik 5%
        
        # 2. Bikin Volume meledak 10x lipat
        avg_vol = df['volume'].mean()
        df.at[last_idx, 'volume'] = avg_vol * 10 
        
        # 3. Kirim ke Scanner dengan flag is_test=True
        msg, chart = check_bsjp_screener(df, ticker_dummy, is_test=True)
        
        if msg:
            asyncio.run(send_signal(msg, chart))
            print("✅ Simulasi Berhasil! Cek Telegram Anda.")
        else:
            print("❌ Simulasi Gagal (Logic Error).")
    else:
        print("❌ Gagal ambil data BBRI untuk simulasi.")

# --- MAIN EXECUTION ---
print("🤖 Bot Aktif!")

# JALANKAN SIMULASI SEKARANG JUGA
run_simulation()

# Masuk ke Loop standby (agar container tidak mati)
while True:
    time.sleep(60)

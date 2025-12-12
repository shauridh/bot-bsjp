import matplotlib
matplotlib.use('Agg') # Wajib untuk VPS tanpa layar
import mplfinance as mpf
import requests
import pandas as pd
import pandas_ta as ta
import schedule
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

# --- FUNGSI CHART GENERATOR ---
def generate_chart(df, ticker, buy_price, tp_price, sl_price, signal_type):
    try:
        subset = df.tail(60).copy()
        
        # Style Chart
        mc = mpf.make_marketcolors(up='#2ebd85', down='#f6465d', edge='inherit', wick='inherit', volume='in')
        s = mpf.make_mpf_style(marketcolors=mc, style='nightclouds', gridstyle=':')
        
        # Buffer gambar
        buf = io.BytesIO()
        title = f"{ticker} - {signal_type}\nBuy: {buy_price} | TP: {tp_price} | SL: {sl_price}"
        
        mpf.plot(
            subset, type='candle', style=s, title=title,
            ylabel='Harga', volume=True, ylabel_lower='Vol',
            hlines=dict(hlines=[buy_price, tp_price, sl_price], colors=['cyan', 'lime', 'red'], linewidths=[1.5, 1.5, 1.5], linestyle='-.'),
            savefig=dict(fname=buf, dpi=100, bbox_inches='tight'),
            tight_layout=True, warn_too_much_data=1000
        )
        buf.seek(0)
        return buf
    except Exception as e:
        print(f"❌ Gagal bikin chart {ticker}: {e}")
        return None

# --- TELEGRAM SENDER ---
async def send_signal(message, chart_buffer=None):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        if chart_buffer:
            await bot.send_photo(chat_id=CHAT_ID, photo=chart_buffer, caption=message, parse_mode='Markdown')
        else:
            await bot.send_message(chat_id=CHAT_ID, text=message, parse_mode='Markdown')
    except Exception as e:
        print(f"❌ Gagal kirim telegram: {e}")

# --- DATA FEED ---
def get_dynamic_tickers():
    # Ambil data LQ45 + Saham Favorit
    url = f"https://api.goapi.io/stock/idx/index/LQ45" 
    params = {"api_key": GOAPI_KEY}
    try:
        res = requests.get(url, params=params, timeout=10).json()
        if res.get('status') == 'success':
            tickers = [item['symbol'] for item in res['data']['results']]
            favorites = ["BUMI", "DEWA", "ENRG", "BRMS", "GOTO", "ANTM", "DKFT", "PSAB", "ADRO", "PTBA"]
            for fav in favorites:
                if fav not in tickers: tickers.append(fav)
            return tickers
    except:
        return ["BBRI", "BBCA", "BMRI", "TLKM", "ASII", "ADRO", "UNTR", "GOTO", "EMTK"]
    return []

def get_data(ticker):
    end = datetime.now().strftime("%Y-%m-%d")
    start = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")
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
            df = df.sort_index()
            return df
    except:
        pass
    return None

# --- STRATEGI (STRICT MODE) ---

def check_bsjp(df, ticker):
    df['MA5'] = df['close'].rolling(5).mean()
    df['VolMA20'] = df['volume'].rolling(20).mean()
    last = df.iloc[-1]
    
    upper_wick = last['high'] - last['close']
    total_range = last['high'] - last['low']
    if total_range == 0: return None, None
    wick_ratio = upper_wick / total_range
    val = last['close'] * last['volume']
    
    if (last['volume'] > (2 * last['VolMA20']) and 
        last['close'] > last['MA5'] and
        wick_ratio < 0.35 and 
        val > 10_000_000_000):
        
        spike = last['volume'] / last['VolMA20']
        buy = int(last['close'])
        tp = int(buy * 1.03) 
        sl = int(buy * 0.98) 
        
        msg = (f"💎 *{ticker}* (BSJP PREMIUM)\n"
               f"✅ Candle Solid (No Wick)\n"
               f"📈 Buy: {buy} | 🎯 TP: {tp} | 🛑 SL: {sl}\n"
               f"Vol Spike: {spike:.1f}x 🚀")
        return msg, generate_chart(df, ticker, buy, tp, sl, "BSJP")
    return None, None

def check_swing(df, ticker):
    macd = df.ta.macd(fast=12, slow=26, signal=9)
    df = pd.concat([df, macd], axis=1)
    df['MA200'] = df['close'].rolling(200).mean()
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    if pd.isna(last['MA200']): return None, None

    if (last['MACD_12_26_9'] > last['MACDs_12_26_9'] and 
        prev['MACD_12_26_9'] <= prev['MACDs_12_26_9'] and
        last['close'] > last['MA200']): 
        
        buy = int(last['close'])
        tp = int(buy * 1.10)
        sl = int(buy * 0.95)
        
        msg = (f"🌊 *{ticker}* (SWING PRO)\n"
               f"✅ Trend: Bullish (> MA200)\n"
               f"📈 Buy Area: {buy}\n"
               f"🎯 TP: {tp} | 🛑 SL: {sl}\n"
               f"Sinyal: MACD Golden Cross")
        return msg, generate_chart(df, ticker, buy, tp, sl, "SWING")
    return None, None

def check_scalping(df, ticker):
    df['RSI'] = df.ta.rsi(length=14)
    last = df.iloc[-1]
    
    # Syarat Scalping: RSI < 30, Candle Hijau, Liquid
    if (last['RSI'] < 30 and 
        last['close'] > last['open'] and 
        (last['close'] * last['volume']) > 2_000_000_000):
        
        buy = int(last['close'])
        tp = int(buy * 1.02)
        sl = int(buy * 0.99)
        
        msg = (f"⚡ *{ticker}* (SCALPING SNIPER)\n"
               f"✅ Konfirmasi Rebound\n"
               f"📈 Buy: {buy} | 🎯 TP: {tp} | 🛑 SL: {sl}\n"
               f"RSI: {last['RSI']:.1f} (Oversold)")
        return msg, generate_chart(df, ticker, buy, tp, sl, "SCALPING")
    return None, None

# --- ENGINE ---
def run_scanner(mode="BSJP"):
    tickers = get_dynamic_tickers()
    print(f"🔎 Scanning {len(tickers)} saham untuk mode {mode}...")
    found_any = False
    
    for ticker in tickers:
        df = get_data(ticker)
        if df is None or len(df) < 60: 
            time.sleep(0.1)
            continue
        
        msg, chart = None, None
        if mode == "BSJP": msg, chart = check_bsjp(df, ticker)
        elif mode == "SWING": msg, chart = check_swing(df, ticker)
        elif mode == "SCALPING": msg, chart = check_scalping(df, ticker)
            
        if msg:
            found_any = True
            asyncio.run(send_signal(msg, chart))
            print(f"✅ Sinyal dikirim: {ticker}")
            time.sleep(1) 
        time.sleep(0.2) 
        
    if not found_any and mode == "BSJP":
        asyncio.run(send_signal(f"😴 Mode {mode}: Tidak ada sinyal (Strict Filter)."))

# --- SCHEDULER (UTC FIX) ---

def job_scalping_intraday():
    # Hitung Jam WIB Manual (Server UTC + 7 Jam)
    now_utc = datetime.now(timezone.utc)
    now_wib = now_utc + timedelta(hours=7)
    jam = now_wib.hour
    
    print(f"⏱️ Cek Scalping... Jam WIB: {now_wib.strftime('%H:%M')} (Server: {now_utc.strftime('%H:%M')})")
    
    if 9 <= jam < 15: 
        run_scanner(mode="SCALPING")
    else:
        print(f"zzz Pasar Tutup (Jam {jam}).")

# Jadwal
schedule.every(30).minutes.do(job_scalping_intraday)
schedule.every().day.at("14:50").do(run_scanner, mode="BSJP")
schedule.every().day.at("16:15").do(run_scanner, mode="SWING")

# Heartbeat (Cek log setiap 2 menit)
def heartbeat():
    now_wib = datetime.now(timezone.utc) + timedelta(hours=7)
    print(f"💓 Bot Hidup | WIB: {now_wib.strftime('%H:%M:%S')}")

schedule.every(2).minutes.do(heartbeat)

print("🤖 Super Bot (Visual + Timezone Fix) Aktif!")
asyncio.run(send_signal("✅ Super Bot Aktif!\nTimezone Fixed (WIB). Siap memantau pasar! 🇮🇩"))

while True:
    schedule.run_pending()
    time.sleep(30)

from binance.client import Client
import pandas as pd
import talib 
from datetime import datetime

symbol = str(input("İşlem yapmak istediğiniz coinin adını  giriniz (örn : BTCUSDT) : "))
api_key = None
api_secret = None
interval = Client.KLINE_INTERVAL_5MINUTE

client = Client(api_key, api_secret)
klines = client.futures_klines(symbol=symbol, interval=interval)
    
df = pd.DataFrame(klines, columns=["timestamp", "open", "high", "low", "close", "volume", "close_time", "quote_asset_volume", "number_of_trades", "taker_buy_base_asset_volume", "taker_buy_quote_asset_volume", "ignore"])
    
df["open"] = pd.to_numeric(df["open"])
df["high"] = pd.to_numeric(df["high"])
df["low"] = pd.to_numeric(df["low"])
df["close"] = pd.to_numeric(df["close"])
df["volume"] = pd.to_numeric(df["volume"])
df["timestamp"] = df["timestamp"].apply(lambda x: datetime.fromtimestamp(x / 1000).strftime('%Y-%m-%d %H:%M'))

# Mum Bilgileri
open = df["open"]
high = df["high"]
low = df["low"]
close = df["close"]
vol = df["volume"]
timestamp = df["timestamp"]

# Heikin Ashi Hesaplaması
ha_open = []  # Heikin-Ashi Açılış
ha_close = []  # Heikin-Ashi Kapanış
ha_high = []  # Heikin-Ashi Yüksek
ha_low = []  # Heikin-Ashi Düşük

for i in range(len(df)):
    if i == 0:
        ha_open.append(df["open"][i])
        ha_close.append((df["open"][i] + df["close"][i] + df["high"][i] + df["low"][i]) / 4)
        ha_high.append(df["high"][i])
        ha_low.append(df["low"][i])
    else:
        ha_open.append((ha_open[i - 1] + ha_close[i - 1]) / 2)
        ha_close.append((df["open"][i] + df["close"][i] + df["high"][i] + df["low"][i]) / 4)
        ha_high.append(max(df["high"][i], ha_open[i], ha_close[i]))
        ha_low.append(min(df["low"][i], ha_open[i], ha_close[i]))

df["ha_open"] = ha_open
df["ha_close"] = ha_close
df["ha_high"] = ha_high
df["ha_low"] = ha_low

def calculate_long_stop_loss(df, current_index, loss_percentage):
    # Long pozisyon için stop loss seviyesini hesaplayan işlev
    prior_red_ha_index = find_prior_red_ha_candle(df, current_index)
    if prior_red_ha_index is not None:
        return df["ha_low"][prior_red_ha_index]
    else:
        return df["close"][current_index] - (df["close"][current_index] * loss_percentage)

def calculate_short_stop_loss(df, current_index, loss_percentage):
    # Short pozisyon için stop loss seviyesini hesaplayan işlev
    prior_green_ha_index = find_prior_green_ha_candle(df, current_index)
    if prior_green_ha_index is not None:
        return df["ha_high"][prior_green_ha_index]
    else:
        return df["close"][current_index] + (df["close"][current_index] * loss_percentage)

# Hesaplanmış EMA'ları ekleyin

df["ema50"] = talib.EMA(close, timeperiod = 50)
df["ema200"] = talib.EMA(close, timeperiod = 200)

ema50 = df["ema50"]
ema200 = df["ema200"]

# RSI 
df["rsi"] = talib.RSI(close, timeperiod=14)
rsi = df["rsi"]

# Bollinger Bantları
df["upper_band"], df["middle_band"], df["lower_band"] = talib.BBANDS(close, timeperiod=20)
upper_band = df["upper_band"]
lower_band = df["lower_band"]

# ATR (Average True Range) hesaplaması
df["atr"] = talib.ATR(df["high"], df["low"], df["close"], timeperiod=14)
atr = df["atr"]

# Stokastik RSI
stoch_rsi = talib.STOCHRSI(close, timeperiod=14, fastk_period=5, fastd_period=3)
fastk = stoch_rsi[0]  # Hızlı K
fastd = stoch_rsi[1]  # Hızlı D

# ADX'i hesapla
df["adx"] = talib.ADX(df["high"], df["low"], df["close"], timeperiod=14)
adx = df["adx"]

# Başlangıç bakiyesi
cuzdan = 1000
long_position = False
short_position = False
long_entry_price = 0.0
short_entry_price = 0.0
successful_trades = 0
unsuccessful_trades = 0


def find_prior_red_ha_candle(df, current_index):
    for i in range(current_index - 1, 0, -1):
        if df["ha_open"][i] > df["ha_close"][i] and df["ha_open"][i - 1] > df["ha_close"][i - 1]:
            return i
    return None
    
def find_prior_green_ha_candle(df, current_index):
    for i in range(current_index - 1, 0, -1):
        if df["ha_open"][i] < df["ha_close"][i] and df["ha_open"][i - 1] < df["ha_close"][i - 1]:
            return i
    return None

def is_red_heikin_ashi(ha_open,ha_close,i):
    if df["ha_open"][i] > df["ha_close"][i]:
        return True
    elif df["ha_open"][i] < df["ha_close"][i]:
        return False

def is_green_heikin_ashi(ha_open,ha_close,i):
    if df["ha_open"][i] < df["ha_close"][i]:
        return True
    elif df["ha_open"][i] > df["ha_close"][i]:
        return False

def long_kar_zarar_hesapla(i, long_entry_price, long_exit_price, cuzdan, kaldirac, komisyon_orani):
    if cuzdan > 0:
        coin_miktar = (cuzdan * kaldirac) / (close[i] * (1 + komisyon_orani))
        long_kar_zarar = (long_exit_price - long_entry_price) * coin_miktar
        cuzdan += long_kar_zarar

        return cuzdan, long_kar_zarar
    else:
        uyari = "Bakiyeniz Sıfırlanmıştır!"
        return uyari

def short_kar_zarar_hesapla(i, short_entry_price, short_exit_price, cuzdan, kaldirac, komisyon_orani):
    if cuzdan > 0:
        coin_miktar = (cuzdan * kaldirac) / (close[i] * (1 + komisyon_orani))
        short_kar_zarar = (short_entry_price - short_exit_price) * coin_miktar
        cuzdan += short_kar_zarar
        return cuzdan, short_kar_zarar
    else:
        uyari = "Bakiyeniz Sıfırlanmıştır!"
        return uyari

successful_trades = 0
unsuccessful_trades = 0

for i in range(len(close)):
    # Uzun pozisyon için giriş koşulu
    if (not long_position and
        ema50[i] > ema200[i] and
        df["ha_close"][i] > ema50[i] and
        df["ha_close"][i] > df["ha_open"][i] and
        adx[i] > 25 and
        vol[i] > vol[i-1]):

        
        long_entry_price = close[i]

        # Long için SL fiyatı
        loss_percentage = 0.01  # %1 kayıp
        long_sl_price = calculate_long_stop_loss(df, i, loss_percentage)

        print(df["timestamp"][i], "tarihinde", symbol, "coinine Long girişi yapıldı. Bakiye:", cuzdan)
        print("Long SL Seviyesi:", long_sl_price)

        long_position = True
    # Long pozisyon için TP ve SL alma koşulları
    if (long_position and
        close[i] <= long_sl_price) :
        
        print(df["timestamp"][i],"tarihinde ",symbol,"için long işlem sl price ile kapatıldı satış fiyatı : ",close[i])
        cuzdan, long_kar_zarar = long_kar_zarar_hesapla(i, long_entry_price, close[i], cuzdan, 10, 0.002)
        print("işlem sonucu net kar : ", long_kar_zarar)
        print("işlem sonucunda yeni bakiye : ", cuzdan)
        unsuccessful_trades += 1
        long_position = False
    elif long_position and is_red_heikin_ashi(ha_open, ha_close, i):
        if (close[i] > long_entry_price):

            print(df["timestamp"][i],"tarihinde ",symbol,"için long işlem kırmızı ha ile kar alarak kapatıldı satış fiyatı : ",close[i])
            cuzdan, long_kar_zarar = long_kar_zarar_hesapla(i, long_entry_price, close[i], cuzdan, 10, 0.002)
            
            print("işlem sonucu net kar : ", long_kar_zarar)
            print("işlem sonucunda yeni bakiye : ", cuzdan)
            successful_trades += 1
            long_position = False
        elif (close[i] < long_entry_price):

            print(df["timestamp"][i],"tarihinde ",symbol,"için long işlem kırmızı ha ile zarar ile kapatıldı satış fiyatı : ",close[i])
            cuzdan, long_kar_zarar = long_kar_zarar_hesapla(i, long_entry_price, close[i], cuzdan, 10, 0.002)
            
            print("işlem sonucu net kar : ", long_kar_zarar)
            print("işlem sonucunda yeni bakiye : ", cuzdan)
            unsuccessful_trades += 1
            long_position = False
        
    # Short pozisyon için giriş koşulu
    if (not short_position and
        ema50[i] < ema200[i] and
        df["ha_close"][i] < ema50[i] and
        df["ha_close"][i] < df["ha_open"][i] and
        adx[i] > 25 and
        vol[i] > vol[i-1]):

        short_entry_price = close[i]

        # Short için SL fiyatı
        loss_percentage = 0.01  # %1 kayıp
        short_sl_price = calculate_short_stop_loss(df, i, loss_percentage)

        print(df["timestamp"][i], "tarihinde", symbol, "coinine Short girişi yapıldı. Bakiye", cuzdan)
        print("Short SL Seviyesi:", short_sl_price)

        short_position = True

    # Short pozisyon için TP ve SL alma koşulları
    if (short_position and 
        close[i] > short_sl_price ):
        print(df["timestamp"][i],"tarihinde short işlem kapatıldı işlem kapatma fiyatı :",close[i])
        cuzdan, short_kar_zarar = short_kar_zarar_hesapla(i, short_entry_price, close[i], cuzdan, 10, 0.002)
        
        print("işlem sonucu net kar : ", short_kar_zarar)
        print("işlem sonucunda yeni bakiye : ", cuzdan)
        unsuccessful_trades += 1
        short_position = False
    elif short_position and is_green_heikin_ashi(ha_open, ha_close, i):
        if (close[i] < short_entry_price):
            print(df["timestamp"][i],"tarihinde ",symbol,"için short işlem yeşil ha ile kar alarak kapatıldı satış fiyatı : ",close[i])
            cuzdan, short_kar_zarar = short_kar_zarar_hesapla(i, short_entry_price, close[i], cuzdan, 10, 0.002)
            
            print("işlem sonucu net kar : ", short_kar_zarar)
            print("işlem sonucunda yeni bakiye : ", cuzdan)
            successful_trades += 1
            short_position = False
        elif (close[i] > short_entry_price):
            print(df["timestamp"][i],"tarihinde ",symbol,"için short işlem yeşil ha ile zarar ile kapatıldı satış fiyatı : ",close[i])
            cuzdan, short_kar_zarar = short_kar_zarar_hesapla(i, short_entry_price, close[i], cuzdan, 10, 0.002)
            
            print("işlem sonucu net kar : ", short_kar_zarar)
            print("işlem sonucunda yeni bakiye : ", cuzdan)
            unsuccessful_trades += 1
            short_position = False


print("başarılı işlem sayısı : ",successful_trades)
print("başarısız işlem sayısı : ",unsuccessful_trades)
print("son bakiye :",cuzdan)

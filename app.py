# app.py
from flask import Flask, render_template_string, jsonify
from flask_apscheduler import APScheduler
import requests
import time
import math
import csv
import os
import collections
from datetime import datetime, UTC
import logging
from threading import Lock

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration for scheduler - UPDATED to run every minute
class Config:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = "UTC"
    SCHEDULER_JOB_DEFAULTS = {
        'coalesce': False,
        'max_instances': 1
    }

app.config.from_object(Config())

# Global variable with thread lock for data safety
latest_dashboard_data = {
    'timestamp': None,
    'html_dashboard': None,
    'raw_data': None,
    'last_update': None,
    'update_count': 0
}
data_lock = Lock()

VERSION = "BTC Dashboard v8.3 (Live - 1 Minute Updates)"

# HTML Template with 10-second auto-refresh for real-time feel
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="10">
    <title>BTC Dashboard v8.3 - Live Trading Dashboard (1min Updates)</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Courier New', 'SF Mono', 'Monaco', monospace;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #00ff9d;
            padding: 20px;
            line-height: 1.6;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .dashboard {
            background: rgba(0, 0, 0, 0.85);
            border-radius: 20px;
            padding: 25px;
            backdrop-filter: blur(10px);
            box-shadow: 0 8px 32px rgba(0, 255, 157, 0.1);
            border: 1px solid rgba(0, 255, 157, 0.3);
        }
        
        h1 {
            font-size: 1.8em;
            margin-bottom: 10px;
            text-align: center;
            color: #00ff9d;
            text-shadow: 0 0 10px rgba(0, 255, 157, 0.5);
        }
        
        .status-bar {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px;
            background: rgba(0, 0, 0, 0.5);
            border-radius: 10px;
            margin-bottom: 20px;
            font-size: 0.9em;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .update-badge {
            background: #ff3366;
            padding: 3px 8px;
            border-radius: 5px;
            font-size: 0.8em;
            animation: pulse 1s infinite;
        }
        
        .price-section {
            text-align: center;
            padding: 20px;
            margin-bottom: 20px;
            background: linear-gradient(135deg, rgba(0, 255, 157, 0.1), rgba(0, 0, 0, 0.5));
            border-radius: 15px;
        }
        
        .btc-price {
            font-size: 3em;
            font-weight: bold;
            color: #ffd700;
            text-shadow: 0 0 20px rgba(255, 215, 0, 0.5);
        }
        
        .direction {
            font-size: 1.5em;
            margin-top: 10px;
        }
        
        .grid-2 {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .card {
            background: rgba(0, 0, 0, 0.6);
            border-radius: 15px;
            padding: 20px;
            border-left: 4px solid #00ff9d;
            transition: transform 0.3s;
        }
        
        .card:hover {
            transform: translateY(-2px);
        }
        
        .card h3 {
            color: #00ff9d;
            margin-bottom: 15px;
            font-size: 1.3em;
        }
        
        .metric-row {
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .metric-label {
            color: #aaa;
        }
        
        .metric-value {
            font-weight: bold;
            color: #fff;
        }
        
        .bullish {
            color: #00ff9d;
            text-shadow: 0 0 5px rgba(0, 255, 157, 0.5);
        }
        
        .bearish {
            color: #ff3366;
            text-shadow: 0 0 5px rgba(255, 51, 102, 0.5);
        }
        
        .neutral {
            color: #ffd700;
        }
        
        .setup-box {
            background: linear-gradient(135deg, rgba(0, 255, 157, 0.2), rgba(0, 0, 0, 0.8));
            border-radius: 15px;
            padding: 20px;
            text-align: center;
            margin-top: 20px;
            border: 2px solid #00ff9d;
        }
        
        .setup-type {
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .action {
            font-size: 1.2em;
            background: rgba(0, 0, 0, 0.5);
            padding: 15px;
            border-radius: 10px;
            margin-top: 10px;
        }
        
        .badge {
            display: inline-block;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.8em;
            font-weight: bold;
        }
        
        .badge-A { background: #ffd700; color: #000; }
        .badge-B { background: #00ff9d; color: #000; }
        .badge-C { background: #ff9933; color: #000; }
        .badge-D { background: #ff3366; color: #fff; }
        
        .timestamp {
            text-align: center;
            margin-top: 20px;
            font-size: 0.8em;
            color: #888;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        @keyframes glow {
            0%, 100% { box-shadow: 0 0 5px #00ff9d; }
            50% { box-shadow: 0 0 20px #00ff9d; }
        }
        
        .live-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            background: #ff3366;
            border-radius: 50%;
            animation: pulse 1s infinite;
            margin-right: 10px;
        }
        
        .countdown {
            font-family: monospace;
            font-size: 0.9em;
            background: rgba(0,0,0,0.5);
            padding: 3px 8px;
            border-radius: 5px;
        }
        
        @media (max-width: 768px) {
            .grid-2 {
                grid-template-columns: 1fr;
            }
            .btc-price {
                font-size: 2em;
            }
            .setup-type {
                font-size: 1.3em;
            }
        }
    </style>
    <script>
        // Client-side countdown timer
        let secondsLeft = 10;
        function updateCountdown() {
            const countdownEl = document.getElementById('countdown');
            if (countdownEl) {
                countdownEl.textContent = `Next refresh in: ${secondsLeft}s`;
                secondsLeft--;
                if (secondsLeft < 0) secondsLeft = 10;
            }
        }
        setInterval(updateCountdown, 1000);
        
        // Auto-refresh data without full page reload (optional)
        function fetchNewData() {
            fetch('/api/latest')
                .then(response => response.json())
                .then(data => {
                    if (data && data.price) {
                        document.getElementById('btc-price').innerHTML = `$${data.price.toLocaleString()}`;
                    }
                })
                .catch(err => console.log('Error fetching data:', err));
        }
        // Uncomment below for AJAX updates instead of full refresh
        // setInterval(fetchNewData, 10000);
    </script>
</head>
<body>
    <div class="container">
        <div class="dashboard">
            <h1>₿ BTC COMBINED DASHBOARD — v8.3</h1>
            <h3 style="text-align:center; font-size:0.9em;">⚡ LIVE MODE: 1-MINUTE DATA UPDATES ⚡</h3>
            
            <div class="status-bar">
                <div>
                    <span class="live-indicator"></span>
                    LIVE DATA
                </div>
                <div>Last Update: {{ data.last_update or 'Waiting for data...' }}</div>
                <div>Updates: {{ data.update_count or 0 }}</div>
                <div class="countdown" id="countdown">Next refresh in: 10s</div>
            </div>
            
            {% if data %}
            <div class="price-section">
                <div class="btc-price" id="btc-price">${{ '{:,.0f}'.format(data.price) if data.price else 'N/A' }}</div>
                <div class="direction">
                    DIRECTION: 
                    <span class="{% if 'LONG' in data.direction %}bullish{% elif 'SHORT' in data.direction %}bearish{% else %}neutral{% endif %}">
                        {{ data.direction or 'N/A' }}
                    </span>
                    {% if data.confidence %} | Confidence: {{ data.confidence }}% {% endif %}
                    {% if data.grade %} | Grade: <span class="badge badge-{{ data.grade }}">{{ data.grade }}</span> {% endif %}
                </div>
            </div>
            
            <div class="grid-2">
                <div class="card">
                    <h3>📊 MODEL 1: STRUCTURE ANALYSIS</h3>
                    <div class="metric-row">
                        <span class="metric-label">Trend:</span>
                        <span class="metric-value {% if 'BULL' in data.trend_label %}bullish{% elif 'BEAR' in data.trend_label %}bearish{% endif %}">
                            {{ data.trend_label or 'N/A' }}
                        </span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">CVD Flow:</span>
                        <span class="metric-value {% if 'BUYING' in data.cvd_label %}bullish{% elif 'SELLING' in data.cvd_label %}bearish{% endif %}">
                            {{ data.cvd_label or 'N/A' }}
                        </span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Open Interest:</span>
                        <span class="metric-value">{{ data.oi_label or 'N/A' }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Spot Flow:</span>
                        <span class="metric-value">{{ data.spot_label or 'N/A' }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Smart Money:</span>
                        <span class="metric-value">{{ data.smart_label or 'N/A' }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">M1 Total Score:</span>
                        <span class="metric-value {% if data.total_score > 0 %}bullish{% elif data.total_score < 0 %}bearish{% endif %}">
                            {{ data.total_score or 'N/A' }}/100
                        </span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>⚡ MODEL 2: EXPANSION ENERGY</h3>
                    <div class="metric-row">
                        <span class="metric-label">Expansion Score:</span>
                        <span class="metric-value">{{ data.expansion_score or 'N/A' }}/100</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Classification:</span>
                        <span class="metric-value">{{ data.classification or 'N/A' }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Expected Move:</span>
                        <span class="metric-value">${{ '{:,.0f}'.format(data.expected_move_low) if data.expected_move_low else 'N/A' }} - ${{ '{:,.0f}'.format(data.expected_move_high) if data.expected_move_high else 'N/A' }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Data Quality:</span>
                        <span class="metric-value">{{ data.data_quality or 'N/A' }}</span>
                    </div>
                </div>
            </div>
            
            <div class="grid-2">
                <div class="card">
                    <h3>🎯 STRUCTURE vs EXPANSION</h3>
                    <div class="metric-row">
                        <span class="metric-label">Stable Bull Trigger:</span>
                        <span class="metric-value">${{ '{:,.0f}'.format(data.stable_bull) if data.stable_bull else 'N/A' }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Stable Bear Trigger:</span>
                        <span class="metric-value">${{ '{:,.0f}'.format(data.stable_bear) if data.stable_bear else 'N/A' }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Bull Power Ratio:</span>
                        <span class="metric-value">{{ data.bull_power_ratio or 'N/A' }}</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Bear Power Ratio:</span>
                        <span class="metric-value">{{ data.bear_power_ratio or 'N/A' }}</span>
                    </div>
                </div>
                
                <div class="card">
                    <h3>🔔 MODEL 3: DECISION ENGINE</h3>
                    <div class="metric-row">
                        <span class="metric-label">Decision Score:</span>
                        <span class="metric-value">{{ data.decision_score or 'N/A' }}/115</span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Trade Status:</span>
                        <span class="metric-value {% if 'ACTIVE' in data.trade_status %}bullish{% endif %}">
                            {{ data.trade_status or 'N/A' }}
                        </span>
                    </div>
                    <div class="metric-row">
                        <span class="metric-label">Confirmation:</span>
                        <span class="metric-value">{{ data.confirmation or 'N/A' }}</span>
                    </div>
                </div>
            </div>
            
            <div class="setup-box">
                <div>🎯 SETUP TYPE</div>
                <div class="setup-type {% if 'LONG' in data.setup_type %}bullish{% elif 'SHORT' in data.setup_type %}bearish{% endif %}">
                    {{ data.setup_type or 'N/A' }}
                </div>
                <div class="action">
                    {{ data.action or 'N/A' }}
                </div>
            </div>
            
            <div class="timestamp">
                Data updated every minute | Page auto-refreshes every 10 seconds | Live Trading Dashboard v8.3
            </div>
            {% else %}
            <div class="price-section">
                <div class="btc-price">Loading data...</div>
                <div>First data fetch in progress. Please wait...</div>
            </div>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

def fetch_gateio_native():
    """Fetch Gate.io futures data"""
    try:
        stats_url = "https://api.gateio.ws/api/v4/futures/usdt/contract_stats"
        from_ts = int(time.time()) - (5 * 24 * 3600)
        stats_params = {"contract": "BTC_USDT", "from": from_ts, "interval": "1h", "limit": "120"}
        stats_raw = requests.get(stats_url, params=stats_params, timeout=10).json()
        
        if not isinstance(stats_raw, list):
            raise ValueError("Invalid response format from Gate.io Stats")
        stats_raw.sort(key=lambda x: float(x.get('time', 0)))
        
        kline_url = "https://api.gateio.ws/api/v4/futures/usdt/candlesticks"
        kline_params = {"contract": "BTC_USDT", "from": from_ts, "interval": "1h", "limit": "120"}
        kline_raw = requests.get(kline_url, params=kline_params, timeout=10).json()
        
        if not isinstance(kline_raw, list):
            raise ValueError("Invalid response format from Gate.io Candlesticks")
        kline_raw.sort(key=lambda x: float(x.get('t', 0)))
        
        kline_map = {}
        for k in kline_raw:
            ts = int(float(k.get('t', 0)))
            kline_map[ts] = {
                'high': float(k.get('h', 0.0)),
                'low': float(k.get('l', 0.0)),
                'close': float(k.get('c', 0.0))
            }
            
        data = []
        running_cvd = 0.0
        for x in stats_raw:
            ts = int(float(x.get('time', 0)))
            k_data = kline_map.get(ts, None)
            if not k_data:
                continue 
                
            buy_vol = float(x.get('long_taker_size', 0.0))
            sell_vol = float(x.get('short_taker_size', 0.0))
            delta = buy_vol - sell_vol
            running_cvd += delta
            
            oi_usd = float(x.get('open_interest_usd', 0.0))
            
            data.append({
                'time': float(ts),
                'price': k_data['close'],
                'high': k_data['high'],
                'low': k_data['low'],
                'OI_USD': oi_usd / 1e9,
                'lsr_taker': float(x.get('lsr_taker', 1.0)),
                'lsr_account': float(x.get('lsr_account', 1.0)),
                'top_lsr': float(x.get('top_lsr_size', 1.0)),
                'long_liq': float(x.get('long_liq_usd', 0.0)),
                'short_liq': float(x.get('short_liq_usd', 0.0)),
                'buy_vol': buy_vol,
                'sell_vol': sell_vol,
                'delta': delta,
                'cvd': running_cvd
            })
            
        fr_raw = requests.get("https://api.gateio.ws/api/v4/futures/usdt/funding_rate",
                              params={"contract": "BTC_USDT", "limit": "120"}, timeout=10).json()
        fr_data = []
        if isinstance(fr_raw, list):
            fr_raw.sort(key=lambda x: float(x.get('t', 0)))
            fr_data = [{'time': float(x.get('t', 0)), 'rate': float(x.get('r', 0.0)) * 100} for x in fr_raw]
        
        return data, fr_data
    except Exception as e:
        logger.error(f"Gate.io Fetch Error: {e}")
        return [], []

def fetch_binance_futures_native():
    """Fetch Binance futures data"""
    try:
        B = "https://fapi.binance.com"
        H = {"User-Agent": "Mozilla/5.0"}
        P = {"symbol": "BTCUSDT", "period": "1h", "limit": "120"}
        
        def get_api(path, params=P):
            resp = requests.get(f"{B}{path}", params=params, headers=H, timeout=10).json()
            if isinstance(resp, dict) and 'msg' in resp:
                raise ValueError(resp['msg'])
            if not resp:
                raise ValueError("Empty response")
            return resp

        oi_raw = get_api("/futures/data/openInterestHist")
        oi_raw.sort(key=lambda x: float(x.get('timestamp', 0)))
        
        top_raw = get_api("/futures/data/topLongShortAccountRatio")
        top_raw.sort(key=lambda x: float(x.get('timestamp', 0)))
        
        pos_raw = get_api("/futures/data/topLongShortPositionRatio")
        pos_raw.sort(key=lambda x: float(x.get('timestamp', 0)))
        
        glob_raw = get_api("/futures/data/globalLongShortAccountRatio")
        glob_raw.sort(key=lambda x: float(x.get('timestamp', 0)))
        
        fr_raw = get_api("/fapi/v1/fundingRate", {"symbol": "BTCUSDT", "limit": "100"})
        fr_raw.sort(key=lambda x: float(x.get('fundingTime', 0)))
        
        return oi_raw, top_raw, pos_raw, glob_raw, fr_raw
    except Exception as e:
        logger.error(f"Binance Futures Error: {e}")
        return [], [], [], [], []

def fetch_binance_spot_native():
    """Fetch Binance spot data"""
    try:
        resp = requests.get("https://api.binance.com/api/v3/klines",
                            params={"symbol": "BTCUSDT", "interval": "1h", "limit": "48"},
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=10).json()
        if isinstance(resp, dict) and 'msg' in resp:
            raise ValueError(resp['msg'])
        
        spot_data = []
        running_spot_cvd = 0.0
        for k in resp:
            vol = float(k[5])
            taker_buy = float(k[9])
            taker_sell = vol - taker_buy
            delta = taker_buy - taker_sell
            running_spot_cvd += delta
            
            spot_data.append({
                'time': float(k[0]) / 1000,
                'close': float(k[4]),
                'spot_vol': vol,
                'taker_buy': taker_buy,
                'taker_sell': taker_sell,
                'spot_delta': delta,
                'spot_cvd': running_spot_cvd
            })
        return spot_data
    except Exception as e:
        logger.error(f"Binance Spot Error: {e}")
        return []

def save_to_csv(log_data, log_file="btc_dashboard_log.csv"):
    """Save data to CSV file"""
    try:
        current_headers = list(log_data.keys())
        file_exists = os.path.exists(log_file) and os.path.getsize(log_file) > 0
        
        # Schema protection
        if file_exists:
            with open(log_file, "r", newline="") as f:
                reader = csv.reader(f)
                existing_headers = next(reader, [])
            
            if existing_headers != current_headers:
                backup_name = log_file.replace(".csv", f"_backup_{int(time.time())}.csv")
                os.rename(log_file, backup_name)
                logger.info(f"CSV schema changed. Backed up to: {backup_name}")
                file_exists = False
        
        with open(log_file, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=current_headers)
            if not file_exists:
                writer.writeheader()
            writer.writerow(log_data)
        
        logger.info(f"Data saved to CSV: {log_file}")
    except Exception as e:
        logger.error(f"Error saving to CSV: {e}")

def process_dashboard_data():
    """Process all data and generate dashboard output"""
    global latest_dashboard_data
    
    logger.info("="*50)
    logger.info("Fetching latest market data...")
    
    gate_df, gate_fr = fetch_gateio_native()
    binance_available = spot_available = False
    
    if len(gate_df) == 0:
        logger.error("Failed to fetch Gate.io data")
        return None
    
    try:
        bn_oi, bn_top, bn_pos, bn_glob, bn_fr = fetch_binance_futures_native()
        binance_available = True if bn_oi else False
    except Exception as e:
        logger.error(f"Binance Futures Error: {e}")
    
    try:
        spot_df = fetch_binance_spot_native()
        spot_available = True if spot_df else False
    except Exception as e:
        logger.error(f"Binance Spot Error: {e}")
    
    data_quality = "GOOD"
    if not binance_available and not spot_available:
        data_quality = "PARTIAL (Gate Only)"
    elif not binance_available or not spot_available:
        data_quality = "PARTIAL"
    
    # Process all indicators
    latest = gate_df[-1]
    len_12 = min(12, len(gate_df))
    price_change = latest['price'] - gate_df[-len_12]['price'] if len_12 > 0 else 0
    gate_fr_latest = gate_fr[-1]['rate'] if gate_fr else 0
    
    if binance_available and 'bn_top' in locals() and bn_top and bn_fr:
        bn_latest_top = float(bn_top[-1]['longShortRatio'])
        bn_fr_latest = float(bn_fr[-1]['fundingRate']) * 100
        smart_gap = abs(bn_latest_top - latest['top_lsr'])
        agg_smart_lsr = 1.0 if smart_gap > 1.0 else (bn_latest_top * 0.65) + (latest['top_lsr'] * 0.35)
        agg_fr = (bn_fr_latest * 0.65) + (gate_fr_latest * 0.35)
    else:
        bn_latest_top = 1.0
        agg_smart_lsr = latest['top_lsr']
        smart_gap = 0
        agg_fr = gate_fr_latest
    
    # Model 1 calculations
    len_24 = min(24, len(gate_df))
    len_72 = min(72, len(gate_df))
    ma24 = sum([x['price'] for x in gate_df[-len_24:]]) / len_24 if len_24 > 0 else latest['price']
    ma72 = sum([x['price'] for x in gate_df[-len_72:]]) / len_72 if len_72 > 0 else latest['price']
    
    if ma24 > ma72:
        if latest['price'] > ma24:
            c1_label, c1_score = "STRONG BULL", 25
        else:
            c1_label, c1_score = "BULL", 15
    elif ma24 < ma72:
        if latest['price'] < ma24:
            c1_label, c1_score = "STRONG BEAR", -25
        else:
            c1_label, c1_score = "BEAR", -15
    else:
        c1_label, c1_score = "NEUTRAL", 0
    
    deltas_6h = [sum([x['delta'] for x in gate_df[max(0, i-5):i+1]]) for i in range(len(gate_df))]
    tail_len = min(48, len(deltas_6h))
    tail_deltas = deltas_6h[-tail_len:]
    cvd_6h_mean = sum(tail_deltas) / tail_len if tail_len > 0 else 0
    cvd_6h_std = math.sqrt(sum((x - cvd_6h_mean) ** 2 for x in tail_deltas) / tail_len) if tail_len > 0 else 1
    cvd_z = (deltas_6h[-1] - cvd_6h_mean) / cvd_6h_std if cvd_6h_std > 0 else 0
    
    if cvd_z > 1.0:
        c2_label, c2_score = "AGGRESSIVE BUYING", 25
    elif cvd_z > 0.3:
        c2_label, c2_score = "BUYING", 15
    elif cvd_z < -1.0:
        c2_label, c2_score = "AGGRESSIVE SELLING", -25
    elif cvd_z < -0.3:
        c2_label, c2_score = "SELLING", -15
    else:
        c2_label, c2_score = "NEUTRAL", 0
    
    oi_changes = [gate_df[i]['OI_USD'] - gate_df[i-1]['OI_USD'] for i in range(1, len(gate_df))] or [0]
    oi_tail_len = min(48, len(oi_changes))
    tail_oi = oi_changes[-oi_tail_len:]
    oi_mean = sum(tail_oi) / oi_tail_len if oi_tail_len > 0 else 0
    oi_std = math.sqrt(sum((x - oi_mean) ** 2 for x in tail_oi) / oi_tail_len) if oi_tail_len > 0 else 1
    oi_z = (oi_changes[-1] - oi_mean) / oi_std if oi_std > 0 else 0
    
    if oi_z > 0.8:
        if price_change > 0:
            c3_label, c3_score = "LONG BUILDUP", 20
        else:
            c3_label, c3_score = "SHORT BUILDUP", -20
    elif oi_z < -0.8:
        if price_change < 0:
            c3_label, c3_score = "LONG FLUSH", -10
        else:
            c3_label, c3_score = "SHORT FLUSH", 10
    else:
        c3_label, c3_score = "NEUTRAL", 0
    
    if spot_available and spot_df:
        spot_buying = spot_df[-1]['taker_buy'] > spot_df[-1]['taker_sell']
        spot_cvd_rising = spot_df[-1]['spot_cvd'] > spot_df[-min(12, len(spot_df))]['spot_cvd']
        if spot_buying and spot_cvd_rising:
            c4_label, c4_score = "BUYING", 15
        elif not spot_buying and not spot_cvd_rising:
            c4_label, c4_score = "SELLING", -15
        else:
            c4_label, c4_score = "NEUTRAL", 0
    else:
        c4_label, c4_score = "NEUTRAL", 0
    
    if agg_smart_lsr > 1.30:
        c5_label, c5_score = "STRONG SMART BUYING", 15
    elif agg_smart_lsr > 1.10:
        c5_label, c5_score = "SMART BUYING", 8
    elif agg_smart_lsr < 0.70:
        c5_label, c5_score = "STRONG SMART SELLING", -15
    elif agg_smart_lsr < 0.90:
        c5_label, c5_score = "SMART SELLING", -8
    else:
        c5_label, c5_score = "NEUTRAL", 0
    
    total_score = c1_score + c2_score + c3_score + c4_score + c5_score
    MAX_SCORE = 100
    confidence = round(abs(total_score) / MAX_SCORE * 100)
    confidence = min(confidence, 100)
    
    if total_score >= 70:
        direction = "STRONG LONG"
    elif total_score >= 40:
        direction = "LONG"
    elif total_score > -40:
        direction = "NEUTRAL"
    elif total_score > -70:
        direction = "SHORT"
    else:
        direction = "STRONG SHORT"
    
    if confidence >= 90:
        grade = "A+"
    elif confidence >= 80:
        grade = "A"
    elif confidence >= 70:
        grade = "B"
    elif confidence >= 60:
        grade = "C"
    else:
        grade = "D"
    
    # Model 2 calculations
    intra_hour_ranges = []
    lookback_24h = gate_df[-min(24, len(gate_df)):]
    
    for x in lookback_24h:
        h = x.get('high', x['price'])
        l = x.get('low', x['price'])
        intra_hour_ranges.append(h - l)
    
    atr_usd = sum(intra_hour_ranges) / len(intra_hour_ranges) if intra_hour_ranges else 500.0
    
    current_hour = gate_df[-1]
    current_range = current_hour.get('high', current_hour['price']) - current_hour.get('low', current_hour['price'])
    vm = current_range / atr_usd if atr_usd > 0 else 1.0
    
    trend_gap_pct = (abs(ma24 - ma72) / ma72 * 100) if ma72 > 0 else 0
    if trend_gap_pct > 2.0:
        m2_c1_score = 25
    elif trend_gap_pct >= 1.0:
        m2_c1_score = 20
    elif trend_gap_pct >= 0.5:
        m2_c1_score = 10
    else:
        m2_c1_score = 0
    
    abs_oi_z = abs(oi_z)
    if abs_oi_z > 1.5:
        m2_c2_score = 25
    elif abs_oi_z >= 1.0:
        m2_c2_score = 18
    elif abs_oi_z >= 0.5:
        m2_c2_score = 10
    else:
        m2_c2_score = 0
    
    abs_cvd_z = abs(cvd_z)
    if abs_cvd_z > 1.5:
        m2_c3_score = 20
    elif abs_cvd_z >= 0.8:
        m2_c3_score = 15
    elif abs_cvd_z >= 0.3:
        m2_c3_score = 8
    else:
        m2_c3_score = 0
    
    long_liq, short_liq = latest['long_liq'], latest['short_liq']
    liq_ratio = max(long_liq, short_liq) / max(min(long_liq, short_liq), 1)
    liq_ratio = min(liq_ratio, 20)
    if liq_ratio > 8:
        m2_c4_score = 15
    elif liq_ratio >= 4:
        m2_c4_score = 10
    elif liq_ratio >= 2:
        m2_c4_score = 5
    else:
        m2_c4_score = 0
    
    if vm >= 3.0:
        m2_c5_score = 15
    elif vm >= 2.0:
        m2_c5_score = 12
    elif vm >= 1.5:
        m2_c5_score = 10
    elif vm >= 1.0:
        m2_c5_score = 7
    elif vm >= 0.5:
        m2_c5_score = 4
    else:
        m2_c5_score = 0
    
    expansion_score = m2_c1_score + m2_c2_score + m2_c3_score + m2_c4_score + m2_c5_score
    
    if expansion_score >= 81:
        classification = "EXPLOSIVE MOVE"
        lower_mult, upper_mult = 2.0, 3.0
    elif expansion_score >= 61:
        classification = "STRONG EXPANSION"
        lower_mult, upper_mult = 1.5, 2.0
    elif expansion_score >= 41:
        classification = "TRADEABLE MOVE"
        lower_mult, upper_mult = 1.0, 1.5
    elif expansion_score >= 21:
        classification = "NORMAL MARKET"
        lower_mult, upper_mult = 0.5, 1.0
    else:
        classification = "DEAD MARKET"
        lower_mult, upper_mult = 0.0, 0.5
    
    expected_move_lower = atr_usd * lower_mult
    expected_move_upper = atr_usd * upper_mult
    
    # Model 3 calculations
    stable_bull_trigger = max([x.get('high', x['price']) for x in lookback_24h])
    stable_bear_trigger = min([x.get('low', x['price']) for x in lookback_24h])
    
    volatile_bull_trigger = latest['price'] + expected_move_lower
    volatile_bear_trigger = latest['price'] - expected_move_lower
    
    bull_gap = volatile_bull_trigger - stable_bull_trigger
    bear_gap = stable_bear_trigger - volatile_bear_trigger
    
    distance_to_res = max(stable_bull_trigger - latest['price'], 1)
    bull_power_ratio = expected_move_lower / distance_to_res
    distance_to_sup = max(latest['price'] - stable_bear_trigger, 1)
    bear_power_ratio = expected_move_lower / distance_to_sup
    
    if "LONG" in direction:
        active_ratio = bull_power_ratio
    elif "SHORT" in direction:
        active_ratio = bear_power_ratio
    else:
        active_ratio = max(bull_power_ratio, bear_power_ratio)
    
    if active_ratio >= 1.50:
        m3_c5 = 15
    elif active_ratio >= 1.00:
        m3_c5 = 10
    elif active_ratio >= 0.70:
        m3_c5 = 5
    else:
        m3_c5 = 0
    
    if direction in ["STRONG LONG", "STRONG SHORT"]:
        m3_c1 = 40
    elif direction in ["LONG", "SHORT"]:
        m3_c1 = 25
    else:
        m3_c1 = 0
    
    if classification == "EXPLOSIVE MOVE":
        m3_c2 = 30
    elif classification == "STRONG EXPANSION":
        m3_c2 = 25
    elif classification == "TRADEABLE MOVE":
        m3_c2 = 15
    elif classification == "NORMAL MARKET":
        m3_c2 = 5
    else:
        m3_c2 = 0
    
    if confidence >= 90:
        m3_c3 = 20
    elif confidence >= 80:
        m3_c3 = 15
    elif confidence >= 70:
        m3_c3 = 10
    elif confidence >= 60:
        m3_c3 = 5
    else:
        m3_c3 = 0
    
    if data_quality == "GOOD":
        m3_c4 = 10
    elif data_quality == "PARTIAL":
        m3_c4 = 5
    else:
        m3_c4 = 0
    
    decision_score = m3_c1 + m3_c2 + m3_c3 + m3_c4 + m3_c5
    
    exp_levels = {"DEAD MARKET": 1, "NORMAL MARKET": 2, "TRADEABLE MOVE": 3, "STRONG EXPANSION": 4, "EXPLOSIVE MOVE": 5}
    current_exp_level = exp_levels.get(classification, 1)
    
    if direction == "STRONG LONG" and current_exp_level >= 4 and confidence >= 80:
        setup_type = "AGGRESSIVE LONG"
    elif direction in ["LONG", "STRONG LONG"] and current_exp_level >= 4:
        setup_type = "LONG"
    elif direction == "STRONG SHORT" and current_exp_level >= 4 and confidence >= 80:
        setup_type = "AGGRESSIVE SHORT"
    elif direction in ["SHORT", "STRONG SHORT"] and current_exp_level >= 4:
        setup_type = "SHORT"
    elif direction in ["LONG", "SHORT"] and current_exp_level == 3:
        setup_type = "WATCHLIST"
    elif direction == "NEUTRAL":
        if classification in ["STRONG EXPANSION", "EXPLOSIVE MOVE"]:
            setup_type = "BREAKOUT WATCH"
        elif classification == "TRADEABLE MOVE":
            setup_type = "WATCHLIST"
        else:
            setup_type = "NO TRADE"
    else:
        setup_type = "NO TRADE"
    
    if "AGGRESSIVE" in setup_type:
        trade_status, confirmation_status, action = "ACTIVE", "PASSED", f"ENTER {setup_type.split()[-1]}"
    elif setup_type in ["LONG", "SHORT"]:
        trade_status, confirmation_status, action = "ACTIVE", "PASSED", f"ENTER {setup_type}"
    elif setup_type == "BREAKOUT WATCH":
        trade_status, confirmation_status = "STANDBY", "PENDING"
        action = f"WAIT FOR BREAKOUT | Potential Move: ${expected_move_lower:,.0f}-${expected_move_upper:,.0f}"
    elif setup_type == "WATCHLIST":
        trade_status, confirmation_status = "STANDBY", "PENDING"
        action = "MONITOR FOR DIRECTIONAL EDGE"
    else:
        trade_status, confirmation_status, action = "INACTIVE", "FAILED", "SIT ON HANDS"
    
    # Prepare output data
    output_data = {
        'price': latest['price'],
        'direction': direction,
        'confidence': confidence,
        'grade': grade,
        'total_score': total_score,
        'trend_label': c1_label,
        'cvd_label': c2_label,
        'oi_label': c3_label,
        'spot_label': c4_label,
        'smart_label': c5_label,
        'data_quality': data_quality,
        'expansion_score': expansion_score,
        'classification': classification,
        'expected_move_low': round(expected_move_lower, 2),
        'expected_move_high': round(expected_move_upper, 2),
        'decision_score': decision_score,
        'setup_type': setup_type,
        'trade_status': trade_status,
        'confirmation': confirmation_status,
        'action': action,
        'stable_bull': round(stable_bull_trigger, 2),
        'stable_bear': round(stable_bear_trigger, 2),
        'bull_power_ratio': round(bull_power_ratio, 3),
        'bear_power_ratio': round(bear_power_ratio, 3),
        'last_update': datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S UTC')
    }
    
    # Save to CSV
    log_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "price": latest['price'],
        "direction": direction,
        "confidence": confidence,
        "grade": grade,
        "total_score": total_score,
        "trend_label": c1_label,
        "cvd_label": c2_label,
        "oi_label": c3_label,
        "spot_label": c4_label,
        "smart_label": c5_label,
        "data_quality": data_quality,
        "expansion_score": expansion_score,
        "classification": classification,
        "expected_move_low": round(expected_move_lower, 2),
        "expected_move_high": round(expected_move_upper, 2),
        "decision_score": decision_score,
        "setup_type": setup_type,
        "trade_status": trade_status,
        "confirmation": confirmation_status,
        "action": action,
        "version": VERSION,
        "stable_bull": round(stable_bull_trigger, 2),
        "stable_bear": round(stable_bear_trigger, 2),
        "bull_power_ratio": round(bull_power_ratio, 3),
        "bear_power_ratio": round(bear_power_ratio, 3)
    }
    save_to_csv(log_entry)
    
    # Update global data with lock
    with data_lock:
        latest_dashboard_data['raw_data'] = output_data
        latest_dashboard_data['last_update'] = output_data['last_update']
        latest_dashboard_data['update_count'] = latest_dashboard_data.get('update_count', 0) + 1
    
    logger.info(f"✅ Data updated successfully | BTC: ${latest['price']:,.0f} | Direction: {direction} | Setup: {setup_type}")
    logger.info(f"📊 Update #{latest_dashboard_data['update_count']} completed")
    
    return output_data

@app.route('/')
def dashboard():
    """Main dashboard route"""
    with data_lock:
        data = latest_dashboard_data.get('raw_data')
        update_count = latest_dashboard_data.get('update_count', 0)
        last_update = latest_dashboard_data.get('last_update', 'Never')
    
    if data:
        data['update_count'] = update_count
        data['last_update'] = last_update
    
    return render_template_string(HTML_TEMPLATE, data=data)

@app.route('/api/latest')
def api_latest():
    """API endpoint for latest data"""
    with data_lock:
        data = latest_dashboard_data.get('raw_data', {})
    return jsonify(data)

@app.route('/health')
def health():
    """Health check endpoint for Render"""
    with data_lock:
        return jsonify({
            'status': 'healthy',
            'last_update': latest_dashboard_data.get('last_update'),
            'update_count': latest_dashboard_data.get('update_count', 0),
            'version': VERSION
        })

# Initialize scheduler
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Schedule the data update every minute (60 seconds)
@scheduler.task('interval', id='update_data', seconds=60, misfire_grace_time=30)
def scheduled_update():
    """Run data update every minute"""
    with app.app_context():
        process_dashboard_data()

# Run initial update on startup
@app.before_first_request
def initialize():
    """Run initial data fetch before first request"""
    import threading
    def delayed_init():
        time.sleep(2)
        with app.app_context():
            process_dashboard_data()
    threading.Thread(target=delayed_init).start()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
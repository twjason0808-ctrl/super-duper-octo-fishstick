from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import pandas as pd

app = Flask(__name__)
CORS(app)

HTML = """<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台股均線分析</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0f0f0f;color:#fff;font-family:sans-serif;padding:20px}
h1{text-align:center;color:#4fc3f7;margin-bottom:30px;font-size:22px}
.input-area{display:flex;gap:10px;margin-bottom:20px}
input{flex:1;padding:14px;background:#1e1e1e;border:1px solid #333;border-radius:10px;color:#fff;font-size:18px}
button{padding:14px 24px;background:#4fc3f7;border:none;border-radius:10px;color:#000;font-size:16px;font-weight:bold}
.card{background:#1e1e1e;border-radius:10px;padding:15px;margin-bottom:12px}
.period{font-size:16px;font-weight:bold;color:#4fc3f7;margin-bottom:8px}
.row{display:flex;justify-content:space-between;margin:4px 0;font-size:14px}
.up{color:#66bb6a}.down{color:#ef5350}.neutral{color:#ffa726}
.summary{background:#1a2744;border-radius:10px;padding:15px;margin-top:10px;font-size:15px;line-height:1.8}
.loading{text-align:center;color:#888;padding:30px;font-size:16px}
</style>
</head>
<body>
<h1>📈 台股均線分析</h1>
<div class="input-area">
<input type="text" id="code" placeholder="輸入代號 例如 1210"/>
<button onclick="analyze()">分析</button>
</div>
<div id="result"></div>
<script>
async function analyze(){
const code=document.getElementById('code').value.trim();
if(!code)return;
document.getElementById('result').innerHTML='<div class="loading">⏳ 分析中，約需30秒...</div>';
try{
const res=await fetch('/api/analyze?code='+code);
const data=await res.json();
if(data.error){document.getElementById('result').innerHTML='<div class="card">❌ '+data.error+'</div>';return;}
let html='';
data.periods.forEach(p=>{
const dc=p.direction==='向上'?'up':p.direction==='向下'?'down':'neutral';
const sc=p.signal==='買點條件成立'?'up':p.signal==='觀察中'?'neutral':'down';
html+='<div class="card"><div class="period">'+p.period+'</div>';
html+='<div class="row"><span>糾結狀態</span><span>'+p.cluster+'（'+p.spread+'%）</span></div>';
html+='<div class="row"><span>方向</span><span class="'+dc+'">'+p.direction+'</span></div>';
html+='<div class="row"><span>訊號</span><span class="'+sc+'">'+p.signal+'</span></div></div>';
});
html+='<div class="summary">📊 '+data.summary+'</div>';
document.getElementById('result').innerHTML=html;
}catch(e){document.getElementById('result').innerHTML='<div class="card">❌ 連線失敗</div>';}
}
document.getElementById('code').addEventListener('keypress',e=>{if(e.key==='Enter')analyze();});
</script>
</body>
</html>"""

@app.route("/")
def index():
    return HTML

def get_close(df):
    if isinstance(df["Close"], pd.DataFrame):
        return df["Close"].iloc[:, 0]
    return df["Close"]

def analyze(ticker_code):
    ticker = None
    for suffix in [".TW", ".TWO"]:
        try:
            df = yf.download(ticker_code+suffix, period="5d", interval="1d", progress=False)
            if not df.empty:
                ticker = ticker_code+suffix
                break
        except:
            pass
    if not ticker:
        return None
    periods = {
        "月線": yf.download(ticker, period="5y", interval="1mo", progress=False),
        "週線": yf.download(ticker, period="2y", interval="1wk", progress=False),
        "日線": yf.download(ticker, period="1y", interval="1d", progress=False),
        "60分": yf.download(ticker, period="60d", interval="60m", progress=False),
        "30分": yf.download(ticker, period="60d", interval="30m", progress=False),
    }
    mas=[8,22,55,144,233]
    results=[]
    met=0
    for name,df in periods.items():
        if df.empty or len(df)<30: continue
        df=df.copy()
        close=get_close(df)
        for m in mas:
            if len(df)>=m: df[f"ma{m}"]=close.rolling(m).mean()
        latest=df.iloc[-1]
        ma_vals={}
        for m in mas:
            col=f"ma{m}"
            if col in latest:
                val=latest[col]
                if isinstance(val,pd.Series): val=val.iloc[0]
                if pd.notna(val): ma_vals[m]=float(val)
        if len(ma_vals)<3: continue
        vals=list(ma_vals.values())
        spread=(max(vals)-min(vals))/min(vals)*100
        if spread<3: cluster="高度糾結"
        elif spread<8: cluster="接近糾結"
        else: cluster="尚未糾結"
        direction="無法判斷"
        if "ma8" in df.columns and len(df)>=3:
            a=df["ma8"].iloc[-1]; b=df["ma8"].iloc[-3]
            if isinstance(a,pd.Series): a=a.iloc[0]
            if isinstance(b,pd.Series): b=b.iloc[0]
            if pd.notna(a) and pd.notna(b):
                if a>b: direction="向上"
                elif a<b: direction="向下"
                else: direction="橫盤"
        if spread<5 and direction=="向上": signal="買點條件成立"; met+=1
        elif spread<8 and direction=="向上": signal="觀察中"
        else: signal="條件未到"
        results.append({"period":name,"cluster":cluster,"spread":round(spread,1),"direction":direction,"signal":signal})
    if met==5: summary="所有週期條件成立，現在是買點！"
    elif met>=3: summary=f"{met}/5 週期條件成立，接近買點"
    else: summary=f"{met}/5 週期條件成立，尚未到買點"
    return {"ticker":ticker,"periods":results,"summary":summary}

@app.route("/api/analyze")
def analyze_route():
    code=request.args.get("code","")
    if not code: return jsonify({"error":"請輸入股票代號"}),400
    result=analyze(code)
    if not result: return jsonify({"error":"找不到股票資料"}),404
    return jsonify(result)

if __name__=="__main__":
    port=int(__import__('os').environ.get("PORT",5000))
    app.run(host
    


<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EndumbeniFX Scanner</title>
<style>
:root{color-scheme:dark;--bg:#0b1020;--panel:#141c30;--line:#293650;--text:#edf3ff;--muted:#9eabc2;--green:#36d69a;--red:#ff687b;--gold:#e7bc62}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:15px Arial,sans-serif}
header{padding:20px 16px;background:#10182b;border-bottom:1px solid var(--line)}
h1{font-size:23px;margin:0 0 7px}
small,.muted{color:var(--muted)}
main{max-width:850px;margin:auto;padding:15px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:15px;margin-bottom:14px}
.tabs,.timeframes{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:13px}
button,select,input{background:#0c1426;color:var(--text);border:1px solid var(--line);padding:11px;border-radius:9px;font-size:14px}
button{cursor:pointer}
button.active{border-color:var(--gold);color:var(--gold)}
button:disabled{opacity:.5}
label{display:block;font-size:12px;color:var(--muted);margin:12px 0 6px}
select,input{width:100%}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.price{font-size:29px;font-weight:bold;margin:9px 0}
.status{font-size:13px;margin:7px 0}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--muted);margin-right:6px}
.good{color:var(--green)}.bad{color:var(--red)}.gold{color:var(--gold)}
.signal{font-size:22px;font-weight:bold;margin:8px 0}
.metrics{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.metric{background:#0c1426;padding:12px;border-radius:9px;overflow-wrap:anywhere}
.metric b{display:block;margin-top:6px}
#chart{width:100%;height:155px;display:block}
.note{font-size:12px;line-height:1.6;color:var(--muted)}
@media(max-width:480px){.row{grid-template-columns:1fr}.price{font-size:25px}}
</style>
</head>
<body>
<header>
  <h1>EndumbeniFX</h1>
  <small>Market scanner · Live data only · No simulated prices</small>
</header>
<main>
  <div class="panel">
    <div class="tabs" id="categoryTabs">
      <button data-category="SYNTHETICS" class="active">Synthetics</button>
      <button data-category="FOREX">Forex</button>
      <button data-category="COMMODITIES">Commodities</button>
      <button data-category="INDICES">Indices</button>
    </div>
    <label>Market</label>
    <select id="symbol"></select>
    <label>Timeframe</label>
    <div class="timeframes" id="timeframes">
      <button data-tf="4h">H4</button>
      <button data-tf="1h" class="active">H1</button>
      <button data-tf="15min">M15</button>
      <button data-tf="5min">M5</button>
    </div>
    <div class="status" id="connection"><span class="dot"></span>Waiting for connection</div>
    <div class="note" id="providerInfo">Synthetics use Deriv. Traditional markets use Twelve Data.</div>
  </div>

  <div class="panel">
    <small>SELECTED MARKET · LIVE PRICE</small>
    <div class="price" id="price">—</div>
    <div class="status muted" id="priceTime">No live price received yet</div>
    <canvas id="chart"></canvas>
  </div>

  <div class="panel">
    <small>MARKET ANALYSIS</small>
    <div class="signal" id="signal">WAITING FOR DATA</div>
    <div class="muted" id="reason">Analysis will start after real candles arrive.</div>
    <div class="metrics" style="margin-top:14px">
      <div class="metric">Entry<b id="entry">—</b></div>
      <div class="metric">Stop loss<b id="sl">—</b></div>
      <div class="metric">Take profit (1:2)<b id="tp">—</b></div>
      <div class="metric">Candles received<b id="candleCount">0</b></div>
    </div>
  </div>

  <div class="panel">
    <b>Traditional market data setup</b>
    <label>Twelve Data API key</label>
    <input id="apiKey" type="password" autocomplete="off"
      placeholder="Paste your API key for this session">
    <p class="note">The key stays in this page's memory and is not saved by this code. Browser-based API keys can still be seen in network requests. Do not use a private production key here.</p>
    <button id="connectTraditional">Connect / refresh traditional market</button>
  </div>

  <div class="panel">
    <b>Important</b>
    <p class="note">Signals are simple technical rules, not guaranteed predictions. WAIT means the rules did not find a setup. Confirm data freshness, broker pricing, spreads and risk before trading. Traditional indices may require a different symbol code or subscription. Nothing here places trades.</p>
  </div>
</main>

<script>
(() => {
  "use strict";

  const $ = id => document.getElementById(id);
  const traditional = {
    FOREX: [
      {name:"EUR/USD", symbol:"EUR/USD"},
      {name:"GBP/USD", symbol:"GBP/USD"},
      {name:"GBP/JPY", symbol:"GBP/JPY"},
      {name:"EUR/JPY", symbol:"EUR/JPY"},
      {name:"USD/CAD", symbol:"USD/CAD"}
    ],
    COMMODITIES: [
      {name:"Gold (XAU/USD)", symbol:"XAU/USD"}
    ],
    INDICES: [
      {name:"NASDAQ 100 (NDX)", symbol:"NDX"},
      {name:"Dow Jones (DJI)", symbol:"DJI"},
      {name:"Germany 40 (DAX)", symbol:"DAX"}
    ]
  };

  const state = {
    category:"SYNTHETICS", timeframe:"1h",
    symbol:"", derivSymbols:[], candles:[],
    price:null, socket:null, requestId:10,
    tickSubId:null, refreshTimer:null, lastDataAt:0,
    traditionalBusy:false
  };

  function setStatus(message, kind="") {
    $("connection").innerHTML =
      '<span class="dot"></span>' + escapeHtml(message);
    $("connection").className = "status " + kind;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, ch => ({
      "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"
    }[ch]));
  }

  function currentOption() {
    return $("symbol").selectedOptions[0];
  }

  function selectedSymbol() {
    return currentOption()?.value || "";
  }

  function populateSymbols() {
    const select = $("symbol");
    select.innerHTML = "";
    let items = [];

    if (state.category === "SYNTHETICS") {
      items = state.derivSymbols.map(s => ({
        name:s.display_name || s.symbol,
        symbol:s.symbol
      }));
      if (!items.length) {
        items = [{name:"Loading Deriv symbols…",symbol:""}];
      }
    } else {
      items = traditional[state.category] || [];
    }

    for (const item of items) {
      const option = document.createElement("option");
      option.value = item.symbol;
      option.textContent = item.name;
      select.appendChild(option);
    }

    state.symbol = select.value;
    resetAnalysis();

    if (state.symbol) connectSelectedMarket();
  }

  function resetAnalysis() {
    state.candles = [];
    state.price = null;
    state.lastDataAt = 0;
    $("price").textContent = "—";
    $("priceTime").textContent = "Waiting for live data";
    $("signal").textContent = "WAITING FOR DATA";
    $("signal").className = "signal";
    $("reason").textContent = "Waiting for real market candles.";
    $("entry").textContent = "—";
    $("sl").textContent = "—";
    $("tp").textContent = "—";
    $("candleCount").textContent = "0";
    drawChart([]);
  }

  function stopConnection() {
    if (state.refreshTimer) clearInterval(state.refreshTimer);
    state.refreshTimer = null;
    if (state.socket) {
      try { state.socket.close(); } catch (_) {}
    }
    state.socket = null;
    state.tickSubId = null;
  }

  function connectSelectedMarket() {
    stopConnection();
    resetAnalysis();
    state.symbol = selectedSymbol();
    if (!state.symbol) return;

    if (state.category === "SYNTHETICS") {
      connectDeriv(state.symbol);
    } else {
      connectTwelveData();
    }
  }

  function derivGranularity(tf) {
    return {"5min":300,"15min":900,"1h":3600,"4h":14400}[tf] || 3600;
  }

  function loadDerivSymbols() {
    setStatus("Loading active symbols from Deriv…");
    const ws = new WebSocket("wss://ws.derivws.com/websockets/v3?app_id=1089");

    ws.onopen = () => ws.send(JSON.stringify({
      active_symbols:"brief", product_type:"basic"
    }));

    ws.onmessage = event => {
      let data;
      try { data = JSON.parse(event.data); } catch (_) { return; }
      if (data.error) {
        setStatus("Deriv symbol error: " + data.error.message, "bad");
        ws.close();
        return;
      }
      if (data.msg_type !== "active_symbols") return;

      state.derivSymbols = (data.active_symbols || [])
        .filter(s => {
          const text = [
            s.display_name,s.market_display_name,
            s.submarket_display_name,s.symbol
          ].join(" ").toLowerCase();
          return /synthetic|volatility|boom|crash|jump|range break/.test(text);
        })
        .sort((a,b) => (a.display_name || a.symbol)
          .localeCompare(b.display_name || b.symbol));

      ws.close();
      if (state.category === "SYNTHETICS") populateSymbols();
      setStatus(state.derivSymbols.length
        ? "Deriv symbol list received" : "No synthetic symbols returned", 
        state.derivSymbols.length ? "good" : "bad");
    };

    ws.onerror = () => setStatus("Could not load Deriv symbols. Check internet.", "bad");
    ws.onclose = () => {};
  }

  function connectDeriv(symbol) {
    setStatus("Connecting to Deriv…");
    $("providerInfo").textContent =
      "Provider: Deriv WebSocket · Symbol: " + symbol;

    const ws = new WebSocket("wss://ws.derivws.com/websockets/v3?app_id=1089");
    state.socket = ws;

    ws.onopen = () => {
      if (state.socket !== ws) return;
      setStatus("Deriv connected; requesting live price and candles", "good");
      ws.send(JSON.stringify({
        ticks_history:symbol,
        style:"candles",
        granularity:derivGranularity(state.timeframe),
        count:100,
        end:"latest",
        req_id:++state.requestId
      }));
      ws.send(JSON.stringify({
        ticks:symbol, subscribe:1, req_id:++state.requestId
      }));
    };

    ws.onmessage = event => {
      if (state.socket !== ws) return;
      let data;
      try { data = JSON.parse(event.data); } catch (_) { return; }

      if (data.error) {
        setStatus("Deriv error: " + data.error.message, "bad");
        return;
      }

      if (data.msg_type === "history" && data.history?.prices) {
        const times = data.history.times || [];
        state.candles = data.history.prices.map((close,i) => ({
          time:times[i] || 0,
          open:Number(data.history.prices[i-1] ?? close),
          high:Number(close), low:Number(close), close:Number(close)
        })).filter(c => Number.isFinite(c.close));
        analyse();
      }

      if (data.msg_type === "candles" && data.candles) {
        state.candles = data.candles.map(c => ({
          time:Number(c.epoch), open:Number(c.open),
          high:Number(c.high), low:Number(c.low), close:Number(c.close)
        }));
        analyse();
      }

      if (data.msg_type === "tick" && data.tick) {
        state.price = Number(data.tick.quote);
        state.lastDataAt = Date.now();
        $("price").textContent = formatPrice(state.price);
        $("priceTime").textContent =
          "Live tick received at " + new Date().toLocaleTimeString();
        setStatus("Deriv live tick connected", "good");
        analyse();
      }
    };

    ws.onerror = () => setStatus("Deriv WebSocket connection error", "bad");
    ws.onclose = () => {
      if (state.socket === ws) {
        setStatus("Deriv connection closed", "bad");
      }
    };
  }

  async function connectTwelveData() {
    const key = $("apiKey").value.trim();
    const symbol = selectedSymbol();
    if (!key) {
      setStatus("Enter your Twelve Data API key first", "bad");
      $("providerInfo").textContent =
        "Traditional markets require a Twelve Data API key.";
      return;
    }
    if (state.traditionalBusy) return;
    state.traditionalBusy = true;
    setStatus("Requesting real candles from Twelve Data…");
    $("providerInfo").textContent =
      "Provider: Twelve Data · Symbol: " + symbol;

    try {
      const url = new URL("https://api.twelvedata.com/time_series");
      url.searchParams.set("symbol", symbol);
      url.searchParams.set("interval", state.timeframe);
      url.searchParams.set("outputsize", "100");
      url.searchParams.set("apikey", key);

      const response = await fetch(url.toString());
      const data = await response.json();

      if (!response.ok || data.status === "error" || !data.values) {
        throw new Error(data.message || data.code || "No candle data returned");
      }

      if (symbol !== selectedSymbol() ||
          state.category === "SYNTHETICS") return;

      state.candles = data.values.slice().reverse().map(c => ({
        time:c.datetime,
        open:Number(c.open), high:Number(c.high),
        low:Number(c.low), close:Number(c.close)
      })).filter(c => [c.open,c.high,c.low,c.close].every(Number.isFinite));

      if (!state.candles.length) throw new Error("No valid candles returned");

      state.price = state.candles[state.candles.length-1].close;
      state.lastDataAt = Date.now();
      $("price").textContent = formatPrice(state.price);
      $("priceTime").textContent =
        "Latest candle close · " + state.candles[state.candles.length-1].time;
      setStatus("Twelve Data candles received", "good");
      analyse();
    } catch (error) {
      setStatus("Traditional data error: " + error.message, "bad");
      $("priceTime").textContent = "No verified live price available";
      $("signal").textContent = "WAIT";
      $("reason").textContent =
        "No signal: provider data is missing or unavailable. Check symbol, API key and plan.";
    } finally {
      state.traditionalBusy = false;
    }
  }

  function formatPrice(value) {
    if (!Number.isFinite(value)) return "—";
    return value.toLocaleString(undefined, {
      maximumFractionDigits:value > 100 ? 3 : 5
    });
  }

  function analyse() {
    const candles = state.candles;
    $("candleCount").textContent = String(candles.length);
    drawChart(candles);

    if (candles.length < 25) {
      $("signal").textContent = "WAIT";
      $("reason").textContent = "Not enough candles for analysis yet.";
      return;
    }

    const closes = candles.map(c => c.close);
    const recent = candles.slice(-20);
    const last = candles[candles.length-1];
    const previous = candles[candles.length-2];
    const mean = values => values.reduce((a,b) => a+b,0)/values.length;
    const sma20 = mean(closes.slice(-20));
    const smaPrevious = mean(closes.slice(-25,-5));
    const rangeHigh = Math.max(...recent.slice(0,-1).map(c => c.high));
    const rangeLow = Math.min(...recent.slice(0,-1).map(c => c.low));
    const atr = mean(candles.slice(-14).map(c =>
      Math.max(c.high-c.low, Math.abs(c.high-c.close),
               Math.abs(c.low-c.close))
    ));

    let signal = "WAIT";
    let reason = "No clear breakout with trend confirmation.";
    if (last.close > rangeHigh && last.close > sma20 && sma20 > smaPrevious) {
      signal = "BUY";
      reason = "Price broke above the recent range with an upward average trend.";
    } else if (last.close < rangeLow && last.close < sma20 && sma20 < smaPrevious) {
      signal = "SELL";
      reason = "Price broke below the recent range with a downward average trend.";
    } else if (last.close === previous.close) {
      reason = "Price has not moved enough to confirm a direction.";
    }

    $("signal").textContent = signal;
    $("signal").className = "signal " +
      (signal === "BUY" ? "good" : signal === "SELL" ? "bad" : "gold");
    $("reason").textContent = reason;

    if (signal === "WAIT" || !Number.isFinite(atr) || atr <= 0) {
      $("entry").textContent = "—";
      $("sl").textContent = "—";
      $("tp").textContent = "—";
      return;
    }

    const entry = state.price ?? last.close;
    const risk = atr;
    const stop = signal === "BUY" ? entry-risk : entry+risk;
    const target = signal === "BUY" ? entry+2*risk : entry-2*risk;
    $("entry").textContent = formatPrice(entry);
    $("sl").textContent = formatPrice(stop);
    $("tp").textContent = formatPrice(target);
  }

  function drawChart(candles) {
    const canvas = $("chart");
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, rect.width*dpr);
    canvas.height = Math.max(1, rect.height*dpr);
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr,dpr);
    ctx.clearRect(0,0,rect.width,rect.height);

    if (!candles.length) {
      ctx.fillStyle = "#9eabc2";
      ctx.font = "12px Arial";
      ctx.fillText("Waiting for real candle data", 8, 25);
      return;
    }

    const list = candles.slice(-60);
    const highs = list.map(c => c.high);
    const lows = list.map(c => c.low);
    const max = Math.max(...highs);
    const min = Math.min(...lows);
    const span = max-min || 1;
    const pad = 8;
    const width = rect.width;
    const height = rect.height;
    const candleWidth = Math.max(2,width/list.length*.55);
    const y = value => pad+(max-value)/span*(height-pad*2);

    list.forEach((c,i) => {
      const x = (i+.5)*width/list.length;
      const up = c.close >= c.open;
      ctx.strokeStyle = up ? "#36d69a" : "#ff687b";
      ctx.fillStyle = ctx.strokeStyle;
      ctx.beginPath();
      ctx.moveTo(x,y(c.high));
      ctx.lineTo(x,y(c.low));
      ctx.stroke();

      const top = y(Math.max(c.open,c.close));
      const bottom = y(Math.min(c.open,c.close));
      ctx.fillRect(x-candleWidth/2,top,candleWidth,
        Math.max(1,bottom-top));
    });
  }

  $("categoryTabs").addEventListener("click", event => {
    const button = event.target.closest("button[data-category]");
    if (!button) return;
    state.category = button.dataset.category;
    document.querySelectorAll("#categoryTabs button")
      .forEach(b => b.classList.toggle("active",b===button));
    populateSymbols();
  });

  $("timeframes").addEventListener("click", event => {
    const button = event.target.closest("button[data-tf]");
    if (!button) return;
    state.timeframe = button.dataset.tf;
    document.querySelectorAll("#timeframes button")
      .forEach(b => b.classList.toggle("active",b===button));
    connectSelectedMarket();
  });

  $("symbol").addEventListener("change", connectSelectedMarket);
  $("connectTraditional").addEventListener("click", connectTwelveData);

  window.addEventListener("resize", () => drawChart(state.candles));

  // Refresh traditional-market candles once per minute.
  state.refreshTimer = setInterval(() => {
    if (state.category !== "SYNTHETICS" &&
        document.visibilityState === "visible") {
      connectTwelveData();
    }
  },60000);

  loadDerivSymbols();
})();
</script>
</body>
</html>

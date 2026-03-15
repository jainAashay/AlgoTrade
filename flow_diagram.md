# Algo Trading System – External API Flow (Delta Exchange)

## Legend
- **REST**: Signed/authenticated HTTP request
- **Public REST**: Unauthenticated HTTP request
- **WS**: WebSocket message (client → server) or (server → client)

---

## 1️⃣ Bootstrap (historical candles) – runs once at startup

### Sequence
```
main.py
 └─ bootstrap_candles()
     └─ fetch_ohlc() [Public REST]
         ├─ GET /chart/history
         │    ├─ symbol: BTCUSDT
         │    ├─ resolution: 1 (for 1m)
         │    ├─ from: <start_ts>
         │    └─ to: <now_ts>
         └─ Response: [{ts, open, high, low, close, volume}, ...]
```

### Purpose
- Warm up indicators (EMA/RSI) so strategies can evaluate immediately
- Performed for each `symbol` and each `timeframe` in config

---

## 2️⃣ Product ID Resolution – cached per symbol

### When called
- First order placement per symbol
- Re-used from memory thereafter

```
order_manager.get_product_id()
 └─ delta_client.get_products() [REST]
      ├─ GET /v2/products
      └─ Response: [{id, symbol, ...}, ...]
```

---

## 3️⃣ WebSocket Real-time Data – continuous

### Connection & Subscription
```
main.py
 └─ start_ws()
      ├─ WebSocket connect to wss://testnet-socket.delta.exchange
      └─ on_open()
           └─ SEND WS:
                {
                  "type": "subscribe",
                  "payload": {
                    "channels": [
                      {"name": "candlesticks", "symbols": ["BTCUSDT_1m"]},
                      {"name": "candlesticks", "symbols": ["BTCUSDT_5m"]},
                      ...
                    ]
                  }
                }
```

### Incoming Candle Updates
```
RECEIVE WS:
{
  "type": "candlestick",
  "data": {
    "symbol": "BTCUSDT_1m",
    "open": "...",
    "high": "...",
    "low": "...",
    "close": "...",
    "volume": "..."
  }
}
```

### Processing
- `on_message()` → `add_candle()` → `apply_indicators()` → update `market_data[symbol][tf]`

---

## 4️⃣ Order Lifecycle – per signal

### 4.1 Cancel Expired Orders (TTL)
```
cancel_expired_orders()
 └─ get_open_orders() [REST]
      ├─ GET /v2/orders?product_id=<id>
      └─ Response: [{id, ...}, ...]

 └─ For each expired order:
        cancel_order() [REST]
             ├─ DELETE /v2/orders/<order_id>
             └─ Response: {success: true}
```

### 4.2 Cancel All Orders (trend reversal)
```
cancel_all_orders()
 └─ Same calls as above, but for all open orders
```

### 4.3 Get Open Positions
```
get_open_positions()
 └─ delta_client.get_positions() [REST]
      ├─ GET /v2/positions
      └─ Response: [{product_id, size, ...}, ...]
```

### 4.4 Set Leverage (when flat)
```
change_order_leverage()
 └─ delta_client.set_leverage() [REST]
      ├─ PUT /v2/leverage
      ├─ body: {product_id, leverage}
      └─ Response: {success: true}
```

### 4.5 Get Best Bid/Ask (optional entry price)
```
get_best_bid_ask()
 └─ delta_client.get_orderbook_l2() [REST]
      ├─ GET /v2/orderbook/l2?product_id=<id>&depth=1
      └─ Response: {buy_book: [{price, size}], sell_book: [{price, size}]}
```

### 4.6 Place Entry Order
```
place_market_order() or place_ioc_limit_order()
 └─ delta_client.place_order() [REST]
      ├─ POST /v2/orders
      ├─ body: {
      │      product_id,
      │      side: "buy" | "sell",
      │      order_type: "market" | "limit",
      │      size,
      │      price?,               // only for limit
      │      time_in_force: "ioc", // only for IOC limit
      │      reduce_only: false
      │    }
      └─ Response: {id, status, ...}
```

### 4.7 Place Stop Loss (reduce_only)
```
place_stop_loss_market_order()
 └─ delta_client.place_order() [REST]
      ├─ POST /v2/orders
      ├─ body: {
      │      product_id,
      │      side,
      │      order_type: "market",
      │      size,
      │      stop_price,
      │      stop_order_type: "stop",
      │      close_on_trigger: true,
      │      reduce_only: true
      │    }
      └─ Response: {id, status, ...}
```

### 4.8 Place Take Profit (reduce_only)
```
place_reduce_only_limit_order()
 └─ delta_client.place_order() [REST]
      ├─ POST /v2/orders
      ├─ body: {
      │      product_id,
      │      side,
      │      order_type: "limit",
      │      size,
      │      price,
      │      reduce_only: true
      │    }
      └─ Response: {id, status, ...}
```

---

## 5️⃣ Main Loop – per-second evaluation

```
while True:
  ├─ engine.evaluate()
  │    └─ For each strategy:
  │         └─ generate_signal() → reads market_data[symbol][tf] (updated by WS)
  ├─ For each signal:
  │       ├─ cancel_expired_orders() (REST)
  │       ├─ get_open_positions() (REST)
  │       ├─ [if flat] change_order_leverage() (REST)
  │       ├─ [optional] get_best_bid_ask() (REST)
  │       ├─ place_entry_order() (REST)
  │       ├─ place_stop_loss() (REST)
  │       └─ place_take_profit() (REST)
  └─ sleep(1)
```

---

## 6️⃣ Error Handling & Retries

- All REST calls are wrapped in `try/except` → `logger.exception()`
- WebSocket message errors are logged but do not stop the connection
- Failed orders raise exceptions and abort the current cycle (logged)

---

## 7️⃣ Summary of External Endpoints Used

| Purpose | Method | Endpoint | Auth |
|---------|--------|----------|-------|
| Products catalog | GET | /v2/products | Signed |
| Open orders | GET | /v2/orders | Signed |
| Cancel order | DELETE | /v2/orders/<id> | Signed |
| Positions | GET | /v2/positions | Signed |
| Set leverage | PUT | /v2/leverage | Signed |
| Place order | POST | /v2/orders | Signed |
| Orderbook L2 | GET | /v2/orderbook/l2 | Signed |
| Historical candles | GET | /chart/history | Public |
| Real-time candles | WS | wss://testnet-socket.delta.exchange | Auth (headers) |

---

### Notes
- **Product ID** is cached after first lookup to avoid repeated `/v2/products` calls.
- **Historical candles** are fetched once per symbol/timeframe at startup.
- **Real-time candles** stream continuously via WebSocket.
- **Order TTL** prevents stale limit orders from lingering; only expired orders are cancelled.
- **Trend reversal** triggers `cancel_all_orders()` before closing position.
- **All order placement** is `reduce_only: false` for entry; `reduce_only: true` for SL/TP.

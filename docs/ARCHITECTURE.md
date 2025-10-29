# Hedge Bot V2 Architecture

## System Overview

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           HEDGE BOT V2 ARCHITECTURE                        │
└──────────────────────────────────────────────────────────────────────────┘

                              ┌─────────────┐
                              │   main()    │
                              │ hedge_bot_v2│
                              └──────┬──────┘
                                     │
                          ┌──────────▼──────────┐
                          │  TradingStateMachine│
                          │   (Core Controller) │
                          └──────────┬──────────┘
                                     │
                ┌────────────────────┼────────────────────┐
                │                    │                    │
                ▼                    ▼                    ▼
        ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
        │SafetyManager │    │PositionManager│    │ OrderManager │
        └──────────────┘    └──────────────┘    └──────────────┘
                │                    │                    │
        ┌───────▼────────┐  ┌───────▼────────┐  ┌───────▼────────┐
        │ Pre-Trade Check│  │ Get Positions  │  │ Place Orders   │
        │ Emergency Stop │  │ (API Only)     │  │ Cancel Orders  │
        │ Threshold Check│  │ Cache (5s TTL) │  │ Size Limits    │
        └────────────────┘  └───────┬────────┘  └───────┬────────┘
                                     │                    │
                            ┌────────▼────────────────────▼────────┐
                            │        Exchange Clients              │
                            ├──────────────────┬───────────────────┤
                            │   GRVT Client   │  Lighter Client   │
                            │  (Post-Only)    │  (Market Orders)  │
                            └──────────────────┴───────────────────┘
```

## State Machine Flow

```
    ┌──────┐      ┌──────────┐      ┌─────────┐      ┌────────────┐
    │ IDLE │ ───► │ BUILDING │ ───► │ HOLDING │ ───► │WINDING_DOWN│
    └──────┘      └──────────┘      └─────────┘      └────────────┘
        ▲              │                  │                  │
        │              │                  │                  │
        └──────────────┴──────────────────┴──────────────────┘
                            │
                            ▼
                    ┌───────────────┐
                    │EMERGENCY_STOP │ (Can be triggered from any state)
                    └───────────────┘
```

## Safety Check Flow

```
Before Every Trade:
    │
    ▼
┌─────────────────┐     NO
│ Safety Check    │─────────► STOP TRADING
│ - Position < Max│
│ - Diff < Tolerance│
│ - Orders <= 1   │
└────────┬────────┘
         │YES
         ▼
    EXECUTE TRADE
```

## Data Flow Example

### 1. BUILD Phase

```
StateMachine ──► SafetyManager.pre_trade_check()
                        │
                        ▼
                 PositionManager.get_positions()
                        │
                        ▼
                 Check: diff < 0.15?
                        │
                        ▼ YES
                 OrderManager.place_hedge_order()
                        │
                 ┌──────┴──────┐
                 ▼             ▼
          GRVT.place()    Lighter.place()
          (Post-Only)     (Market Order)
```

### 2. HOLD Phase

```
Wait for configured time (e.g., 180s)
Monitor positions periodically
```

### 3. WINDDOWN Phase

```
Loop until position ≈ 0:
   │
   ▼
Get current position
   │
   ▼
Place close orders (max SIZE per iteration)
   │
   ▼
Check if |position| < 0.001 → Done
```

## Module Responsibilities

### SafetyManager

- **Position Limits**: Enforce MAX_POSITION parameter
- **Imbalance Check**: Monitor REBALANCE_TOLERANCE (default 0.15)
- **Critical Threshold**: 10x SIZE triggers emergency stop
- **Open Orders Check**: Limit to MAX_OPEN_ORDERS

### PositionManager

- **Pure API**: NEVER accumulate positions locally
- **Caching**: 5-second TTL to reduce API calls
- **Parallel Fetching**: Query both exchanges simultaneously
- **Fallback**: Use cached values on API errors

### OrderManager

- **Size Enforcement**: Never exceed SIZE parameter
- **Retry Logic**: 3 attempts with exponential backoff
- **Atomic Operations**: Orders either fully succeed or fully fail
- **Cleanup**: Automatic cancellation on failures

### TradingStateMachine

- **State Management**: Track current phase (BUILD/HOLD/WINDDOWN)
- **Cycle Control**: Execute configured number of cycles
- **Direction Management**: Handle long/short/random strategies
- **Emergency Stop**: Coordinate shutdown across all components

## Configuration Flow

```
Environment Variables / .env
            │
            ▼
      TradingConfig
            │
    ┌───────┼───────┐
    │       │       │
    ▼       ▼       ▼
Safety  Position  Order
Manager  Manager  Manager
```

## Error Handling

```
Try Operation
    │
    ├─► Success: Continue
    │
    └─► Failure:
         │
         ├─► Retry (if retriable)
         │
         ├─► Use Fallback (if available)
         │
         └─► Emergency Stop (if critical)
```

## Key Safety Features

1. **No Local State**: Positions always from API
2. **Size Limits**: Every order respects SIZE parameter
3. **Graduated Response**: Warning → Stop → Emergency
4. **Atomic Operations**: No partial states
5. **Automatic Cleanup**: Failed operations cleaned up

## Performance Optimizations

- **Position Cache**: 5-second TTL reduces API calls
- **Parallel API Calls**: Fetch from both exchanges simultaneously
- **Exponential Backoff**: Intelligent retry delays
- **Early Exit**: Stop immediately on critical errors
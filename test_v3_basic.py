#!/usr/bin/env python3
"""
基础测试V3架构 - 不需要真实的API keys
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_basic():
    print("Testing V3 architecture basics...")

    # 1. 测试导入
    print("✓ Testing imports...")
    from hedge.services import HedgeService, GrvtLighterHedgeService
    from hedge.core.trading_engine import TradingEngine
    from hedge.managers import SafetyManager, SafetyLevel
    print("  ✓ All imports successful")

    # 2. 测试接口
    print("✓ Testing interfaces...")
    assert hasattr(HedgeService, 'get_positions')
    assert hasattr(HedgeService, 'execute_hedge_cycle')
    assert hasattr(TradingEngine, 'start')
    print("  ✓ All interfaces present")

    # 3. 测试SafetyLevel
    print("✓ Testing SafetyLevel enum...")
    assert SafetyLevel.NORMAL < SafetyLevel.WARNING
    assert SafetyLevel.WARNING < SafetyLevel.AUTO_REBALANCE
    assert SafetyLevel.AUTO_REBALANCE < SafetyLevel.PAUSE
    assert SafetyLevel.PAUSE < SafetyLevel.EMERGENCY
    print("  ✓ SafetyLevel ordering correct")

    print("\n✅ All basic tests passed!")
    return True

if __name__ == "__main__":
    success = test_basic()
    sys.exit(0 if success else 1)
#!/usr/bin/env python3
"""
测试V3架构的脚本。
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s: %(message)s')

async def test_architecture():
    """测试新架构的基本功能"""
    logger = logging.getLogger("test_v3")

    try:
        # 测试导入
        logger.info("Testing imports...")
        from hedge.services import HedgeService, GrvtLighterHedgeService
        from hedge.core.trading_engine import TradingEngine
        from hedge.managers import SafetyManager
        logger.info("✓ All imports successful")

        # 测试服务接口
        logger.info("\nTesting service interface...")
        assert hasattr(HedgeService, 'get_positions')
        assert hasattr(HedgeService, 'execute_hedge_cycle')
        assert hasattr(HedgeService, 'rebalance_positions')
        logger.info("✓ Service interface methods present")

        # 测试引擎
        logger.info("\nTesting trading engine...")
        assert hasattr(TradingEngine, 'start')
        assert hasattr(TradingEngine, 'stop')
        assert hasattr(TradingEngine, 'get_status')
        logger.info("✓ Trading engine methods present")

        # 测试配置加载
        logger.info("\nTesting configuration loading...")
        from hedge.hedge_bot_v3 import load_config

        # 设置测试环境变量
        os.environ['GRVT_API_KEY'] = 'test_grvt_key'
        os.environ['GRVT_PRIVATE_KEY'] = 'test_grvt_private'
        os.environ['LIGHTER_API_KEY'] = 'test_lighter_key'
        os.environ['LIGHTER_PRIVATE_KEY'] = 'test_lighter_private'

        config = load_config()
        # 只验证配置对象被成功创建
        assert config is not None
        assert hasattr(config, 'grvt_api_key')
        assert hasattr(config, 'lighter_api_key')
        assert hasattr(config, 'order_quantity')
        logger.info("✓ Configuration loading successful")

        logger.info("\n" + "="*50)
        logger.info("✅ All tests passed! V3 architecture is ready.")
        logger.info("="*50)

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    return True

if __name__ == "__main__":
    success = asyncio.run(test_architecture())
    sys.exit(0 if success else 1)
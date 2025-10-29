# 项目目录结构说明

## 当前目录结构分析

### 🔴 问题识别
1. **根目录混乱**：测试文件、主程序、工具脚本混在一起
2. **命名不一致**：有些用下划线(hedge_mode.py)，有些用驼峰(runbot.py)
3. **版本混淆**：hedge_bot_v2.py, hedge_bot_v3.py, 还有旧的实现
4. **功能重复**：trading_bot.py和hedge/目录下的bot似乎功能重叠

## 📁 当前结构

```
lantern/
├── 📁 核心代码
│   ├── hedge/                 # 对冲交易核心 (V3新架构)
│   │   ├── core/              # 核心引擎
│   │   ├── services/          # 服务层(新)
│   │   ├── managers/          # 管理器
│   │   ├── models/            # 数据模型
│   │   ├── deprecated/        # 废弃代码
│   │   └── hedge_bot_v3.py    # V3入口(最新)
│   │
│   ├── exchanges/             # 交易所接口
│   │   ├── grvt.py
│   │   ├── apex.py
│   │   └── ...
│   │
│   └── lighter/               # Lighter交易所特殊实现
│
├── 📁 辅助功能
│   ├── helpers/               # 辅助工具
│   │   ├── telegram_bot.py   # Telegram通知
│   │   ├── lark_bot.py       # Lark通知
│   │   └── logger.py         # 日志工具
│   │
│   └── tests/                 # 测试文件
│       └── test_query_retry.py
│
├── 📁 配置和文档
│   ├── docs/                  # 文档
│   ├── .env                   # 环境变量
│   ├── .env.docker.example    # Docker环境示例
│   ├── docker-compose.yml     # Docker配置
│   ├── Dockerfile
│   └── requirements.txt       # 依赖
│
├── 📁 根目录程序（需要整理）
│   ├── trading_bot.py         # 旧的交易机器人？
│   ├── runbot.py             # 旧的运行脚本？
│   ├── hedge_mode.py         # 对冲模式入口（旧）
│   ├── test_v3_*.py          # V3测试文件
│   └── V3_ARCHITECTURE_SUMMARY.md
│
└── 📁 其他
    ├── env/                   # Python虚拟环境
    └── logs/                  # 日志文件
```

## 🎯 建议的目录重组方案

```
lantern/
├── src/                       # 所有源代码
│   ├── hedge/                # 对冲交易模块
│   ├── exchanges/            # 交易所接口
│   ├── lighter/              # Lighter特殊实现
│   └── utils/                # 工具类(原helpers)
│
├── tests/                     # 所有测试
│   ├── unit/                # 单元测试
│   ├── integration/          # 集成测试
│   └── fixtures/             # 测试数据
│
├── scripts/                   # 运行脚本
│   ├── run_hedge_v3.py      # V3运行脚本
│   └── run_legacy.py        # 旧版本运行脚本
│
├── config/                    # 配置文件
│   ├── .env.example
│   └── docker/
│       ├── Dockerfile
│       └── docker-compose.yml
│
├── docs/                      # 文档
│   ├── architecture/         # 架构文档
│   ├── setup/               # 安装指南
│   └── api/                 # API文档
│
├── deprecated/                # 废弃代码
│   ├── trading_bot.py
│   ├── runbot.py
│   └── hedge_mode.py
│
└── [根目录文件]
    ├── README.md
    ├── LICENSE
    ├── requirements.txt
    └── .gitignore
```

## 📋 整理步骤

### 第一步：备份和创建新结构
```bash
# 1. 创建新目录结构
mkdir -p src tests/unit tests/integration scripts config/docker deprecated

# 2. 移动废弃文件
mv trading_bot.py runbot.py hedge_mode.py deprecated/

# 3. 移动测试文件
mv test_v3_*.py tests/
mv tests/test_query_retry.py tests/unit/
```

### 第二步：重组核心代码
```bash
# 1. 移动核心模块
mv hedge src/
mv exchanges src/
mv lighter src/
mv helpers src/utils

# 2. 移动配置文件
mv Dockerfile docker-compose.yml config/docker/
mv .env.docker.example config/
```

### 第三步：创建新的入口脚本
```bash
# 在scripts/目录创建清晰的运行脚本
# run_hedge_v3.py - 运行V3架构
# run_hedge_v2.py - 运行V2架构(如果需要)
```

## 🚀 使用新结构的好处

1. **清晰的模块划分**：src/包含所有源代码，tests/包含所有测试
2. **版本管理**：deprecated/保存旧代码，避免混淆
3. **易于维护**：每个目录职责单一
4. **标准化**：符合Python项目的最佳实践
5. **易于部署**：config/集中管理所有配置

## ⚠️ 注意事项

1. **保持向后兼容**：整理时确保现有功能不受影响
2. **更新导入路径**：移动文件后需要更新所有import语句
3. **更新文档**：确保README和其他文档反映新结构
4. **测试验证**：每步整理后运行测试确保功能正常

## 现在需要决定

1. 是否按照建议重组目录？
2. 是否保留V2版本还是完全迁移到V3？
3. trading_bot.py和runbot.py是否还在使用？
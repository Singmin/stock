# ETF Rotation System 项目日志

## 工作规则

每次开始修改这个项目之前，先阅读本文档。

阅读后需要确认三件事：

1. 当前项目目标是什么。
2. 上一次做到哪里。
3. 本次工作是否符合既定技术路线。

如果技术路线发生变化，先更新本文档，再改代码。

## 项目目标

做一个可学习、可验证、可逐步扩展的 ETF 量化交易系统原型。

短期目标不是直接实盘赚钱，而是先建立完整研究闭环：

- 获取或缓存 ETF 历史行情
- 运行 ETF 动量轮动策略
- 生成回测指标、净值曲线、持仓记录和调仓记录
- 用前端面板查看策略表现
- 后续接入真实数据、参数测试、每日信号和模拟交易

## 技术路线

### 后端与回测

- 语言：Python
- 核心库：pandas、numpy、matplotlib、openpyxl
- 数据源优先级：
  1. 本地缓存 `data/raw/*.csv`
  2. AkShare 真实 ETF 数据
  3. 无法联网时使用固定随机种子的 synthetic 实验数据
- 策略原型：
  - ETF 池：沪深300、中证500、创业板、红利、黄金、纳指、恒生科技、国债 ETF
  - 打分：20/60/120 日动量加权
  - 风控：60 日波动率惩罚、120 日正动量过滤
  - 调仓：默认每周五
  - 持仓：默认 Top 2 等权
  - 成本：默认单边 0.08%

### 前端面板

- 框架：React + Vite + TypeScript
- 图标：lucide-react
- 样式：原生 CSS
- 数据读取：
  - `/output/metrics.json`
  - `/output/equity_curve.csv`
  - `/output/daily_weights.csv`
  - `/output/rebalance_log.csv`
- Vite 插件负责把本地 `output` 目录暴露为 `/output/*`
- 前端只负责展示，不直接修改回测结果

### 项目原则

- 先做可验证闭环，再追求复杂功能。
- 每个阶段都要能独立运行。
- 先用简单可解释策略，不急着引入机器学习。
- 所有回测结果都要能复现。
- 实盘之前必须加入真实数据校验、交易约束、日志、告警和风控。

## 当前文件结构

```text
etf_rotation_system/
  etf_rotation_backtest.py    # Python 回测主脚本
  README.md                   # 使用说明
  PROJECT_LOG.md              # 项目日志与技术路线
  serve_dashboard.py          # 早期零依赖静态面板服务脚本，后续可保留或移除
  package.json                # React 前端依赖与脚本
  vite.config.ts              # Vite 配置和 output 数据服务插件
  tsconfig.json               # TypeScript 配置
  index.html                  # React 入口 HTML
  src/
    main.tsx                  # React 面板主逻辑
    styles.css                # React 面板样式
  data/
    raw/                      # 真实 ETF 数据缓存
  output/                     # 回测输出结果
  dashboard/                  # 早期零依赖 HTML 面板，后续可保留或移除
```

## 当前进度

### 已完成

- 创建了独立项目目录 `etf_rotation_system`
- 实现了 Python ETF 轮动回测脚本
- 实现了本地缓存、AkShare 数据入口和 synthetic 数据兜底
- 生成了以下回测输出：
  - `output/equity_curve.csv`
  - `output/daily_weights.csv`
  - `output/rebalance_log.csv`
  - `output/metrics.json`
  - `output/results.xlsx`
  - `output/equity_curve.png`
  - `output/report.md`
- 用 synthetic 数据跑通过一次完整回测
- 添加了早期零依赖 HTML 面板
- 按用户要求改为 React 技术路线，并创建了 React + Vite + TypeScript 前端工程

### 当前阻塞

React 前端依赖已经由用户安装完成，前端可启动。

当前发现的工程问题：

- 当前 Node 版本是 `22.3.0`
- 已安装的 Vite 7 要求 Node `20.19+` 或 `22.12+`
- 因此 `npm run build` 会失败
- 已按决策把 `package.json` 降级到 Vite 6.x 和 `@vitejs/plugin-react` 4.x，而不是要求升级本机 Node
- 用户会自行运行 `npm install` 更新 `package-lock.json` 和 `node_modules`

## 下一步计划

1. 安装前端依赖：

   ```powershell
   cd C:\Users\Singmin\Desktop\stock\etf_rotation_system
   npm install
   ```

2. 启动 React 面板：

   ```powershell
   npm run dev
   ```

3. 打开：

   ```text
   http://127.0.0.1:5173/
   ```

4. 验证前端是否正确读取 `output` 数据。

5. 当前阶段接入真实 AkShare ETF 数据，并补充数据质量与数据来源展示。

6. 后续增强：

   - 参数测试页面
   - ETF 成交额过滤
   - 样本内/样本外验证
   - 每日最新信号生成
   - 模拟交易记录
   - 策略配置页面
   - 风控和告警模块

## 更新记录

### 2026-06-15

- 用户确认下一阶段优先接入 Futu 模拟盘，而不是本地虚拟撮合。
- 新增 `trade_signal.json` 输出，记录最新策略目标仓位、Futu 代码映射、信号日期和建议调仓日期。
- 新增 Futu 模拟盘脚本：`futu_sim_preflight.py`、`generate_futu_sim_orders.py`、`execute_futu_sim_orders.py`。
- 新增共享模块 `futu_sim_common.py`，统一处理 Futu skill 脚本路径、模拟账户筛选、JSON/CSV 输出和安全环境。
- 模拟盘流程固定使用 `SIMULATE`，当前项目不接入实盘；执行脚本必须显式传 `--confirmed`。
- 新增前端 “Futu 模拟盘” 面板，展示预检、资金持仓、策略信号、订单预览、风控结果和最近订单；前端不直接发单。
- 模拟盘订单预览新增三种模式：`observe` 观察、`cash-only` 只用现金调仓、`full-account` 全账户调仓。

### 2026-06-13

- 建立 ETF 轮动系统原型。
- 新增 `etf_rotation_backtest.py`。
- 新增 `README.md`。
- 使用 synthetic 数据完成第一次回测。
- 生成回测结果文件和图表。
- 新增零依赖静态面板 `dashboard/index.html` 和 `serve_dashboard.py`。
- 根据用户要求切换为 React 前端路线。
- 新增 `package.json`、`index.html`、`tsconfig.json`、`vite.config.ts`、`src/main.tsx`、`src/styles.css`。
- React 前端代码已写好，但依赖安装未完成。
- 新增本文档 `PROJECT_LOG.md`，作为后续每次工作的起点。
- 用户确认前端已经跑起来。
- 决定下一阶段先做真实 ETF 数据可信闭环，不做参数测试页和模拟交易。
- 决定 `--data-source akshare` 使用严格模式：真实数据失败就停止，不自动降级到 synthetic。
- 决定新增 `run_meta.json`、`data_quality.csv`、`data_quality.json`，让前端明确展示数据来源、缓存状态和数据质量。
- 决定前端依赖降级到 Vite 6.x / `@vitejs/plugin-react` 4.x，以兼容当前 Node `22.3.0`。
- 已实现 `PriceLoadResult`，让数据加载同时返回价格矩阵、实际数据模式、数据质量和来源状态。
- 已实现数据质量检查：有效数据覆盖率、重复日期、异常涨跌幅、warning/error 状态。
- 已实现新增输出：`output/run_meta.json`、`output/data_quality.csv`、`output/data_quality.json`。
- 已实现前端数据来源 badge、synthetic 警示、数据质量提示和数据质量表。
- 已把 `package.json` 固定到 `vite@6.3.5`、`@vitejs/plugin-react@4.7.0`，并新增 `@types/react`、`@types/react-dom`。
- 已验证 `python -m py_compile etf_rotation_backtest.py` 通过。
- 已验证 synthetic 回测能生成完整输出。
- 已验证 `--data-source akshare` 在 AkShare 网络失败时停止，并输出 `no synthetic fallback was used`，不会静默降级。
- 已新增 `output/price_series.json`，为前端提供每只 ETF 的历史价格序列。
- 已新增 React “ETF 行情中心”：ETF 列表、最新收盘、日涨跌、20/60/120 日动量、目标权重、日线走势图。
- 当前“ETF 行情中心”的日线来自本次回测数据；真实数据跑通后会自动展示真实 ETF 日线。
- 分时图接口暂未接入，下一步可用 AkShare `fund_etf_hist_min_em` 输出分钟线数据，再在前端增加“分时/日线”切换。
- 用户说明当前证券账户是银河证券，通过同花顺入口使用。
- 实盘接口路线调整：不优先做同花顺客户端自动化；后续优先确认银河是否支持 QMT/Ptrade/券商量化终端或其他正式 API。
- 已接入分时输出文件：`output/intraday_series.json` 和 `output/market_snapshot.json`。
- 已在前端行情中心增加“日线 / 分时”切换。
- 当前 synthetic 模式下分时为日线派生数据，前端会显示来源提示；真实 AkShare 分钟线跑通后会显示 AkShare 分钟线来源。

## 决策记录

### 为什么先做 ETF 轮动

ETF 比个股更适合作为第一个量化系统原型：

- 标的数量少，便于理解和验证
- 停牌、财务造假、退市等问题相对少
- 流动性和交易规则更容易处理
- 策略逻辑更直观，适合初期建立研究框架

### 为什么先不用机器学习

当前阶段重点是建立可靠研究闭环。

机器学习会引入更多问题：

- 数据泄漏
- 过拟合
- 特征工程复杂
- 样本外不稳定
- 难解释

因此先用动量轮动这种简单策略验证系统能力。

### 为什么前端使用 React

用户明确要求使用 React 框架。

React 适合后续扩展：

- 策略参数配置
- 图表交互
- 多策略对比
- 回测任务管理
- 每日信号面板
- 模拟交易记录

### 为什么真实数据失败时停止

当用户显式指定 `--data-source akshare` 时，系统必须保证结果来自真实行情或有效缓存。

如果真实数据失败后自动降级 synthetic，容易把实验数据误判为真实回测，影响策略判断。因此：

- `akshare` 模式失败就停止
- `auto` 模式允许 fallback，但必须在输出和前端醒目标记
- `synthetic` 只作为离线演示和流程验证

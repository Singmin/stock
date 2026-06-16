# ETF Rotation System

一个小而完整的 ETF 动量轮动原型，用来学习和验证量化交易系统的基本链路：

- 获取或缓存 ETF 日线数据
- 计算 20/60/120 日动量和波动率惩罚
- 每周或每月调仓
- 加入手续费和换手成本
- 输出净值曲线、指标、持仓记录和报告

## 快速运行

```powershell
cd C:\Users\Singmin\Desktop\stock\etf_rotation_system
python etf_rotation_backtest.py
```

默认会先尝试使用 `data/raw/*.csv` 本地缓存；如果没有缓存且无法访问 AkShare 数据源，会自动生成一份固定随机种子的实验数据，保证流程能完整跑通。

## 打开 React 前端面板

先跑一次回测生成 `output` 文件，然后启动本地面板：

```powershell
cd C:\Users\Singmin\Desktop\stock\etf_rotation_system
npm install
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173/
```

这个面板使用 Vite + React + TypeScript，会读取 `output/metrics.json`、`output/equity_curve.csv`、`output/daily_weights.csv` 和 `output/rebalance_log.csv`。

## 使用真实数据

```powershell
python etf_rotation_backtest.py --data-source futu --end 2026-06-12
python etf_rotation_backtest.py --data-source akshare --end 2026-06-12
```

如果本机代理干扰 AkShare，可以加：

```powershell
python etf_rotation_backtest.py --data-source akshare --clear-proxy
```

## 常用参数

```powershell
python etf_rotation_backtest.py --rebalance W-FRI --top-n 2 --fee-rate 0.001
python etf_rotation_backtest.py --rebalance ME --top-n 3 --risk-penalty 0.25
python etf_rotation_backtest.py --data-source synthetic --end 2026-06-12
```

## Futu 模拟盘交易闭环

先生成最新回测和交易信号：

```powershell
python etf_rotation_backtest.py --data-source futu
```

检查 OpenD、SDK 和模拟账户权限：

```powershell
python futu_sim_preflight.py
```

生成模拟盘订单预览和风控结果，不会下单。支持三种模式：

```powershell
python generate_futu_sim_orders.py --mode observe
python generate_futu_sim_orders.py --mode cash-only --cash-buffer 0.05
python generate_futu_sim_orders.py --mode full-account --cash-buffer 0.05
```

- `observe`: 观察模式，只刷新账户、持仓和策略信号，不生成可执行订单
- `cash-only`: 只用现金调仓，不卖出现有非 ETF 持仓
- `full-account`: 全账户调仓，允许卖出现有非 ETF 持仓并转向目标 ETF

确认 `output/futu_sim_order_preview.json` 的风控状态为 `pass` 后，显式执行模拟盘订单：

```powershell
python execute_futu_sim_orders.py --confirmed
```

所有交易命令固定使用 `SIMULATE`，当前项目不接入实盘。

## 输出文件

运行后会生成：

- `output/equity_curve.csv`: 策略和基准每日净值
- `output/daily_weights.csv`: 每日有效持仓权重
- `output/rebalance_log.csv`: 每次调仓记录
- `output/metrics.json`: 核心绩效指标
- `output/run_meta.json`: 本次运行的数据来源、参数、ETF 池和数据状态
- `output/trade_signal.json`: 最新策略目标仓位和 Futu 代码映射
- `output/futu_sim_account.json`: Futu 模拟账户预检结果
- `output/futu_sim_positions.json`: Futu 模拟盘资金和持仓快照
- `output/futu_sim_order_preview.json`: 模拟盘订单预览和风控结果
- `output/futu_sim_orders.csv`: 模拟盘订单预览表
- `output/futu_sim_execution_log.jsonl`: 模拟盘执行审计日志
- `output/data_quality.csv`: 每只 ETF 的数据质量检查表
- `output/data_quality.json`: 前端读取的数据质量 JSON
- `output/results.xlsx`: 汇总 Excel
- `output/equity_curve.png`: 净值图
- `output/report.md`: 中文回测报告

## 数据模式

```powershell
python etf_rotation_backtest.py --data-source synthetic
```

只使用实验数据，适合离线验证流程。

```powershell
python etf_rotation_backtest.py --data-source auto --clear-proxy
```

优先使用本地缓存或 AkShare；如果真实数据不可用，会 fallback 到 synthetic，并在 `run_meta.json` 和前端面板中标注。

```powershell
python etf_rotation_backtest.py --data-source akshare --clear-proxy
```

严格真实数据模式。如果 AkShare 下载失败、字段异常或有效数据不足，会直接停止，不会降级到 synthetic。

## 重要提醒

这个项目是研究原型，不是实盘交易建议。真正上实盘前至少要补：

- 更可靠的数据源和复权校验
- 停牌、涨跌停、成交额、冲击成本约束
- 参数稳定性测试和样本外测试
- 模拟盘执行和风控监控
- 日志、告警、异常恢复

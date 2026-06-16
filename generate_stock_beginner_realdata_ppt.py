from __future__ import annotations

import json
import re
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import requests
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt


ROOT = Path(r"C:\Users\Singmin\Desktop\stock")
OUT = ROOT / "炒股初学者入门课_真实行情图解版.pptx"
ASSET_DIR = ROOT / "real_stock_charts"
ASSET_DIR.mkdir(exist_ok=True)

FONT = "Microsoft YaHei"
BG = RGBColor(15, 26, 38)
BG2 = RGBColor(28, 45, 62)
CARD = RGBColor(247, 250, 253)
TEXT = RGBColor(34, 47, 60)
MUTED = RGBColor(102, 115, 128)
WHITE = RGBColor(255, 255, 255)
RED = RGBColor(220, 64, 82)
GREEN = RGBColor(26, 156, 112)
BLUE = RGBColor(70, 135, 210)
GOLD = RGBColor(220, 164, 58)
CYAN = RGBColor(58, 180, 190)


STOCKS = [
    {"market": "A股", "name": "贵州茅台", "code": "600519.SH", "src": "tencent", "symbol": "sh600519", "type": "消费龙头", "color": RED},
    {"market": "A股", "name": "宁德时代", "code": "300750.SZ", "src": "tencent", "symbol": "sz300750", "type": "新能源成长", "color": GREEN},
    {"market": "A股", "name": "工商银行", "code": "601398.SH", "src": "tencent", "symbol": "sh601398", "type": "大型银行", "color": BLUE},
    {"market": "港股", "name": "腾讯控股", "code": "00700.HK", "src": "tencent", "symbol": "hk00700", "type": "互联网平台", "color": CYAN},
    {"market": "港股", "name": "阿里巴巴-W", "code": "09988.HK", "src": "tencent", "symbol": "hk09988", "type": "电商/云", "color": GOLD},
    {"market": "港股", "name": "汇丰控股", "code": "00005.HK", "src": "tencent", "symbol": "hk00005", "type": "国际银行", "color": BLUE},
    {"market": "美股", "name": "Apple", "code": "AAPL", "src": "nasdaq", "symbol": "AAPL", "type": "消费电子", "color": RGBColor(90, 105, 120)},
    {"market": "美股", "name": "NVIDIA", "code": "NVDA", "src": "nasdaq", "symbol": "NVDA", "type": "AI芯片", "color": RED},
    {"market": "美股", "name": "Tesla", "code": "TSLA", "src": "nasdaq", "symbol": "TSLA", "type": "高波动成长", "color": GREEN},
]


def no_proxy_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.headers.update({"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"})
    return s


def fetch_tencent(symbol: str) -> pd.DataFrame:
    session = no_proxy_session()
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
    resp = session.get(url, params={"param": f"{symbol},day,,,260,qfq"}, timeout=25)
    resp.raise_for_status()
    payload = resp.json()
    item = payload["data"][symbol]
    rows = item.get("qfqday") or item.get("day")
    records = []
    for row in rows:
        records.append({
            "Date": pd.to_datetime(row[0]),
            "Open": float(row[1]),
            "Close": float(row[2]),
            "High": float(row[3]),
            "Low": float(row[4]),
            "Volume": float(row[5]),
        })
    df = pd.DataFrame(records).set_index("Date").sort_index()
    return df.tail(190)


def money_to_float(value: str) -> float:
    return float(re.sub(r"[$,]", "", value))


def fetch_nasdaq(symbol: str) -> pd.DataFrame:
    session = no_proxy_session()
    session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com",
        "Referer": "https://www.nasdaq.com/",
    })
    url = f"https://api.nasdaq.com/api/quote/{symbol}/historical"
    params = {"assetclass": "stocks", "fromdate": "2025-06-12", "todate": "2026-06-12", "limit": "9999"}
    resp = session.get(url, params=params, timeout=25)
    resp.raise_for_status()
    rows = resp.json()["data"]["tradesTable"]["rows"]
    records = []
    for row in rows:
        records.append({
            "Date": pd.to_datetime(row["date"]),
            "Open": money_to_float(row["open"]),
            "Close": money_to_float(row["close"]),
            "High": money_to_float(row["high"]),
            "Low": money_to_float(row["low"]),
            "Volume": float(row["volume"].replace(",", "")),
        })
    df = pd.DataFrame(records).set_index("Date").sort_index()
    return df.tail(190)


def fetch_all() -> dict[str, pd.DataFrame]:
    data = {}
    for stock in STOCKS:
        if stock["src"] == "tencent":
            df = fetch_tencent(stock["symbol"])
        else:
            df = fetch_nasdaq(stock["symbol"])
        data[stock["code"]] = df
        time.sleep(0.25)
    return data


def render_chart(stock: dict, df: pd.DataFrame, wide: bool = False) -> Path:
    path = ASSET_DIR / f"{stock['code'].replace('.', '_')}.png"
    title = f"{stock['name']} {stock['code']}  日K + MA5/20/60"
    mc = mpf.make_marketcolors(up="#d84a5f", down="#159a70", edge="inherit", wick="inherit", volume="inherit")
    style = mpf.make_mpf_style(base_mpf_style="yahoo", marketcolors=mc, rc={
        "font.family": "Microsoft YaHei",
        "axes.unicode_minus": False,
        "figure.facecolor": "white",
    })
    figsize = (9.6, 4.9) if wide else (5.8, 4.1)
    mpf.plot(
        df,
        type="candle",
        mav=(5, 20, 60),
        volume=True,
        style=style,
        title=title,
        ylabel="价格",
        ylabel_lower="成交量",
        figsize=figsize,
        savefig=dict(fname=str(path), dpi=170, bbox_inches="tight"),
        warn_too_much_data=1000,
    )
    return path


def pct_change(df: pd.DataFrame) -> float:
    return (df["Close"].iloc[-1] / df["Close"].iloc[0] - 1) * 100


def last_price(df: pd.DataFrame) -> float:
    return float(df["Close"].iloc[-1])


prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank = prs.slide_layouts[6]


def fill(shape, color):
    shape.fill.solid()
    shape.fill.fore_color.rgb = color


def no_line(shape):
    shape.line.fill.background()


def add_bg(slide):
    r = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, prs.slide_width, prs.slide_height)
    fill(r, BG)
    no_line(r)
    band = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.95))
    fill(band, BG2)
    no_line(band)


def tx(slide, x, y, w, h, text, size=18, color=TEXT, bold=False, align=PP_ALIGN.LEFT, valign=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.margin_left = Inches(0.06)
    tf.margin_right = Inches(0.06)
    tf.margin_top = Inches(0.03)
    tf.margin_bottom = Inches(0.03)
    tf.vertical_anchor = valign
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = FONT
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def header(slide, title, page, section="真实行情图解版"):
    tx(slide, 0.55, 0.21, 9.0, 0.45, title, 22, WHITE, True)
    tx(slide, 10.35, 0.28, 2.25, 0.22, section, 9.5, RGBColor(190, 210, 226), False, PP_ALIGN.RIGHT)
    tx(slide, 12.58, 7.22, 0.45, 0.16, f"{page:02d}", 8, RGBColor(160, 176, 190), False, PP_ALIGN.RIGHT)


def footer(slide, note="真实股票仅作教学样本，不构成投资建议；行情数据来自公开接口，生成时间为 2026-06-12。"):
    tx(slide, 0.55, 7.17, 12.0, 0.22, note, 7.5, RGBColor(185, 199, 211))


def card(slide, x, y, w, h, color=CARD):
    c = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    c.adjustments[0] = 0.06
    fill(c, color)
    c.line.color.rgb = RGBColor(218, 228, 237)
    c.line.width = Pt(0.7)
    return c


def bullets(slide, x, y, w, h, items, size=17):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item
        p.font.name = FONT
        p.font.size = Pt(size)
        p.font.color.rgb = TEXT
        p.space_after = Pt(7)
        p._p.get_or_add_pPr().set("marL", "160000")
        p._p.get_or_add_pPr().set("indent", "-100000")


def slide_base(title, page):
    slide = prs.slides.add_slide(blank)
    add_bg(slide)
    header(slide, title, page)
    footer(slide)
    return slide


def cover(charts, page):
    slide = prs.slides.add_slide(blank)
    add_bg(slide)
    tx(slide, 0.72, 0.72, 5.5, 0.35, "真实行情图解版 · 炒股初学者", 15, RGBColor(190, 210, 226), True)
    tx(slide, 0.68, 1.35, 7.7, 1.1, "炒股初学者入门课", 44, WHITE, True)
    tx(slide, 0.74, 2.52, 7.2, 0.44, "用真实股票图表讲规则、K线、均线和风控", 21, RGBColor(218, 231, 240))
    for i, code in enumerate(["600519.SH", "00700.HK", "NVDA"]):
        x = 7.65 + (i % 1) * 0
        y = 0.95 + i * 1.83
        card(slide, x, y, 4.8, 1.5, WHITE)
        slide.shapes.add_picture(str(charts[code]), Inches(x + 0.1), Inches(y + 0.14), width=Inches(4.6), height=Inches(1.22))
    tx(slide, 0.72, 6.35, 7.3, 0.3, "案例股票只用于教学观察，不构成任何买卖建议。", 13.5, RGBColor(203, 216, 227))
    footer(slide)


def rules_table(page):
    slide = slide_base("先把三地交易规则放在一张图里", page)
    headers = ["市场", "代表案例", "交易/交收", "新手重点"]
    rows = [
        ["A股", "贵州茅台 / 宁德时代 / 工商银行", "常见 T+1；主板、科创板、创业板规则不同", "先确认板块、涨跌幅、交易单位"],
        ["港股", "腾讯控股 / 阿里巴巴-W / 汇丰控股", "通常 T+2；一手股数不统一", "无普通涨跌停，注意港币、价差和流动性"],
        ["美股", "Apple / NVIDIA / Tesla", "多数证券 T+1；核心时段美东 9:30-16:00", "可 1 股起，盘前盘后价差和波动更大"],
    ]
    tbl = slide.shapes.add_table(4, 4, Inches(0.72), Inches(1.35), Inches(11.9), Inches(4.85)).table
    widths = [1.15, 3.25, 3.7, 3.8]
    for i, w in enumerate(widths):
        tbl.columns[i].width = Inches(w)
    for c, h in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.text = h
        fill(cell, BG2)
        for p in cell.text_frame.paragraphs:
            p.font.name = FONT; p.font.size = Pt(13); p.font.bold = True; p.font.color.rgb = WHITE
            p.alignment = PP_ALIGN.CENTER
    for r, row in enumerate(rows, 1):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.text = val
            fill(cell, WHITE if r % 2 else RGBColor(238, 244, 249))
            for p in cell.text_frame.paragraphs:
                p.font.name = FONT; p.font.size = Pt(12); p.font.color.rgb = TEXT
                p.alignment = PP_ALIGN.CENTER if c == 0 else PP_ALIGN.LEFT
    tx(slide, 0.95, 6.42, 11.4, 0.28, "讲法：先用规则解释“能不能买卖”，再用图表解释“价格正在发生什么”。", 14, RGBColor(203, 216, 227), True, PP_ALIGN.CENTER)


def stock_universe(charts, data, page):
    slide = slide_base("案例股票池：九只真实股票，九种教学视角", page)
    for i, st in enumerate(STOCKS):
        row, col = divmod(i, 3)
        x, y = 0.62 + col * 4.18, 1.16 + row * 1.8
        card(slide, x, y, 3.82, 1.48, WHITE)
        band = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, Inches(x), Inches(y), Inches(0.14), Inches(1.48))
        fill(band, st["color"]); no_line(band)
        df = data[st["code"]]
        tx(slide, x + 0.25, y + 0.17, 2.0, 0.24, st["name"], 14.5, TEXT, True)
        tx(slide, x + 2.25, y + 0.19, 1.1, 0.18, st["code"], 8.5, MUTED, False, PP_ALIGN.RIGHT)
        tx(slide, x + 0.25, y + 0.50, 1.8, 0.22, f"{st['market']} · {st['type']}", 9.5, st["color"], True)
        change = pct_change(df)
        colr = RED if change >= 0 else GREEN
        tx(slide, x + 0.25, y + 0.83, 1.35, 0.24, f"近约1年 {change:+.1f}%", 12.5, colr, True)
        tx(slide, x + 0.25, y + 1.13, 1.35, 0.18, f"最新收盘 {last_price(df):.2f}", 8.8, MUTED)
        slide.shapes.add_picture(str(charts[st["code"]]), Inches(x + 1.68), Inches(y + 0.63), width=Inches(1.95), height=Inches(0.68))


def market_cases(title, cases, charts, data, page):
    slide = slide_base(title, page)
    for i, st in enumerate(cases):
        x = 0.55 + i * 4.25
        card(slide, x, 1.18, 4.0, 5.65, WHITE)
        tx(slide, x + 0.22, 1.42, 2.0, 0.32, st["name"], 18, TEXT, True)
        tx(slide, x + 2.55, 1.47, 1.05, 0.2, st["code"], 9.5, MUTED, False, PP_ALIGN.RIGHT)
        slide.shapes.add_picture(str(charts[st["code"]]), Inches(x + 0.20), Inches(1.92), width=Inches(3.6), height=Inches(2.55))
        df = data[st["code"]]
        bullets(slide, x + 0.38, 4.78, 3.25, 1.0, [
            f"{st['type']}样本",
            f"近约1年涨跌幅 {pct_change(df):+.1f}%",
            "用来练趋势、均线和风险问题",
        ], 11.8)


def kline_one_page(charts, page):
    slide = slide_base("K线一页讲清：先读四个价格，再看位置", page)
    card(slide, 0.62, 1.18, 7.0, 5.55, WHITE)
    slide.shapes.add_picture(str(charts["600519.SH"]), Inches(0.88), Inches(1.55), width=Inches(6.45), height=Inches(3.85))
    tx(slide, 0.92, 5.58, 6.35, 0.45, "真实行情图：贵州茅台 600519.SH，日K + MA5/20/60", 12.5, MUTED, False, PP_ALIGN.CENTER)
    card(slide, 7.95, 1.18, 4.72, 5.55, RGBColor(238, 245, 250))
    tx(slide, 8.32, 1.55, 3.8, 0.34, "只讲这三件事", 22, TEXT, True, PP_ALIGN.CENTER)
    bullets(slide, 8.35, 2.25, 3.75, 2.55, [
        "一根K线 = 开盘、收盘、最高、最低",
        "阳线/阴线只说明当日强弱，不等于未来方向",
        "形态必须放在趋势、位置、成交量里解释",
    ], 17)
    tx(slide, 8.28, 5.55, 3.95, 0.52, "讲K线不要背形态大全，直接拿真实图问：价格在哪？量有没有配合？错了怎么退出？", 13, TEXT, True, PP_ALIGN.CENTER)


def two_chart_compare(title, left, right, charts, data, page, message):
    slide = slide_base(title, page)
    for i, st in enumerate([left, right]):
        x = 0.72 + i * 6.1
        card(slide, x, 1.22, 5.55, 5.35, WHITE)
        tx(slide, x + 0.24, 1.45, 2.5, 0.3, f"{st['name']} {st['code']}", 17, TEXT, True)
        tx(slide, x + 3.15, 1.50, 1.95, 0.2, f"{st['market']} · {st['type']}", 9.5, st["color"], True, PP_ALIGN.RIGHT)
        slide.shapes.add_picture(str(charts[st["code"]]), Inches(x + 0.22), Inches(1.90), width=Inches(5.1), height=Inches(3.25))
        tx(slide, x + 0.35, 5.50, 4.8, 0.34, f"近约1年涨跌幅 {pct_change(data[st['code']]):+.1f}%", 14, RED if pct_change(data[st["code"]]) >= 0 else GREEN, True, PP_ALIGN.CENTER)
    tx(slide, 1.45, 6.75, 10.5, 0.25, message, 12.5, RGBColor(203, 216, 227), True, PP_ALIGN.CENTER)


def simple_visual_page(title, image_code, charts, points, page):
    slide = slide_base(title, page)
    card(slide, 0.62, 1.18, 7.25, 5.55, WHITE)
    slide.shapes.add_picture(str(charts[image_code]), Inches(0.92), Inches(1.58), width=Inches(6.65), height=Inches(4.35))
    card(slide, 8.15, 1.18, 4.45, 5.55, RGBColor(238, 245, 250))
    bullets(slide, 8.45, 1.70, 3.75, 3.5, points, 18)


def flow_page(page):
    slide = slide_base("交易计划：一张流程图够新手先用", page)
    steps = [("规则", "能不能买卖"), ("位置", "趋势/均线/支撑"), ("风险", "止损与仓位"), ("执行", "按计划下单"), ("复盘", "记录错误")]
    for i, (a, b) in enumerate(steps):
        x = 0.75 + i * 2.45
        box = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, Inches(x), Inches(2.45), Inches(1.95), Inches(1.15))
        box.adjustments[0] = 0.1
        fill(box, [BLUE, CYAN, GOLD, RED, GREEN][i]); no_line(box)
        tx(slide, x + 0.18, 2.66, 1.55, 0.28, a, 18, WHITE, True, PP_ALIGN.CENTER)
        tx(slide, x + 0.18, 3.08, 1.55, 0.18, b, 9.5, WHITE, False, PP_ALIGN.CENTER)
        if i < len(steps) - 1:
            ar = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RIGHT_ARROW, Inches(x + 2.02), Inches(2.83), Inches(0.32), Inches(0.34))
            fill(ar, RGBColor(166, 183, 197)); no_line(ar)
    tx(slide, 1.15, 5.15, 10.9, 0.6, "每次买入前，只回答三个问题：为什么买？错了在哪里止损？赚了怎么卖？", 24, WHITE, True, PP_ALIGN.CENTER)


def checklist_page(page):
    slide = slide_base("复盘表：把每次交易变成下一次的素材", page)
    headers = ["项目", "记录什么", "关键问题"]
    rows = [
        ["买入理由", "规则、趋势、位置、量能", "是不是有明确依据？"],
        ["风险设定", "仓位、止损、最大亏损", "错了是否可承受？"],
        ["卖出理由", "止盈/止损/条件变化", "是按计划还是情绪？"],
        ["结果归因", "市场、行业、个股、执行", "赚亏来自能力还是运气？"],
        ["下次改进", "保留、删除、调整", "下一笔具体改变什么？"],
    ]
    tbl = slide.shapes.add_table(6, 3, Inches(0.85), Inches(1.35), Inches(11.65), Inches(4.8)).table
    for i, w in enumerate([1.6, 4.6, 5.45]):
        tbl.columns[i].width = Inches(w)
    for c, h in enumerate(headers):
        cell = tbl.cell(0, c); cell.text = h; fill(cell, BG2)
        for p in cell.text_frame.paragraphs:
            p.font.name = FONT; p.font.size = Pt(13); p.font.bold = True; p.font.color.rgb = WHITE; p.alignment = PP_ALIGN.CENTER
    for r, row in enumerate(rows, 1):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c); cell.text = val; fill(cell, WHITE if r % 2 else RGBColor(238, 245, 250))
            for p in cell.text_frame.paragraphs:
                p.font.name = FONT; p.font.size = Pt(12.5); p.font.color.rgb = TEXT; p.alignment = PP_ALIGN.CENTER if c == 0 else PP_ALIGN.LEFT


def summary_page(page):
    slide = slide_base("最后：真实图表不是答案，只是证据", page)
    card(slide, 1.05, 1.45, 11.2, 4.9, RGBColor(238, 245, 250))
    bullets(slide, 1.75, 2.05, 9.9, 2.9, [
        "规则决定你能怎么交易：A股、港股、美股先分清制度差异",
        "K线和均线帮助观察市场，但不负责保证收益",
        "真实股票案例只用于训练判断，不构成投资建议",
        "新手最重要的不是预测，而是控制仓位、止损和复盘",
    ], 20)


def build_deck(data, charts):
    page = 1
    cover(charts, page); page += 1
    rules_table(page); page += 1
    stock_universe(charts, data, page); page += 1
    market_cases("A股案例：同一个市场里，股票性格差异很大", STOCKS[0:3], charts, data, page); page += 1
    market_cases("港股案例：真实K线 + 港币/流动性/一手股数", STOCKS[3:6], charts, data, page); page += 1
    market_cases("美股案例：真实K线 + 1股起 + 高波动", STOCKS[6:9], charts, data, page); page += 1
    kline_one_page(charts, page); page += 1
    simple_visual_page("均线：用 NVIDIA 这类趋势股讲更直观", "NVDA", charts, [
        "MA5：短期节奏，反应快但噪声大",
        "MA20：常用中短期趋势参考",
        "MA60：观察阶段趋势和成本区",
    ], page); page += 1
    simple_visual_page("成交量：用宁德时代看放量和波动", "300750.SZ", charts, [
        "放量说明参与度提高，不等于一定上涨",
        "突破、跌破、冲高回落都要配合量来看",
        "成交量最好回答：这次价格变化有没有资金参与？",
    ], page); page += 1
    two_chart_compare("低波动 vs 高波动：同样一手仓位，心理压力不同", STOCKS[2], STOCKS[8], charts, data, page,
                      "工商银行更适合讲防守属性；Tesla 更适合讲波动、仓位和止损。"); page += 1
    two_chart_compare("消费龙头 vs AI成长：趋势、估值和情绪不是一回事", STOCKS[0], STOCKS[7], charts, data, page,
                      "不要把“好公司”“热门赛道”和“现在适合买”混为一谈。"); page += 1
    simple_visual_page("A股规则页：用案例解释 T+1 和涨跌幅", "600519.SH", charts, [
        "今天买入的A股股票，通常不能当天卖出",
        "不同板块涨跌幅和新股规则不同",
        "下单前先确认代码所属市场和板块",
    ], page); page += 1
    simple_visual_page("港股规则页：无普通涨跌停，不等于风险更小", "00700.HK", charts, [
        "港股通常 T+2 交收",
        "一手股数不统一，交易前必须看清数量",
        "无普通日涨跌停，价差和流动性更重要",
    ], page); page += 1
    simple_visual_page("美股规则页：盘前盘后更自由，也更容易滑点", "AAPL", charts, [
        "核心交易时段通常为美东 9:30-16:00",
        "多数证券已进入 T+1 结算周期",
        "盘前盘后成交少时，市价单风险更高",
    ], page); page += 1
    simple_visual_page("MACD/RSI/KDJ/布林线：一页定位就够", "TSLA", charts, [
        "MACD：看趋势动能，不是买卖命令",
        "RSI/KDJ：看短期强弱，假信号很多",
        "布林线：看波动区间，不能机械碰线买卖",
    ], page); page += 1
    flow_page(page); page += 1
    simple_visual_page("风控：先决定亏多少，再决定买多少", "00005.HK", charts, [
        "单笔亏损上限先写出来",
        "不要因为亏损而无计划加仓",
        "现金也是仓位，等待也是选择",
    ], page); page += 1
    simple_visual_page("止盈止损：退出规则要在买入前写好", "09988.HK", charts, [
        "止损：价格、技术位、资金比例、时间",
        "止盈：分批、移动止盈、趋势破坏",
        "没有退出计划，短线容易变成长线被动持有",
    ], page); page += 1
    checklist_page(page); page += 1
    simple_visual_page("新手最常见错误：看对图，也可能做错交易", "300750.SZ", charts, [
        "追涨杀跌：买在兴奋点，卖在恐慌点",
        "只看形态：忽视规则、公告、财报和费用",
        "不复盘：同一个错误反复出现",
    ], page); page += 1
    summary_page(page); page += 1
    prs.save(OUT)


def main():
    data = fetch_all()
    charts = {}
    for st in STOCKS:
        charts[st["code"]] = render_chart(st, data[st["code"]], wide=False)
    build_deck(data, charts)
    print(OUT)
    print(json.dumps({code: {"rows": len(df), "from": str(df.index.min().date()), "to": str(df.index.max().date())} for code, df in data.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

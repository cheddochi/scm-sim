"""Plotly 차트. 제목(주장형 결론)과 부제(단위·기준·시나리오·출처)를 그림 안에 넣어 PNG로 바로 슬라이드에 쓴다."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from ui import NAVY, BLUE, SLATE, GREY, LINE, ORANGE, RED, AMBER, GREEN, FONT

PLOT_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}

# 화면 폭 등급별 제목 최대 글자 수(13px 굵게, 한글 기준)와 PNG 저장 폭(px).
# 저장 폭을 고정해 화면 크기와 무관하게 슬라이드용 이미지 규격이 같도록 한다 (scale 2 → 실제 2배 픽셀).
SIZES = {"full": (64, 1400), "half": (36, 900), "narrow": (22, 560)}


def wrap(text: str, maxc: int) -> str:
    """maxc를 넘으면 가운데에 가까운 구분자(—, 쉼표, ·, 콜론, 공백)에서 두 줄로 나눈다."""
    if len(text) <= maxc:
        return text
    mid = len(text) / 2
    best = None
    for sep in (" | ", " — ", ", ", " · ", ": ", " "):
        i = text.find(sep)
        while i != -1:
            # " | "·공백은 구분자 앞에서 자르고 구분자를 버린다. 나머지는 구분자를 앞줄 끝에 남긴다.
            cut = i if sep in (" | ", " ") else i + len(sep.rstrip())
            if best is None or abs(cut - mid) < abs(best[0] - mid) - 3:
                best = (cut, sep)
            i = text.find(sep, i + 1)
        if best and abs(best[0] - mid) < len(text) * 0.25:
            break
    if best is None:
        return text
    cut, sep = best
    return text[:cut].rstrip() + "<br>" + text[cut:].lstrip(" ,|").lstrip()


def show(fig: go.Figure, name: str, size: str = "half"):
    """제목·부제를 폭 등급에 맞춰 줄바꿈하고, PNG 저장 규격을 고정해 그린다."""
    import streamlit as st
    maxc, width = SIZES[size]
    meta = fig.layout.meta or {}
    t = wrap(meta.get("title", ""), maxc)
    sub = wrap(meta.get("subtitle", ""), int(maxc * 1.45))
    lines = t.count("<br>") + sub.count("<br>") + 2
    fig.update_layout(
        title=dict(text=f"<b>{t}</b><br><span style='font-size:10.5px;color:{SLATE}'>{sub}</span>"),
        margin=dict(t=28 + 17 * lines), height=fig.layout.height + 17 * (lines - 2))
    cfg = dict(PLOT_CONFIG, toImageButtonOptions={"format": "png", "filename": name, "scale": 2,
                                                  "width": width, "height": fig.layout.height})
    st.plotly_chart(fig, use_container_width=True, config=cfg)


def base(fig: go.Figure, title: str, subtitle: str, height: int = 320, legend: bool = True) -> go.Figure:
    fig.update_layout(
        meta={"title": title, "subtitle": subtitle},
        title=dict(text=f"<b>{title}</b><br><span style='font-size:10.5px;color:{SLATE}'>{subtitle}</span>",
                   x=0.01, xanchor="left", y=1, yref="container", yanchor="top", pad=dict(t=10),
                   font=dict(size=13, color=NAVY)),
        font=dict(family=FONT, size=11, color=NAVY), paper_bgcolor="#FFFFFF", plot_bgcolor="#FFFFFF",
        height=height, margin=dict(l=48, r=12, t=58, b=34), showlegend=legend,
        legend=dict(orientation="h", y=-0.14, x=0, font=dict(size=10.5), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(font=dict(family=FONT, size=11)),
    )
    fig.update_xaxes(gridcolor=LINE, linecolor=LINE, zeroline=False, ticks="outside", tickcolor=LINE)
    fig.update_yaxes(gridcolor=LINE, linecolor=LINE, zeroline=False)
    return fig


def spaghetti(years, sample, p10, p50, p90, lines: dict, cap: float, title, subtitle):
    fig = go.Figure()
    for path in sample:
        fig.add_trace(go.Scatter(x=years, y=path, mode="lines", line=dict(color="rgba(148,163,184,0.28)", width=0.7),
                                 hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=years, y=p90, mode="lines", line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=years, y=p10, mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor="rgba(148,163,184,0.25)", name="몬테카를로 10~90%"))
    fig.add_trace(go.Scatter(x=years, y=p50, mode="lines", line=dict(color=SLATE, width=1.5, dash="dot"), name="MC 중앙값"))
    for name, (y, hl) in lines.items():
        fig.add_trace(go.Scatter(x=years, y=y, mode="lines", name=name,
                                 line=dict(color=ORANGE if hl else BLUE, width=2.6 if hl else 1.6)))
    if cap:
        fig.add_hline(y=cap, line=dict(color=NAVY, dash="dash", width=1),
                      annotation_text=f"브로츠와프 공급 가능 {cap:.0f}GWh", annotation_font_size=10)
    fig.update_yaxes(title_text="GWh")
    return base(fig, title, subtitle, height=360)


def distribution(values, lines: dict, title, subtitle):
    fig = go.Figure(go.Histogram(x=values, nbinsx=40, marker_color=GREY, marker_line_width=0, name="경로 분포"))
    for i, (label, (x, color)) in enumerate(lines.items()):
        fig.add_vline(x=x, line=dict(color=color, width=1.6, dash="dash"))
        fig.add_annotation(x=x, y=1 - 0.09 * i, yref="paper", text=label, showarrow=False, xanchor="left",
                           font=dict(size=10, color=color), bgcolor="rgba(255,255,255,0.8)")
    fig.update_xaxes(title_text="유럽 공략 가능 물량 (GWh)")
    fig.update_yaxes(title_text="경로 수")
    return base(fig, title, subtitle, height=360, legend=False)


def util_heatmap(util: pd.DataFrame, shadow: pd.DataFrame, title, subtitle):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.55, 0.45], vertical_spacing=0.06,
                        subplot_titles=("가동률 (%)", "생산능력 잠재가격 ($/kWh)"))
    fig.add_trace(go.Heatmap(z=util.values * 100, x=util.columns, y=util.index, zmin=0, zmax=100,
                             colorscale=[[0, "#FFFFFF"], [0.6, "#BFDBFE"], [1, BLUE]], showscale=False,
                             text=np.vectorize(lambda v: f"{v:.0f}")(util.values * 100), texttemplate="%{text}",
                             textfont=dict(size=9), hovertemplate="%{y} %{x}: %{z:.1f}%<extra></extra>"), 1, 1)
    fig.add_trace(go.Heatmap(z=shadow.values, x=shadow.columns, y=shadow.index,
                             colorscale=[[0, "#FFFFFF"], [1, SLATE]], showscale=False,
                             text=np.vectorize(lambda v: f"{v:.1f}")(shadow.values), texttemplate="%{text}",
                             textfont=dict(size=9), hovertemplate="%{y} %{x}: $%{z:.2f}/kWh<extra></extra>"), 2, 1)
    fig.update_annotations(font_size=10.5, font_color=SLATE)
    fig.update_xaxes(dtick=2, showgrid=False)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    return base(fig, title, subtitle, height=380, legend=False)


def stacked_share(share: pd.DataFrame, colors: dict, title, subtitle):
    """share: 고객 × 공장 (비중 0~1)."""
    fig = go.Figure()
    for f in share.columns:
        fig.add_trace(go.Bar(y=share.index, x=share[f] * 100, name=f, orientation="h", marker_color=colors.get(f, GREY),
                             hovertemplate=f"{f} %{{x:.0f}}%<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.25)
    fig.update_xaxes(title_text="공급 비중 (%)", range=[0, 100])
    fig.update_yaxes(autorange="reversed", tickfont=dict(size=10))
    return base(fig, title, subtitle, height=380)


def cost_breakdown(df: pd.DataFrame, items: dict, hl: str | None, title, subtitle):
    """df: 공장 × 원가항목 ($/kWh)."""
    palette = [NAVY, BLUE, "#3B82F6", SLATE, GREY, "#CBD5E1", AMBER, RED, "#F59E0B"]
    fig = go.Figure()
    for i, (c, label) in enumerate(items.items()):
        if c in df and df[c].abs().sum() > 0:
            fig.add_trace(go.Bar(y=df.index, x=df[c], name=label, orientation="h", marker_color=palette[i % len(palette)],
                                 hovertemplate=f"{label} %{{x:.2f}}<extra></extra>"))
    tot = df[[c for c in items if c in df]].sum(axis=1)
    for f, v in tot.items():
        fig.add_annotation(x=v, y=f, text=f"{v:.2f}", showarrow=False, xanchor="left", xshift=3,
                           font=dict(size=10.5, color=ORANGE if f == hl else NAVY))
    fig.update_layout(barmode="stack", bargap=0.3)
    fig.update_xaxes(title_text="$/kWh")
    fig.update_yaxes(autorange="reversed")
    return base(fig, title, subtitle, height=340)


def timing_bars(summary: pd.DataFrame, best: str, title, subtitle):
    fig = go.Figure()
    fig.add_trace(go.Bar(y=summary.index, x=summary["expected_npv"], orientation="h", name="기대 증분 NPV",
                         marker_color=[ORANGE if i == best else BLUE for i in summary.index],
                         text=[f"{v:,.0f}" for v in summary["expected_npv"]], textposition="outside"))
    fig.add_trace(go.Bar(y=summary.index, x=summary["worst_npv"], orientation="h", name="최악 시나리오 NPV",
                         marker_color=GREY, text=[f"{v:,.0f}" for v in summary["worst_npv"]], textposition="outside"))
    fig.update_layout(barmode="group", bargap=0.3)
    fig.update_xaxes(title_text="$M", zeroline=True, zerolinecolor=SLATE)
    fig.update_yaxes(autorange="reversed")
    return base(fig, title, subtitle, height=260)


def scenario_heatmap(m: pd.DataFrame, hl_row: str | None, hl_col: str | None, title, subtitle,
                     cost_cols: tuple = ("최대후회",)):
    """NPV는 양수=파랑·음수=빨강. cost_cols(후회처럼 클수록 나쁜 값)는 부호를 뒤집어 칠한다."""
    z = m.values.astype(float).copy()
    for c in cost_cols:
        if c in m.columns:
            z[:, list(m.columns).index(c)] *= -1
    lim = np.nanmax(np.abs(z))
    fig = go.Figure(go.Heatmap(z=z, x=m.columns, y=m.index, zmid=0, zmin=-lim, zmax=lim, customdata=m.values,
                               colorscale=[[0, "#B91C1C"], [0.5, "#FFFFFF"], [1, BLUE]], showscale=False,
                               text=np.vectorize(lambda v: f"{v:,.0f}".replace("-", "−"))(m.values.astype(float)),
                               texttemplate="%{text}", textfont=dict(size=10.5),
                               hovertemplate="%{y} · %{x}: %{customdata:,.0f}<extra></extra>"))
    if hl_row is not None and hl_row in m.index:
        i = list(m.index).index(hl_row)
        fig.add_shape(type="rect", x0=-0.5, x1=len(m.columns) - 0.5, y0=i - 0.5, y1=i + 0.5,
                      line=dict(color=ORANGE, width=2))
    if hl_col is not None and hl_col in m.columns:
        j = list(m.columns).index(hl_col)
        fig.add_shape(type="rect", x0=j - 0.5, x1=j + 0.5, y0=-0.5, y1=len(m.index) - 0.5,
                      line=dict(color=NAVY, width=1.5))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(side="top", showgrid=False)
    return base(fig, title, subtitle, height=330, legend=False)


def tornado(t: pd.DataFrame, title, subtitle):
    t = t.iloc[::-1]
    mid = float(t["base"].iloc[0])
    fig = go.Figure()
    fig.add_trace(go.Bar(y=t["variable"], x=t["low"] - mid, base=mid, orientation="h", name="낮은 값",
                         marker_color=GREY, text=[f"{l}" for l in t["low_label"]], textposition="inside"))
    fig.add_trace(go.Bar(y=t["variable"], x=t["high"] - mid, base=mid, orientation="h", name="높은 값",
                         marker_color=BLUE, text=[f"{h}" for h in t["high_label"]], textposition="inside"))
    top = t.iloc[-1]
    fig.add_trace(go.Bar(y=[top["variable"]], x=[top["high"] - mid], base=mid, orientation="h", showlegend=False,
                         marker_color=ORANGE, hoverinfo="skip"))
    fig.add_vline(x=mid, line=dict(color=NAVY, width=1))
    fig.add_vline(x=0, line=dict(color=RED, width=1, dash="dot"))
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_xaxes(title_text="증분 NPV ($M)")
    return base(fig, title, subtitle, height=280)


def switchpoint(curve: pd.DataFrame, labels: dict, hl: str, x_switch: float | None, title, subtitle):
    fig = go.Figure()
    for f in curve.columns:
        fig.add_trace(go.Scatter(x=curve.index, y=curve[f], mode="lines+markers", name=labels.get(f, f),
                                 line=dict(color=ORANGE if f == hl else GREY, width=2.6 if f == hl else 1.1),
                                 marker=dict(size=4 if f == hl else 3)))
    fig.add_hline(y=0, line=dict(color=NAVY, width=1))
    if x_switch is not None:
        fig.add_vline(x=x_switch, line=dict(color=ORANGE, width=1.5, dash="dash"),
                      annotation_text=f"전환점 ×{x_switch:.2f}", annotation_font=dict(size=10.5, color=ORANGE))
    fig.update_xaxes(title_text="수요 성장률 승수 (기준 = 1.0)")
    fig.update_yaxes(title_text="증분 NPV ($M)")
    return base(fig, title, subtitle, height=330)


def pareto(t: pd.DataFrame, labels: dict, hl: str, title, subtitle):
    fig = go.Figure()
    front = t[t["pareto"]].sort_values("carbon_margin")
    fig.add_trace(go.Scatter(x=front["carbon_margin"], y=front["expected_npv"], mode="lines",
                             line=dict(color=SLATE, dash="dot", width=1), name="파레토 경계"))
    for f, r in t.iterrows():
        fig.add_trace(go.Scatter(x=[r["carbon_margin"]], y=[r["expected_npv"]], mode="markers+text",
                                 marker=dict(size=7 + 30 * (1 - r["max_site_share"]),
                                             color=ORANGE if f == hl else (BLUE if r["pareto"] else GREY)),
                                 text=[labels.get(f, f)], textposition="top center", textfont=dict(size=10),
                                 showlegend=False,
                                 hovertemplate=f"{labels.get(f, f)}<br>기대 NPV %{{y:,.0f}}<br>탄소 마진 %{{x:.1f}}kg"
                                               f"<br>유럽 리드타임 {r['eu_lead_time']:.1f}일<extra></extra>"))
    fig.add_vline(x=0, line=dict(color=RED, width=1, dash="dot"))
    fig.add_hline(y=0, line=dict(color=NAVY, width=1))
    fig.update_xaxes(title_text="2035 위치기반 60kg 상한 대비 안전마진 (kg/kWh)")
    fig.update_yaxes(title_text="기대 증분 NPV ($M)")
    return base(fig, title, subtitle, height=330)


def loss_hist(loss: np.ndarray, title, subtitle):
    p50, p90, p99 = np.percentile(loss, [50, 90, 99])
    fig = go.Figure(go.Histogram(x=loss, nbinsx=40, marker_color=GREY, marker_line_width=0))
    for v, label, c in ((p50, "중앙값", NAVY), (p90, "90%", ORANGE), (p99, "99%", RED)):
        fig.add_vline(x=v, line=dict(color=c, dash="dash", width=1.3),
                      annotation_text=f"{label} {v:,.0f}", annotation_font=dict(size=10, color=c))
    fig.update_xaxes(title_text="20년 EBITDA 손실 현가 ($M)")
    fig.update_yaxes(title_text="시뮬레이션 수")
    return base(fig, title, subtitle, height=330, legend=False)

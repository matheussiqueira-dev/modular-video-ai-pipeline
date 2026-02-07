from __future__ import annotations

from typing import Dict, List, Sequence, Tuple

import pandas as pd
import streamlit as st


def render_hero(title: str, subtitle: str, tags: Sequence[str]) -> None:
    badges = "".join([f"<span class='badge'>{tag}</span>" for tag in tags])
    st.markdown(
        f"""
        <div class='hero-shell ui-fade-in'>
          <h1 style='margin:0;font-size:2rem;'>{title}</h1>
          <p class='muted' style='margin:8px 0 12px 0;'>{subtitle}</p>
          <div>{badges}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(metrics: Sequence[Tuple[str, str]]) -> None:
    cards = []
    for label, value in metrics:
        cards.append(
            f"""
            <div class='metric-card'>
              <div class='metric-label'>{label}</div>
              <div class='metric-value'>{value}</div>
            </div>
            """
        )

    st.markdown(
        f"""
        <div class='panel-shell ui-fade-in'>
          <div class='metric-grid'>
            {''.join(cards)}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_zone_preview(zones: List[dict]) -> None:
    if not zones:
        st.info("Nenhuma zona configurada. Eventos de entrada/saida por zona serao desativados.")
        return

    rows = [
        {
            "Zona": zone["name"],
            "x1": zone["x1"],
            "y1": zone["y1"],
            "x2": zone["x2"],
            "y2": zone["y2"],
        }
        for zone in zones
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_run_history(history: List[Dict]) -> None:
    if not history:
        st.info("Sem historico de execucoes nesta sessao.")
        return

    rows = [
        {
            "timestamp": item.get("timestamp", ""),
            "preset": item.get("preset", "Custom"),
            "frames": item.get("frames", 0),
            "events": item.get("events", 0),
            "avg_fps": item.get("avg_fps", 0.0),
        }
        for item in history
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_comparison_summary(comparison: Dict) -> None:
    if not comparison.get("current"):
        return

    current = comparison["current"]
    if not comparison.get("has_previous"):
        render_metric_cards(
            [
                ("Frames (Atual)", str(current.get("frames_processed", 0))),
                ("Eventos (Atual)", str(current.get("events_detected", 0))),
                ("FPS (Atual)", f"{float(current.get('average_processing_fps', 0.0)):.2f}"),
            ]
        )
        st.caption("Sem execucao anterior para comparacao.")
        return

    delta = comparison.get("delta", {})

    def _fmt_delta(value: float, digits: int = 0) -> str:
        sign = "+" if value > 0 else ""
        if digits == 0:
            return f"{sign}{int(value)}"
        return f"{sign}{value:.{digits}f}"

    render_metric_cards(
        [
            (
                "Frames",
                f"{current.get('frames_processed', 0)} ({_fmt_delta(float(delta.get('frames_processed', 0)))})",
            ),
            (
                "Eventos",
                f"{current.get('events_detected', 0)} ({_fmt_delta(float(delta.get('events_detected', 0)))})",
            ),
            (
                "FPS Medio",
                f"{float(current.get('average_processing_fps', 0.0)):.2f} ({_fmt_delta(float(delta.get('average_processing_fps', 0.0)), digits=2)})",
            ),
        ]
    )


def build_severity_distribution_chart(events_df: pd.DataFrame):
    if events_df.empty:
        return None

    try:
        import plotly.express as px
    except ModuleNotFoundError:
        return None

    counts = events_df["severity"].fillna("info").value_counts().reset_index()
    counts.columns = ["severity", "count"]

    fig = px.pie(
        counts,
        names="severity",
        values="count",
        title="Distribuicao por Severidade",
        color="severity",
        color_discrete_map={"info": "#4dc7ff", "warning": "#ffb347", "critical": "#f26f6f"},
        hole=0.52,
    )
    fig.update_layout(
        template="plotly_dark",
        height=340,
        margin=dict(l=24, r=24, t=42, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16, 40, 60, 0.32)",
        legend_title_text="Severidade",
    )
    return fig


def build_event_timeline_chart(events_df: pd.DataFrame):
    if events_df.empty:
        return None

    try:
        import plotly.express as px
    except ModuleNotFoundError:
        return None

    fig = px.scatter(
        events_df,
        x="frame",
        y="object_id",
        color="severity",
        symbol="type",
        hover_data=["details"],
        color_discrete_map={"info": "#4dc7ff", "warning": "#ffb347", "critical": "#f26f6f"},
        title="Timeline de Eventos",
    )
    fig.update_layout(
        template="plotly_dark",
        height=340,
        legend_title_text="Severidade",
        margin=dict(l=24, r=24, t=42, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16, 40, 60, 0.32)",
    )
    fig.update_xaxes(title_text="Frame")
    fig.update_yaxes(title_text="Object ID")
    return fig


def build_frame_performance_chart(frames_df: pd.DataFrame):
    if frames_df.empty:
        return None

    try:
        import plotly.express as px
    except ModuleNotFoundError:
        return None

    melted = frames_df.melt(
        id_vars=["frame"],
        value_vars=["processing_fps", "active_tracks", "events_in_frame"],
        var_name="metric",
        value_name="value",
    )

    metric_names = {
        "processing_fps": "FPS",
        "active_tracks": "Tracks Ativos",
        "events_in_frame": "Eventos no Frame",
    }
    melted["metric"] = melted["metric"].map(metric_names).fillna(melted["metric"])

    fig = px.line(
        melted,
        x="frame",
        y="value",
        color="metric",
        title="Performance por Frame",
        color_discrete_map={
            "FPS": "#4dc7ff",
            "Tracks Ativos": "#48c78e",
            "Eventos no Frame": "#ffb347",
        },
    )
    fig.update_layout(
        template="plotly_dark",
        height=340,
        margin=dict(l=24, r=24, t=42, b=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(16, 40, 60, 0.32)",
        legend_title_text="Metrica",
    )
    fig.update_xaxes(title_text="Frame")
    fig.update_yaxes(title_text="Valor")
    return fig

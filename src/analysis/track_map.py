"""Track map visualizations using FastF1 telemetry position data."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from src.pipeline.session_loader import get_telemetry, get_fastest_lap

CHANNEL_LABELS = {
    "Speed": "Speed (km/h)",
    "Throttle": "Throttle (%)",
    "nGear": "Gear",
    "Brake": "Braking",
}

CHANNEL_COLORMAPS = {
    "Speed": "RdYlGn",
    "Throttle": "RdYlGn",
    "nGear": "Viridis",
    "Brake": "RdYlGn_r",
}


def _resample_to_points(tel: pd.DataFrame, n: int = 1000) -> pd.DataFrame:
    """Resample telemetry to n evenly spaced distance points."""
    dist = np.linspace(tel["Distance"].min(), tel["Distance"].max(), n)
    out = {}
    for col in ["X", "Y", "Speed", "Throttle", "nGear", "Brake"]:
        if col in tel.columns:
            out[col] = np.interp(dist, tel["Distance"].values, tel[col].values)
    out["Distance"] = dist
    return pd.DataFrame(out)


def build_track_figure(lap, color_channel: str = "Speed") -> go.Figure:
    """
    Draw the track colored by a telemetry channel.
    color_channel: 'Speed', 'Throttle', 'nGear', 'Brake'
    """
    try:
        tel = get_telemetry(lap)
    except Exception:
        tel = lap.get_telemetry().add_distance()

    if "X" not in tel.columns or "Y" not in tel.columns:
        fig = go.Figure()
        fig.add_annotation(text="Position data not available", showarrow=False)
        return fig

    df = _resample_to_points(tel)
    if color_channel not in df.columns:
        color_channel = "Speed"

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["X"], y=df["Y"],
        mode="markers",
        marker=dict(
            color=df[color_channel],
            colorscale=CHANNEL_COLORMAPS.get(color_channel, "RdYlGn"),
            size=4,
            colorbar=dict(title=CHANNEL_LABELS.get(color_channel, color_channel)),
            showscale=True,
        ),
        hovertemplate=(
            f"{color_channel}: " + "%{marker.color:.1f}<br>"
            "X: %{x:.0f}, Y: %{y:.0f}<extra></extra>"
        ),
    ))

    fig.update_layout(
        plot_bgcolor="#0F0F0F",
        paper_bgcolor="#0F0F0F",
        font_color="#FFFFFF",
        xaxis=dict(visible=False, scaleanchor="y"),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0),
        height=400,
    )
    return fig


def build_delta_map(lap_a, lap_b, label_a: str = "A", label_b: str = "B") -> go.Figure:
    """
    Draw track colored by cumulative time delta between two drivers.
    Red = lap_a faster, Blue = lap_b faster.
    """
    try:
        tel_a = get_telemetry(lap_a)
        tel_b = get_telemetry(lap_b)
    except Exception:
        tel_a = lap_a.get_telemetry().add_distance()
        tel_b = lap_b.get_telemetry().add_distance()

    if "X" not in tel_a.columns or "X" not in tel_b.columns:
        fig = go.Figure()
        fig.add_annotation(text="Position data not available for delta map", showarrow=False)
        return fig

    # Resample both to same distance grid
    df_a = _resample_to_points(tel_a)
    df_b = _resample_to_points(tel_b)

    # Compute delta: positive = A faster, negative = B faster
    # Speed-based: delta_t ≈ Δ(1/v) × distance_step
    dist_step = np.diff(df_a["Distance"].values, prepend=0)
    speed_a = np.maximum(df_a["Speed"].values, 1)
    speed_b = np.maximum(df_b["Speed"].values, 1)
    delta = np.cumsum((1 / speed_a - 1 / speed_b) * dist_step * 3.6)  # seconds

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_a["X"], y=df_a["Y"],
        mode="markers",
        marker=dict(
            color=delta,
            colorscale="RdBu",
            size=4,
            cmid=0,
            colorbar=dict(
                title=f"Delta (s)<br>Red={label_a} faster<br>Blue={label_b} faster",
                tickformat=".2f",
            ),
            showscale=True,
        ),
        hovertemplate="Delta: %{marker.color:.3f}s<extra></extra>",
    ))

    fig.update_layout(
        plot_bgcolor="#0F0F0F",
        paper_bgcolor="#0F0F0F",
        font_color="#FFFFFF",
        xaxis=dict(visible=False, scaleanchor="y"),
        yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0),
        height=400,
        title=dict(text=f"Track Delta: {label_a} vs {label_b}", font_color="#FFFFFF"),
    )
    return fig

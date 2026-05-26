"""Track map visualizations — accepts plain DataFrames so callers can cache data separately."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go

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


def _resample(tel: pd.DataFrame, n: int = 1000) -> pd.DataFrame:
    dist = np.linspace(tel["Distance"].min(), tel["Distance"].max(), n)
    out = {"Distance": dist}
    for col in ["X", "Y", "Speed", "Throttle", "nGear", "Brake"]:
        if col in tel.columns:
            out[col] = np.interp(dist, tel["Distance"].values, tel[col].values)
    return pd.DataFrame(out)


def lap_to_telemetry(lap) -> pd.DataFrame:
    """Extract telemetry + position from a FastF1 Lap object into a plain DataFrame."""
    tel = lap.get_telemetry().add_distance()
    try:
        pos = lap.get_pos_data()
        tel = tel.merge_channels(pos)
    except Exception:
        pass
    keep = [c for c in ["X", "Y", "Speed", "Throttle", "nGear", "Brake", "Distance"] if c in tel.columns]
    return tel[keep].reset_index(drop=True)


def build_track_figure(tel: pd.DataFrame, color_channel: str = "Speed") -> go.Figure:
    """Draw track colored by a telemetry channel. `tel` is a plain DataFrame."""
    if "X" not in tel.columns or "Y" not in tel.columns:
        fig = go.Figure()
        fig.add_annotation(text="Position data not available", showarrow=False)
        return fig

    df = _resample(tel)
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
        hovertemplate=f"{color_channel}: " + "%{marker.color:.1f}<br>X: %{x:.0f}, Y: %{y:.0f}<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="#0F0F0F", paper_bgcolor="#0F0F0F", font_color="#FFFFFF",
        xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0), height=400,
    )
    return fig


def build_delta_map(tel_a: pd.DataFrame, tel_b: pd.DataFrame,
                    label_a: str = "A", label_b: str = "B") -> go.Figure:
    """Draw track colored by cumulative time delta. Both args are plain DataFrames."""
    if "X" not in tel_a.columns or "X" not in tel_b.columns:
        fig = go.Figure()
        fig.add_annotation(text="Position data not available for delta map", showarrow=False)
        return fig

    df_a = _resample(tel_a)
    df_b = _resample(tel_b)

    dist_step = np.diff(df_a["Distance"].values, prepend=0)
    speed_a = np.maximum(df_a["Speed"].values, 1)
    speed_b = np.maximum(df_b["Speed"].values, 1)
    delta = np.cumsum((1 / speed_a - 1 / speed_b) * dist_step * 3.6)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_a["X"], y=df_a["Y"],
        mode="markers",
        marker=dict(
            color=delta, colorscale="RdBu", size=4, cmid=0,
            colorbar=dict(
                title=f"Delta (s)<br>Red={label_a} faster<br>Blue={label_b} faster",
                tickformat=".2f",
            ),
            showscale=True,
        ),
        hovertemplate="Delta: %{marker.color:.3f}s<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="#0F0F0F", paper_bgcolor="#0F0F0F", font_color="#FFFFFF",
        xaxis=dict(visible=False, scaleanchor="y"), yaxis=dict(visible=False),
        margin=dict(l=0, r=0, t=0, b=0), height=400,
        title=dict(text=f"Track Delta: {label_a} vs {label_b}", font_color="#FFFFFF"),
    )
    return fig

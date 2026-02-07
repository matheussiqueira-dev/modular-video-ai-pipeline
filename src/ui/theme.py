from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ThemeOptions:
    high_contrast: bool = False
    reduced_motion: bool = False


def build_css(options: ThemeOptions) -> str:
    if options.high_contrast:
        palette = {
            "bg_start": "#05111a",
            "bg_end": "#0d1f2d",
            "surface": "#112637",
            "surface_soft": "#17334a",
            "text_main": "#f4f9ff",
            "text_muted": "#d2e3f6",
            "accent": "#4bd2ff",
            "accent_alt": "#ffcc4d",
            "border": "#4f7898",
            "success": "#61d69d",
            "danger": "#ff6b6b",
        }
    else:
        palette = {
            "bg_start": "#081724",
            "bg_end": "#12334a",
            "surface": "#10283d",
            "surface_soft": "#183e59",
            "text_main": "#ebf4ff",
            "text_muted": "#b8d0e8",
            "accent": "#4dc7ff",
            "accent_alt": "#ffb347",
            "border": "#2f5a79",
            "success": "#48c78e",
            "danger": "#f26f6f",
        }

    animation_duration = "0.01s" if options.reduced_motion else "0.55s"
    transform_offset = "0" if options.reduced_motion else "8px"

    return f"""
    <style>
      @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap');

      :root {{
        --bg-start: {palette['bg_start']};
        --bg-end: {palette['bg_end']};
        --surface: {palette['surface']};
        --surface-soft: {palette['surface_soft']};
        --text-main: {palette['text_main']};
        --text-muted: {palette['text_muted']};
        --accent: {palette['accent']};
        --accent-alt: {palette['accent_alt']};
        --border: {palette['border']};
        --success: {palette['success']};
        --danger: {palette['danger']};
      }}

      .stApp {{
        font-family: 'Outfit', sans-serif;
        color: var(--text-main);
        background:
          radial-gradient(circle at 12% 14%, rgba(77, 199, 255, 0.22), transparent 35%),
          radial-gradient(circle at 86% 8%, rgba(255, 179, 71, 0.18), transparent 34%),
          linear-gradient(140deg, var(--bg-start), var(--bg-end));
      }}

      .block-container {{
        max-width: 1300px;
        padding-top: 1.2rem;
        padding-bottom: 2.2rem;
      }}

      h1, h2, h3, h4, p, span, label, div {{
        color: var(--text-main);
      }}

      .ui-fade-in {{
        animation: fade-slide {animation_duration} ease-out;
      }}

      @keyframes fade-slide {{
        from {{
          opacity: 0;
          transform: translateY({transform_offset});
        }}
        to {{
          opacity: 1;
          transform: translateY(0);
        }}
      }}

      .hero-shell {{
        background: linear-gradient(122deg, rgba(17, 43, 63, 0.92), rgba(22, 57, 82, 0.78));
        border: 1px solid var(--border);
        border-radius: 18px;
        padding: 20px 22px;
        box-shadow: 0 18px 42px rgba(5, 13, 22, 0.32);
        margin-bottom: 14px;
      }}

      .panel-shell {{
        background: linear-gradient(140deg, rgba(16, 40, 60, 0.82), rgba(24, 62, 89, 0.72));
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 14px;
        box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.02);
      }}

      .metric-grid {{
        display: grid;
        grid-template-columns: repeat(4, minmax(140px, 1fr));
        gap: 10px;
      }}

      .metric-card {{
        background: linear-gradient(140deg, var(--surface), var(--surface-soft));
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 10px 12px;
      }}

      .metric-label {{
        font-size: 0.78rem;
        color: var(--text-muted);
      }}

      .metric-value {{
        font-size: 1.35rem;
        font-weight: 700;
        margin-top: 3px;
      }}

      .muted {{
        color: var(--text-muted);
      }}

      .badge {{
        display: inline-block;
        padding: 4px 10px;
        border-radius: 999px;
        border: 1px solid var(--border);
        background: rgba(11, 31, 47, 0.62);
        color: var(--text-main);
        font-size: 0.75rem;
        margin-right: 6px;
      }}

      .stButton > button {{
        border-radius: 11px;
        border: 1px solid var(--accent);
        background: linear-gradient(90deg, var(--accent), #1ea6d8);
        color: #071420;
        font-weight: 700;
        letter-spacing: 0.2px;
      }}

      .stDownloadButton > button {{
        border-radius: 11px;
        border: 1px solid var(--accent-alt);
        background: linear-gradient(90deg, var(--accent-alt), #f29d38);
        color: #2b1906;
        font-weight: 700;
      }}

      .stTextInput > div > div > input,
      .stTextArea textarea,
      .stNumberInput input,
      .stSelectbox > div > div,
      .stMultiSelect > div > div,
      .stSlider [data-baseweb='slider'] {{
        color: var(--text-main);
      }}

      [data-testid='stSidebar'] {{
        background: linear-gradient(170deg, rgba(12, 30, 45, 0.95), rgba(19, 47, 68, 0.92));
        border-right: 1px solid var(--border);
      }}

      @media (max-width: 900px) {{
        .metric-grid {{
          grid-template-columns: repeat(2, minmax(130px, 1fr));
        }}

        .hero-shell {{
          padding: 16px;
        }}
      }}
    </style>
    """

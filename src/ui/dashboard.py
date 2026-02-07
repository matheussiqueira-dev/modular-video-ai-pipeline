from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd
import streamlit as st

from src.clustering.identifier import VisualIdentifier
from src.core.config import PipelineConfig
from src.core.exporters import JsonlExporter
from src.core.pipeline import VisionPipeline
from src.detection.detector import ObjectDetector
from src.events.analyzer import EventAnalyzer
from src.homography.transformer import PerspectiveTransformer
from src.ocr.reader import SceneTextReader
from src.segmentation.segmenter import VideoSegmenter
from src.visualization.drawer import PipelineVisualizer


st.set_page_config(page_title="Video AI Pipeline", page_icon="🎬", layout="wide")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');

          :root {
            --bg-start: #081726;
            --bg-end: #12324c;
            --surface: #10253a;
            --surface-soft: #143552;
            --text-main: #eef6ff;
            --text-muted: #bad2eb;
            --accent: #43c8ff;
            --accent-strong: #ffb020;
            --border: #2f5677;
          }

          .stApp {
            font-family: 'Space Grotesk', sans-serif;
            background:
              radial-gradient(circle at 15% 10%, rgba(67, 200, 255, 0.20), transparent 34%),
              radial-gradient(circle at 85% 10%, rgba(255, 176, 32, 0.18), transparent 38%),
              linear-gradient(130deg, var(--bg-start), var(--bg-end));
            color: var(--text-main);
          }

          .block-container {
            padding-top: 1.6rem;
            padding-bottom: 2.4rem;
            max-width: 1280px;
          }

          h1, h2, h3, p, label, span, div {
            color: var(--text-main);
          }

          .hero {
            background: linear-gradient(120deg, rgba(17, 45, 69, 0.86), rgba(26, 61, 89, 0.75));
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 20px 24px;
            margin-bottom: 14px;
            box-shadow: 0 18px 38px rgba(3, 10, 18, 0.30);
          }

          .metric-card {
            background: linear-gradient(140deg, var(--surface), var(--surface-soft));
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 12px 14px;
          }

          .muted {
            color: var(--text-muted);
          }

          .stButton > button {
            border-radius: 12px;
            border: 1px solid var(--accent);
            background: linear-gradient(90deg, var(--accent), #0ea5c7);
            color: #05131f;
            font-weight: 700;
            letter-spacing: 0.2px;
          }

          .stTextInput > div > div > input,
          .stTextArea textarea,
          .stNumberInput input {
            background: rgba(7, 24, 37, 0.70);
            border: 1px solid var(--border);
            color: var(--text-main);
          }

          .stSlider [data-baseweb="slider"] {
            padding-top: 10px;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def parse_zones(raw: str) -> List[dict]:
    """
    Each line format:
    zone_name,x1,y1,x2,y2
    """
    zones: List[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) != 5:
            continue
        name, x1, y1, x2, y2 = parts
        try:
            zones.append(
                {
                    "name": name,
                    "x1": int(x1),
                    "y1": int(y1),
                    "x2": int(x2),
                    "y2": int(y2),
                }
            )
        except ValueError:
            continue
    return zones


def run_dashboard() -> None:
    inject_styles()

    st.markdown(
        """
        <div class="hero">
          <h1 style="margin:0; font-size:2.0rem;">Modular Video AI Pipeline</h1>
          <p class="muted" style="margin:8px 0 0 0;">Processamento de vídeo com detecção, tracking, agrupamento visual, OCR e eventos temporais.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_right = st.columns([1.2, 1.0], gap="large")

    with col_left:
        st.subheader("Entrada")
        uploaded = st.file_uploader("Upload de vídeo", type=["mp4", "mov", "avi", "mkv"])

        st.subheader("Configuração")
        max_frames = st.slider("Máximo de frames", min_value=30, max_value=1200, value=240, step=30)
        fps = st.slider("FPS de saída", min_value=10, max_value=60, value=30)
        ocr_interval = st.slider("Intervalo de OCR", min_value=1, max_value=120, value=30)
        cluster_interval = st.slider("Intervalo de clustering", min_value=1, max_value=30, value=5)

        zones_raw = st.text_area(
            "Zonas monitoradas (uma por linha)",
            value="area_restrita,80,120,390,520\nentrada,900,120,1240,540",
            height=110,
            help="Formato: nome,x1,y1,x2,y2",
        )

        run = st.button("Processar vídeo", use_container_width=True, type="primary")

    with col_right:
        st.subheader("Saída")
        status = st.empty()
        metric_area = st.empty()
        video_area = st.empty()
        event_area = st.empty()

    if not run:
        return

    if uploaded is None:
        st.warning("Envie um vídeo para iniciar o processamento.")
        return

    zones = parse_zones(zones_raw)

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        input_path = temp_dir / uploaded.name
        output_path = temp_dir / "processed.mp4"
        export_path = temp_dir / "analytics.jsonl"

        input_path.write_bytes(uploaded.read())

        config = PipelineConfig(
            output_path=output_path,
            export_jsonl_path=export_path,
            max_frames=max_frames,
            fps=fps,
            ocr_interval=ocr_interval,
            clustering_interval=cluster_interval,
        )

        status.info("Executando pipeline...")

        detector = ObjectDetector(mock_mode=True)
        segmenter = VideoSegmenter()
        identifier = VisualIdentifier(mock_mode=True)
        reader = SceneTextReader(mock_mode=True)
        transformer = PerspectiveTransformer(
            src_points=np.array([[0, 0], [1280, 0], [1280, 720], [0, 720]], dtype=np.float32),
            dst_points=np.array([[0, 0], [100, 0], [100, 200], [0, 200]], dtype=np.float32),
        )
        analyzer = EventAnalyzer(fps=fps, dwell_seconds=3, zones=zones)
        visualizer = PipelineVisualizer(title="Pipeline Session")

        pipeline = VisionPipeline(
            detector=detector,
            segmenter=segmenter,
            identifier=identifier,
            reader=reader,
            transformer=transformer,
            analyzer=analyzer,
            visualizer=visualizer,
            config=config,
        )

        with JsonlExporter(export_path) as exporter:
            summary = pipeline.run_video(
                video_path=str(input_path),
                output_path=output_path,
                max_frames=max_frames,
                exporter=exporter,
            )

        status.success("Processamento concluído.")

        metric_html = f"""
        <div style='display:grid; grid-template-columns:repeat(3,1fr); gap:12px;'>
          <div class='metric-card'><div class='muted'>Frames</div><div style='font-size:1.5rem;font-weight:700;'>{int(summary['frames_processed'])}</div></div>
          <div class='metric-card'><div class='muted'>Eventos</div><div style='font-size:1.5rem;font-weight:700;'>{int(summary['events_detected'])}</div></div>
          <div class='metric-card'><div class='muted'>FPS Médio</div><div style='font-size:1.5rem;font-weight:700;'>{summary['average_processing_fps']:.2f}</div></div>
        </div>
        """
        metric_area.markdown(metric_html, unsafe_allow_html=True)

        video_area.video(output_path.read_bytes())

        events = []
        if export_path.exists():
            with export_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    row = json.loads(line)
                    if row.get("type") == "event":
                        events.append(row)

        if events:
            df = pd.DataFrame(events)
            event_area.dataframe(df[["frame", "type", "object_id", "severity", "details"]], use_container_width=True)
        else:
            event_area.info("Nenhum evento detectado com os parâmetros atuais.")


if __name__ == "__main__":
    run_dashboard()

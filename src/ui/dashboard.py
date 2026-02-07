from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Dict

import numpy as np
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
from src.ui.analytics import filter_events, load_analytics_jsonl, summarize_events, summarize_frames
from src.ui.components import (
    build_event_timeline_chart,
    build_frame_performance_chart,
    render_hero,
    render_metric_cards,
    render_run_history,
    render_zone_preview,
)
from src.ui.parsers import estimated_runtime_seconds, parse_zones_text
from src.ui.presets import PRESETS, list_preset_names
from src.ui.state import dataframe_to_csv_bytes, get_run_history, get_run_result, init_session_state, save_run_result
from src.ui.theme import ThemeOptions, build_css
from src.visualization.drawer import PipelineVisualizer


st.set_page_config(page_title="Vision Frontend Studio", page_icon="🎞️", layout="wide")


def _apply_preset_defaults(preset_name: str) -> None:
    if preset_name == "Custom":
        st.session_state["selected_preset"] = "Custom"
        return

    if preset_name not in PRESETS:
        return

    previous = st.session_state.get("selected_preset")
    if previous == preset_name:
        return

    preset = PRESETS[preset_name]
    st.session_state["max_frames"] = preset.max_frames
    st.session_state["fps"] = preset.fps
    st.session_state["ocr_interval"] = preset.ocr_interval
    st.session_state["cluster_interval"] = preset.cluster_interval
    st.session_state["zones_editor"] = preset.zones_text
    st.session_state["selected_preset"] = preset_name


def _build_pipeline(config: PipelineConfig, zones: list[dict], mock_mode: bool) -> VisionPipeline:
    detector = ObjectDetector(mock_mode=mock_mode)
    segmenter = VideoSegmenter()
    identifier = VisualIdentifier(mock_mode=mock_mode)
    reader = SceneTextReader(mock_mode=mock_mode)
    transformer = PerspectiveTransformer(
        src_points=np.array([[0, 0], [1280, 0], [1280, 720], [0, 720]], dtype=np.float32),
        dst_points=np.array([[0, 0], [100, 0], [100, 200], [0, 200]], dtype=np.float32),
    )
    analyzer = EventAnalyzer(fps=config.fps, dwell_seconds=3, zones=zones)
    visualizer = PipelineVisualizer(title="Frontend Studio Session")

    return VisionPipeline(
        detector=detector,
        segmenter=segmenter,
        identifier=identifier,
        reader=reader,
        transformer=transformer,
        analyzer=analyzer,
        visualizer=visualizer,
        config=config,
    )


def _render_sidebar_controls() -> Dict:
    with st.sidebar:
        st.header("Control Center")
        st.caption("Configure o processamento com foco em qualidade, velocidade e analise operacional.")

        preset_name = st.selectbox(
            "Preset de fluxo",
            options=list_preset_names(),
            help="Aplique um preset para acelerar configuracoes comuns.",
        )
        _apply_preset_defaults(preset_name)

        if preset_name in PRESETS:
            st.info(PRESETS[preset_name].description)

        uploaded = st.file_uploader(
            "Video de entrada",
            type=["mp4", "mov", "avi", "mkv"],
            help="Use videos curtos para iterar mais rapido no ajuste de parametros.",
        )

        st.subheader("Parametros")
        max_frames = st.slider("Maximo de frames", min_value=30, max_value=1500, step=30, key="max_frames")
        fps = st.slider("FPS de saida", min_value=10, max_value=60, key="fps")
        ocr_interval = st.slider("Intervalo OCR", min_value=1, max_value=120, key="ocr_interval")
        cluster_interval = st.slider("Intervalo Clustering", min_value=1, max_value=40, key="cluster_interval")

        st.subheader("Acessibilidade")
        high_contrast = st.toggle("Alto contraste", key="high_contrast")
        reduced_motion = st.toggle("Reducao de movimento", key="reduced_motion")

        st.subheader("Modo de execucao")
        mock_mode = st.toggle("Mock mode", key="mock_mode", help="Desative para integrar modelos reais no futuro.")

        zones_text = st.text_area(
            "Zonas monitoradas",
            key="zones_editor",
            height=130,
            help="Formato por linha: nome,x1,y1,x2,y2",
        )

        zones, zone_warnings = parse_zones_text(zones_text)
        for warning in zone_warnings[:4]:
            st.warning(warning)
        if len(zone_warnings) > 4:
            st.caption(f"+{len(zone_warnings) - 4} aviso(s) adicional(is)")

        estimated_seconds = estimated_runtime_seconds(max_frames, expected_fps=max(1.0, fps * 0.42))
        st.caption(f"Tempo estimado de processamento: ~{estimated_seconds:.1f}s")

        run_clicked = st.button("Processar video", use_container_width=True, type="primary")

    return {
        "preset_name": preset_name,
        "uploaded": uploaded,
        "max_frames": max_frames,
        "fps": fps,
        "ocr_interval": ocr_interval,
        "cluster_interval": cluster_interval,
        "high_contrast": high_contrast,
        "reduced_motion": reduced_motion,
        "mock_mode": mock_mode,
        "zones": zones,
        "run_clicked": run_clicked,
    }


def _run_pipeline_from_ui(control: Dict, studio_slot) -> None:
    uploaded = control["uploaded"]
    if uploaded is None:
        studio_slot.warning("Envie um video para iniciar o processamento.")
        return

    progress = studio_slot.progress(0)
    status = studio_slot.empty()

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        input_path = temp_dir / uploaded.name
        output_path = temp_dir / "processed.mp4"
        export_path = temp_dir / "analytics.jsonl"

        input_path.write_bytes(uploaded.getbuffer())

        config = PipelineConfig(
            output_path=output_path,
            export_jsonl_path=export_path,
            max_frames=control["max_frames"],
            fps=control["fps"],
            ocr_interval=control["ocr_interval"],
            clustering_interval=control["cluster_interval"],
        )

        pipeline = _build_pipeline(config=config, zones=control["zones"], mock_mode=control["mock_mode"])

        def _on_progress(done_frames: int, total_frames: int, stats: Dict[str, float]) -> None:
            pct = int(min(100, (done_frames / max(1, total_frames)) * 100))
            progress.progress(pct)
            status.info(
                f"Processando... frame {done_frames}/{total_frames} | FPS {stats.get('processing_fps', 0.0):.2f}"
            )

        with JsonlExporter(export_path) as exporter:
            summary = pipeline.run_video(
                video_path=str(input_path),
                output_path=output_path,
                max_frames=config.max_frames,
                exporter=exporter,
                progress_callback=_on_progress,
            )

        frames_df, events_df = load_analytics_jsonl(export_path)
        video_bytes = output_path.read_bytes() if output_path.exists() else b""
        analytics_bytes = export_path.read_bytes() if export_path.exists() else b""

        save_run_result(
            {
                "preset": control["preset_name"],
                "summary": summary,
                "video_bytes": video_bytes,
                "analytics_bytes": analytics_bytes,
                "frames_df": frames_df,
                "events_df": events_df,
                "zones": control["zones"],
                "config": {
                    "max_frames": config.max_frames,
                    "fps": config.fps,
                    "ocr_interval": config.ocr_interval,
                    "cluster_interval": config.clustering_interval,
                    "mock_mode": control["mock_mode"],
                },
            }
        )

    progress.progress(100)
    status.success("Processamento concluido com sucesso.")


def _render_studio_tab(control: Dict, run_result: Dict | None) -> None:
    render_hero(
        title="Frontend Vision Studio",
        subtitle="Orquestracao visual para upload, configuracao, processamento e inspecao operacional de eventos.",
        tags=["A11y", "Pipeline", "Analytics", "Production-ready"],
    )

    st.subheader("Configuracao de zonas")
    render_zone_preview(control["zones"])

    if run_result is None:
        st.info("Execute o pipeline para visualizar metricas, video processado e analytics detalhado.")
        return

    summary = run_result.get("summary", {})
    metrics = [
        ("Frames Processados", str(int(summary.get("frames_processed", 0)))),
        ("Eventos Detectados", str(int(summary.get("events_detected", 0)))),
        ("FPS Medio", f"{float(summary.get('average_processing_fps', 0.0)):.2f}"),
        ("Preset", str(run_result.get("preset", "Custom"))),
    ]
    render_metric_cards(metrics)

    st.subheader("Video anotado")
    video_bytes = run_result.get("video_bytes", b"")
    if video_bytes:
        st.video(video_bytes)

    st.subheader("Exportacao")
    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            label="Download video processado",
            data=video_bytes,
            file_name="processed_frontend.mp4",
            mime="video/mp4",
            use_container_width=True,
        )
    with col2:
        st.download_button(
            label="Download analytics JSONL",
            data=run_result.get("analytics_bytes", b""),
            file_name="frontend_analytics.jsonl",
            mime="application/json",
            use_container_width=True,
        )


def _render_analytics_tab(run_result: Dict | None) -> None:
    st.subheader("Analytics Explorer")

    if run_result is None:
        st.info("Sem dados. Execute o processamento para habilitar analytics.")
        return

    frames_df = run_result.get("frames_df")
    events_df = run_result.get("events_df")

    if frames_df is None or events_df is None:
        st.info("Dados incompletos para analytics.")
        return

    frame_summary = summarize_frames(frames_df)
    event_summary = summarize_events(events_df)
    render_metric_cards(
        [
            ("Frames", str(frame_summary["frames"])),
            ("Pico de Tracks", str(frame_summary["peak_tracks"])),
            ("Pico de Eventos", str(frame_summary["peak_events"])),
            ("Eventos Totais", str(event_summary["total"])),
        ]
    )

    st.markdown("### Filtros de eventos")
    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns([1.3, 1.2, 1.1, 1.4])

    with filter_col1:
        selected_types = st.multiselect(
            "Tipo",
            options=sorted(events_df["type"].dropna().unique().tolist()) if not events_df.empty else [],
        )
    with filter_col2:
        selected_severities = st.multiselect(
            "Severidade",
            options=sorted(events_df["severity"].dropna().unique().tolist()) if not events_df.empty else [],
        )
    with filter_col3:
        object_id_query = st.text_input("Object IDs", placeholder="Ex: 1,2,5")
    with filter_col4:
        text_query = st.text_input("Busca textual", placeholder="Ex: zone")

    filtered_events = filter_events(events_df, selected_types, selected_severities, object_id_query, text_query)

    chart_col1, chart_col2 = st.columns(2)
    with chart_col1:
        perf_fig = build_frame_performance_chart(frames_df)
        if perf_fig is not None:
            st.plotly_chart(perf_fig, use_container_width=True)
        else:
            st.info("Grafico de performance indisponivel. Instale plotly para habilitar visualizacao.")
    with chart_col2:
        events_fig = build_event_timeline_chart(filtered_events)
        if events_fig is not None:
            st.plotly_chart(events_fig, use_container_width=True)
        else:
            if filtered_events.empty:
                st.info("Sem eventos para os filtros atuais.")
            else:
                st.info("Timeline indisponivel. Instale plotly para habilitar visualizacao.")

    st.markdown("### Eventos filtrados")
    st.dataframe(filtered_events, use_container_width=True, hide_index=True)

    st.download_button(
        label="Download eventos filtrados (CSV)",
        data=dataframe_to_csv_bytes(filtered_events),
        file_name="filtered_events.csv",
        mime="text/csv",
        use_container_width=True,
    )


def _render_history_tab() -> None:
    st.subheader("Historico da Sessao")
    render_run_history(get_run_history())


def _render_architecture_notes(control: Dict) -> None:
    st.markdown(
        f"""
        <div class='panel-shell ui-fade-in'>
          <h3 style='margin-top:0;'>Frontend Review Snapshot</h3>
          <p class='muted'>
            Arquitetura modularizada em componentes de UI, estado e analytics. Fluxo principal cobre upload, parametrizacao,
            execucao assitida com progresso, leitura analitica e exportacao.
          </p>
          <ul>
            <li><span class='muted'>Responsividade:</span> layout com colunas adaptativas e blocos mobile-friendly.</li>
            <li><span class='muted'>Acessibilidade:</span> modo alto contraste e opcao de reducao de movimento.</li>
            <li><span class='muted'>Performance:</span> OCR/Clustering intervalados, filtros client-side e exportacao direta.</li>
            <li><span class='muted'>SEO:</span> para Streamlit, SEO publico e limitado por arquitetura server-rendered.</li>
            <li><span class='muted'>Preset ativo:</span> {control['preset_name']}.</li>
          </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_dashboard() -> None:
    init_session_state()
    control = _render_sidebar_controls()

    st.markdown(
        build_css(
            ThemeOptions(
                high_contrast=control["high_contrast"],
                reduced_motion=control["reduced_motion"],
            )
        ),
        unsafe_allow_html=True,
    )

    studio_placeholder = st.empty()

    if control["run_clicked"]:
        _run_pipeline_from_ui(control, studio_placeholder)

    run_result = get_run_result()

    tabs = st.tabs(["Studio", "Analytics", "History", "Review"])
    with tabs[0]:
        _render_studio_tab(control, run_result)
    with tabs[1]:
        _render_analytics_tab(run_result)
    with tabs[2]:
        _render_history_tab()
    with tabs[3]:
        _render_architecture_notes(control)


if __name__ == "__main__":
    run_dashboard()

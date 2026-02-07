from __future__ import annotations

import time
from typing import Dict

import numpy as np
import requests
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
from src.ui.analytics import filter_events, load_analytics_jsonl_bytes, summarize_events, summarize_frames
from src.ui.api_client import ApiClientConfig, BackendApiClient
from src.ui.components import (
    build_event_timeline_chart,
    build_frame_performance_chart,
    build_severity_distribution_chart,
    render_comparison_summary,
    render_hero,
    render_metric_cards,
    render_run_history,
    render_zone_preview,
)
from src.ui.contracts import FrontendControl, RunPayload
from src.ui.insights import compare_summaries
from src.ui.parsers import estimated_runtime_seconds, parse_zones_text
from src.ui.presets import PRESETS, list_preset_names
from src.ui.profiles import add_profile, apply_profile_to_state, find_profile, get_profile_names, snapshot_config_from_control
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


def _build_control(
    preset_name: str,
    uploaded,
    execution_target: str,
    max_frames: int,
    fps: int,
    ocr_interval: int,
    cluster_interval: int,
    high_contrast: bool,
    reduced_motion: bool,
    mock_mode: bool,
    zones: list[dict],
    run_clicked: bool,
) -> FrontendControl:
    return FrontendControl(
        preset_name=preset_name,
        uploaded=uploaded,
        execution_target=execution_target,
        max_frames=max_frames,
        fps=fps,
        ocr_interval=ocr_interval,
        cluster_interval=cluster_interval,
        high_contrast=high_contrast,
        reduced_motion=reduced_motion,
        mock_mode=mock_mode,
        zones=zones,
        backend_base_url=st.session_state.get("backend_base_url", "http://localhost:8000"),
        backend_api_key=st.session_state.get("backend_api_key", ""),
        backend_poll=float(st.session_state.get("backend_poll", 1.2)),
        run_clicked=run_clicked,
    )


def _render_profile_manager(control: FrontendControl) -> None:
    st.subheader("Perfis")
    st.caption("Salve configuracoes para repetir cenarios sem retrabalho.")

    profile_name = st.text_input("Nome do perfil", key="profile_name_input", placeholder="Ex: loja-noturno")
    profile_names = get_profile_names(st.session_state.get("config_profiles", []))
    selected_profile = st.selectbox(
        "Perfil salvo",
        options=[""] + profile_names,
        key="selected_profile_name",
        help="Selecione e carregue um perfil para preencher os controles atuais.",
    )

    col_save, col_load = st.columns(2)
    with col_save:
        if st.button("Salvar perfil", use_container_width=True):
            updated, ok, message = add_profile(
                profiles=list(st.session_state.get("config_profiles", [])),
                name=profile_name,
                config_snapshot=snapshot_config_from_control(control),
            )
            st.session_state["config_profiles"] = updated
            if ok:
                st.success(message)
            else:
                st.warning(message)

    with col_load:
        if st.button("Carregar perfil", use_container_width=True):
            if not selected_profile:
                st.warning("Selecione um perfil para carregar.")
            else:
                found = find_profile(st.session_state.get("config_profiles", []), selected_profile)
                if found is None:
                    st.error("Perfil nao encontrado.")
                else:
                    apply_profile_to_state(found.get("config", {}), st.session_state)
                    st.success(f"Perfil '{selected_profile}' carregado")
                    st.rerun()


def _render_sidebar_controls() -> FrontendControl:
    with st.sidebar:
        st.header("Control Center")
        st.caption("Configure processamento com foco em qualidade, performance e operabilidade.")

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
            help="Use videos curtos para iterar rapidamente no ajuste de parametros.",
        )

        st.subheader("Engine")
        execution_target = st.radio(
            "Destino de execucao",
            options=["Local Engine", "Backend API"],
            key="execution_target",
            help="Local: processa no app. API: envia job para backend protegido por API key.",
        )

        if execution_target == "Backend API":
            st.text_input("Base URL da API", key="backend_base_url", placeholder="http://localhost:8000")
            st.text_input("API Key", key="backend_api_key", type="password")
            st.slider("Intervalo de polling (s)", min_value=1.0, max_value=5.0, value=1.2, step=0.2, key="backend_poll")

        st.subheader("Parametros")
        max_frames = st.slider("Maximo de frames", min_value=30, max_value=1500, step=30, key="max_frames")
        fps = st.slider("FPS de saida", min_value=10, max_value=60, key="fps")
        ocr_interval = st.slider("Intervalo OCR", min_value=1, max_value=120, key="ocr_interval")
        cluster_interval = st.slider("Intervalo Clustering", min_value=1, max_value=40, key="cluster_interval")

        st.subheader("Acessibilidade")
        high_contrast = st.toggle("Alto contraste", key="high_contrast")
        reduced_motion = st.toggle("Reducao de movimento", key="reduced_motion")

        st.subheader("Inferencia")
        mock_mode = st.toggle("Mock mode", key="mock_mode", help="Desative para integrar modelos reais.")

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

        control = _build_control(
            preset_name=preset_name,
            uploaded=uploaded,
            execution_target=execution_target,
            max_frames=max_frames,
            fps=fps,
            ocr_interval=ocr_interval,
            cluster_interval=cluster_interval,
            high_contrast=high_contrast,
            reduced_motion=reduced_motion,
            mock_mode=mock_mode,
            zones=zones,
            run_clicked=run_clicked,
        )

        st.markdown("---")
        _render_profile_manager(control)

    return control


def _save_result_payload(control: FrontendControl, summary: dict, video_bytes: bytes, analytics_bytes: bytes, job_id: str | None = None) -> None:
    frames_df, events_df = load_analytics_jsonl_bytes(analytics_bytes)

    payload = RunPayload(
        preset=control.preset_name,
        summary=summary,
        video_bytes=video_bytes,
        analytics_bytes=analytics_bytes,
        frames_df=frames_df,
        events_df=events_df,
        zones=control.zones,
        execution_target=control.execution_target,
        config={
            "max_frames": control.max_frames,
            "fps": control.fps,
            "ocr_interval": control.ocr_interval,
            "cluster_interval": control.cluster_interval,
            "mock_mode": control.mock_mode,
        },
        job_id=job_id,
    )

    save_run_result(
        {
            "preset": payload.preset,
            "summary": payload.summary,
            "video_bytes": payload.video_bytes,
            "analytics_bytes": payload.analytics_bytes,
            "frames_df": payload.frames_df,
            "events_df": payload.events_df,
            "zones": payload.zones,
            "job_id": payload.job_id,
            "execution_target": payload.execution_target,
            "config": payload.config,
        }
    )


def _run_pipeline_local(control: FrontendControl, studio_slot) -> None:
    uploaded = control.uploaded
    if uploaded is None:
        studio_slot.warning("Envie um video para iniciar o processamento.")
        return

    progress = studio_slot.progress(0)
    status = studio_slot.empty()

    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmpdir:
        temp_dir = Path(tmpdir)
        input_path = temp_dir / uploaded.name
        output_path = temp_dir / "processed.mp4"
        export_path = temp_dir / "analytics.jsonl"

        input_path.write_bytes(uploaded.getbuffer())

        config = PipelineConfig(
            output_path=output_path,
            export_jsonl_path=export_path,
            max_frames=control.max_frames,
            fps=control.fps,
            ocr_interval=control.ocr_interval,
            clustering_interval=control.cluster_interval,
        )

        pipeline = _build_pipeline(config=config, zones=control.zones, mock_mode=control.mock_mode)

        def _on_progress(done_frames: int, total_frames: int, stats: Dict[str, float]) -> None:
            pct = int(min(100, (done_frames / max(1, total_frames)) * 100))
            progress.progress(pct)
            status.info(
                f"Processando localmente... frame {done_frames}/{total_frames} | FPS {stats.get('processing_fps', 0.0):.2f}"
            )

        with JsonlExporter(export_path) as exporter:
            summary = pipeline.run_video(
                video_path=str(input_path),
                output_path=output_path,
                max_frames=config.max_frames,
                exporter=exporter,
                progress_callback=_on_progress,
            )

        video_bytes = output_path.read_bytes() if output_path.exists() else b""
        analytics_bytes = export_path.read_bytes() if export_path.exists() else b""
        _save_result_payload(control, summary, video_bytes, analytics_bytes, job_id=None)

    progress.progress(100)
    status.success("Processamento local concluido.")


def _run_pipeline_backend(control: FrontendControl, studio_slot) -> None:
    uploaded = control.uploaded
    if uploaded is None:
        studio_slot.warning("Envie um video para iniciar o processamento.")
        return

    if not control.backend_base_url:
        studio_slot.error("Informe a Base URL da API para executar no backend.")
        return

    if not control.backend_api_key:
        studio_slot.error("Informe a API Key para autenticar no backend.")
        return

    progress = studio_slot.progress(0)
    status = studio_slot.empty()

    client = BackendApiClient(
        ApiClientConfig(
            base_url=control.backend_base_url,
            api_key=control.backend_api_key,
            timeout_seconds=300,
        )
    )

    payload = {
        "max_frames": control.max_frames,
        "fps": control.fps,
        "ocr_interval": control.ocr_interval,
        "clustering_interval": control.cluster_interval,
        "mock_mode": control.mock_mode,
    }

    try:
        status.info("Criando job no backend...")
        created = client.create_job(
            file_name=uploaded.name,
            file_bytes=uploaded.getvalue(),
            payload=payload,
            zones=control.zones,
            async_mode=True,
        )
        job_id = created["job_id"]

        while True:
            job = client.get_job(job_id)
            pct = int(float(job.get("progress", 0.0)))
            progress.progress(max(0, min(100, pct)))
            status.info(
                f"Backend job {job_id} | status={job.get('status')} | {int(job.get('processed_frames', 0))}/{int(job.get('max_frames', 0))} frames"
            )

            state = job.get("status")
            if state == "completed":
                video_bytes = client.download_video(job_id)
                analytics_bytes = client.download_analytics(job_id)
                summary = job.get("summary", {})
                _save_result_payload(control, summary, video_bytes, analytics_bytes, job_id=job_id)
                progress.progress(100)
                status.success(f"Processamento remoto concluido. Job ID: {job_id}")
                break

            if state == "failed":
                message = job.get("error_message") or "Falha no processamento remoto"
                status.error(f"Job {job_id} falhou: {message}")
                break

            time.sleep(max(0.5, control.backend_poll))

    except requests.HTTPError as exc:
        detail = "Erro HTTP ao executar backend"
        if exc.response is not None:
            try:
                payload = exc.response.json()
                detail = payload.get("detail", detail)
            except Exception:
                detail = exc.response.text or detail
        status.error(detail)
    except Exception as exc:
        status.error(f"Falha na integracao backend: {exc}")


def _run_pipeline_from_ui(control: FrontendControl, studio_slot) -> None:
    if control.execution_target == "Backend API":
        _run_pipeline_backend(control, studio_slot)
    else:
        _run_pipeline_local(control, studio_slot)


def _get_previous_summary() -> dict | None:
    history = get_run_history()
    if len(history) < 2:
        return None
    return history[1].get("summary")


def _render_studio_tab(control: FrontendControl, run_result: Dict | None) -> None:
    render_hero(
        title="Frontend Vision Studio",
        subtitle="Orquestracao visual para upload, configuracao, processamento e inspecao operacional de eventos.",
        tags=["A11y", "Pipeline", "Analytics", "Production-ready"],
    )

    st.subheader("Configuracao de zonas")
    render_zone_preview(control.zones)

    if run_result is None:
        st.info("Execute o pipeline para visualizar metricas, video processado e analytics detalhado.")
        return

    summary = run_result.get("summary", {})
    previous = _get_previous_summary()
    comparison = compare_summaries(summary, previous)

    st.markdown("### Resultado da Execucao")
    render_comparison_summary(comparison)

    metadata_cols = st.columns(3)
    metadata_cols[0].caption(f"Preset: {run_result.get('preset', 'Custom')}")
    metadata_cols[1].caption(f"Execucao: {run_result.get('execution_target', 'Local Engine')}")
    metadata_cols[2].caption(f"Job ID: {run_result.get('job_id', 'N/A')}")

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

    chart_col1, chart_col2, chart_col3 = st.columns(3)
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
    with chart_col3:
        severity_fig = build_severity_distribution_chart(filtered_events)
        if severity_fig is not None:
            st.plotly_chart(severity_fig, use_container_width=True)
        else:
            st.info("Distribuicao de severidade indisponivel para os filtros atuais.")

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


def _render_architecture_notes(control: FrontendControl) -> None:
    st.markdown(
        f"""
        <div class='panel-shell ui-fade-in'>
          <h3 style='margin-top:0;'>Frontend Review Snapshot</h3>
          <p class='muted'>
            Arquitetura modular com execucao local/remota, contratos tipados no dashboard, perfis de configuracao,
            comparativo de runs e analytics com filtros multicriterio.
          </p>
          <ul>
            <li><span class='muted'>Design System:</span> tokens centralizados, componentes reutilizaveis e layout responsivo.</li>
            <li><span class='muted'>Acessibilidade:</span> alto contraste e reducao de movimento configuraveis.</li>
            <li><span class='muted'>Performance:</span> parsing em memoria e fluxo incremental por job.</li>
            <li><span class='muted'>Escalabilidade:</span> compativel com backend API versionado.</li>
            <li><span class='muted'>Target atual:</span> {control.execution_target}.</li>
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
                high_contrast=control.high_contrast,
                reduced_motion=control.reduced_motion,
            )
        ),
        unsafe_allow_html=True,
    )

    studio_placeholder = st.empty()

    if control.run_clicked:
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

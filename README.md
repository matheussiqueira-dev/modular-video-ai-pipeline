# Modular Video AI Pipeline

Pipeline modular para análise de vídeo com foco em arquitetura limpa, evolução contínua e operação em produção.

## Visão Geral

Este projeto processa vídeo quadro a quadro e combina múltiplos estágios de visão computacional:

- detecção de objetos
- segmentação/tracking com IDs estáveis
- agrupamento visual (clustering)
- leitura de texto em cena (OCR)
- transformação espacial (homografia)
- detecção de eventos temporais (dwell, entrada/saída de zona)
- visualização avançada com HUD

O sistema roda em **modo mock determinístico** por padrão, permitindo desenvolvimento e testes sem pesos pesados de modelos.

## Público-Alvo

- times de engenharia de visão computacional
- projetos de monitoramento e segurança
- analytics esportivo e varejo
- squads que precisam de base escalável para evoluir de protótipo para produção

## Tecnologias Utilizadas

- Python 3.10+
- OpenCV
- NumPy
- scikit-learn (KMeans)
- Streamlit (dashboard)
- Plotly/Pandas (analytics no dashboard)
- PyTest (testes)

Dependências opcionais para modelos reais:

- PyTorch
- Transformers
- Accelerate

## Funcionalidades Principais

- Pipeline orquestrado por `VisionPipeline` (`src/core/pipeline.py`)
- Tracking por IoU para manter consistência de IDs
- OCR com cache por trilha para reduzir recomputação
- Clustering com embeddings determinísticos em mock mode
- Eventos temporais com anti-spam (cooldown)
- Monitoramento por zonas configuráveis (entrada/saída)
- Exportação de telemetria em JSONL (frames + eventos)
- Overlay UI/UX refatorado com melhor hierarquia visual
- Dashboard web para upload, configuração, execução e inspeção de resultados

## Instalação

```bash
git clone https://github.com/matheussiqueira-dev/modular-video-ai-pipeline.git
cd modular-video-ai-pipeline
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
# source .venv/bin/activate
pip install -r requirements.txt
```

## Como Usar

### 1. Execução via CLI

```bash
python demo.py \
  --video_path input.mp4 \
  --output_path output.mp4 \
  --max_frames 300 \
  --ocr_interval 30 \
  --cluster_interval 5 \
  --export_jsonl outputs/analytics.jsonl
```

Exemplo com zonas:

```bash
python demo.py \
  --video_path input.mp4 \
  --zone area_restrita:80,120,390,520 \
  --zone entrada:900,120,1240,540
```

### 2. Execução via Dashboard

```bash
streamlit run app.py
```

Fluxo do dashboard:

1. upload do vídeo
2. ajuste de parâmetros
3. definição de zonas
4. processamento
5. visualização de vídeo anotado + tabela de eventos

## Estrutura do Projeto

```text
modular-video-ai-pipeline/
├── app.py
├── demo.py
├── requirements.txt
├── README.md
├── ARCHITECTURE.md
├── src/
│   ├── core/
│   │   ├── config.py
│   │   ├── exporters.py
│   │   └── pipeline.py
│   ├── detection/
│   │   └── detector.py
│   ├── segmentation/
│   │   └── segmenter.py
│   ├── clustering/
│   │   └── identifier.py
│   ├── ocr/
│   │   └── reader.py
│   ├── homography/
│   │   └── transformer.py
│   ├── events/
│   │   └── analyzer.py
│   ├── visualization/
│   │   └── drawer.py
│   └── ui/
│       └── dashboard.py
└── tests/
    ├── test_detector.py
    ├── test_segmenter.py
    ├── test_clustering.py
    ├── test_events.py
    └── test_pipeline.py
```

## Boas Práticas Aplicadas

- separação clara de responsabilidades por módulo
- interfaces previsíveis entre etapas
- validação de entrada e tratamento de edge cases
- redução de custo computacional por intervalos configuráveis
- logs e telemetria estruturada para observabilidade
- testes automatizados cobrindo componentes críticos

## Qualidade e Testes

```bash
python -m pytest tests -q
```

Resultado esperado da suíte atual: **21 testes passando**.

## Possíveis Melhorias Futuras

- ativar inferência real (RF-DETR, SAM2, VLM) com fallback automático
- suporte multi-câmera e correlação de identidades entre cenas
- fila assíncrona para processamento distribuído
- persistência em banco para analytics históricos
- alertas em tempo real (webhook, e-mail, mensageria)
- tuning adaptativo de thresholds por contexto operacional

## Licença

MIT. Consulte `LICENSE`.

## Autoria

Autoria: Matheus Siqueira  
Website: https://www.matheussiqueira.dev/

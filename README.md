# Frontend Vision Studio

Interface frontend profissional para o **Modular Video AI Pipeline**, projetada para configurar, executar e analisar processamento de video com foco em usabilidade, acessibilidade e observabilidade.

## Visao Geral do Frontend

O frontend foi desenhado para operadores e times tecnicos que precisam:

- subir videos rapidamente
- configurar parametros de processamento sem editar codigo
- acompanhar execucao com feedback visual
- investigar eventos com filtros e visualizacoes
- exportar resultados para auditoria e analise externa

### Fluxo principal

1. Upload do video
2. Selecao de preset ou configuracao manual
3. Definicao/validacao de zonas monitoradas
4. Execucao com progresso em tempo real
5. Analise de resultados (video, tabela, timeline, historico)

## Analise Frontend (estado atual apos refactor)

### Arquitetura e organizacao

A camada frontend foi modularizada para facilitar manutencao e crescimento:

- `src/ui/dashboard.py`: composicao do fluxo da aplicacao
- `src/ui/theme.py`: tokens visuais e estilos globais
- `src/ui/presets.py`: presets operacionais por contexto
- `src/ui/parsers.py`: parsing e validacao de zonas
- `src/ui/analytics.py`: leitura/filtro/sumarizacao de telemetria
- `src/ui/state.py`: gerenciamento de estado de sessao
- `src/ui/components/panels.py`: blocos de UI reutilizaveis

### Performance e escalabilidade

- processamento configuravel por `ocr_interval` e `cluster_interval`
- callback de progresso para feedback continuo sem bloquear UX
- exportacao JSONL incremental para analise posterior
- historico local de execucoes para comparacao rapida de configuracoes

### Acessibilidade e responsividade

- modo de alto contraste
- modo de reducao de movimento
- componentes com labels explicitos e feedback de validacao
- layout adaptativo com grid responsivo e sidebar funcional

### SEO

Como o frontend usa Streamlit (app server-side), SEO indexavel publico e limitado por natureza arquitetural.
Para paginas publicas com estrategia SEO forte, recomenda-se frontend web dedicado (React/Next.js) consumindo os mesmos artefatos.

## Stack e Tecnologias

- Python 3.10+
- Streamlit
- Pandas
- Plotly (graficos, com fallback seguro quando ausente)
- NumPy
- OpenCV
- PyTest

## Features Frontend Implementadas

- Design system leve com tokens visuais reutilizaveis
- Presets de operacao (`Sports Analytics`, `Retail Monitoring`, `Security Patrol`)
- Validacao assistida de zonas com avisos contextuais
- Barra de progresso e status frame-a-frame
- Analytics Explorer com filtros combinados:
  - tipo de evento
  - severidade
  - object IDs
  - busca textual
- Exportacao de artefatos:
  - video processado
  - analytics JSONL
  - eventos filtrados em CSV
- Historico de execucoes na sessao

## Estrutura do Projeto

```text
modular-video-ai-pipeline/
├── app.py
├── demo.py
├── requirements.txt
├── src/
│   ├── core/
│   │   ├── config.py
│   │   ├── exporters.py
│   │   └── pipeline.py
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── dashboard.py
│   │   ├── theme.py
│   │   ├── presets.py
│   │   ├── parsers.py
│   │   ├── analytics.py
│   │   ├── state.py
│   │   └── components/
│   │       ├── __init__.py
│   │       └── panels.py
│   └── ...
└── tests/
    ├── test_pipeline.py
    ├── test_ui_parsers.py
    ├── test_ui_analytics.py
    └── ...
```

## Setup e Execucao

### 1. Instalacao

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

### 2. Rodar Frontend

```bash
streamlit run app.py
```

### 3. Rodar via CLI (suporte)

```bash
python demo.py --video_path input.mp4 --output_path output.mp4 --export_jsonl outputs/analytics.jsonl
```

## Build

Por ser Streamlit, nao existe etapa de bundle frontend tradicional (webpack/vite build).
Em producao, recomenda-se:

1. containerizar app (`Docker`)
2. configurar variaveis e volumes de saida
3. publicar atras de proxy reverso (Nginx/Traefik)

## Qualidade e Testes

```bash
python -m pytest tests -q
```

Suite atual contempla modulos de pipeline e frontend utilitario (parsers e analytics).

## Boas Praticas Adotadas

- modularizacao por responsabilidade
- design tokens centralizados
- fallback para dependencia opcional (`plotly`)
- estado de sessao explicito e controlado
- validacoes de entrada antes da execucao
- exportacao estruturada para rastreabilidade

## Melhorias Futuras

- comparador visual entre duas execucoes (A/B de parametros)
- autenticao e perfis de permissao para operacao multiusuario
- pagina de configuracoes persistentes por ambiente
- notificacoes em tempo real (webhook/Slack/email)
- frontend dedicado SPA/SSR para SEO publico

## Licenca

MIT. Consulte `LICENSE`.

Autoria: Matheus Siqueira  
Website: https://www.matheussiqueira.dev/

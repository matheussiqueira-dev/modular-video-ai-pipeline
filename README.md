# Frontend Vision Studio

Aplicacao frontend profissional para operacao e analise do pipeline de video AI, com foco em UX de alto nivel, acessibilidade, performance e arquitetura frontend escalavel.

## Visao Geral do Frontend

O Frontend Vision Studio foi desenhado para operadores, analistas e equipes de engenharia que precisam configurar, executar e investigar processamento de video com alto controle visual.

### Proposito

- reduzir friccao operacional no uso do pipeline
- acelerar iteracao de parametros
- melhorar leitura de resultados e eventos
- permitir operacao local ou remota (via API backend)

### Fluxo principal do usuario

1. Upload do video
2. Escolha de preset ou configuracao manual
3. Definicao e validacao de zonas monitoradas
4. Execucao (Local Engine ou Backend API)
5. Analise de resultados, comparacao de runs e exportacao de artefatos

## Analise Frontend (arquitetura atual)

### Organizacao e padroes

Camada frontend modularizada em responsabilidades claras:

- `src/ui/dashboard.py`: orquestracao da experiencia
- `src/ui/theme.py`: design tokens e estilos globais
- `src/ui/components/panels.py`: componentes reutilizaveis e visualizacao
- `src/ui/analytics.py`: parsing, filtros e sumarios de telemetria
- `src/ui/parsers.py`: validacao e normalizacao de entrada
- `src/ui/profiles.py`: perfis salvos de configuracao
- `src/ui/insights.py`: comparacao entre execucoes
- `src/ui/api_client.py`: integracao com backend remoto
- `src/ui/state.py`: estado de sessao

### Pontos tecnicos resolvidos no refactor

- reducao de acoplamento no dashboard com contratos tipados
- reducao de duplicacao em fluxos de execucao local/remota
- melhoria de robustez em parsing de analytics por arquivo e por bytes
- centralizacao de componentes de interface e graficos

### Performance, estado e escalabilidade

- fluxo incremental de progresso por frame/job
- filtros client-side eficientes para analytics
- possibilidade de escalar processamento para backend API
- gerenciamento de estado previsivel via `st.session_state`

### Acessibilidade, responsividade e SEO

- modo alto contraste
- modo de reducao de movimento
- layout responsivo e hierarquia visual clara
- SEO publico limitado por natureza do Streamlit (server-rendered app)

## UI/UX Refactor (nivel senior)

### Melhorias aplicadas

- design system com tokens visuais reutilizaveis
- componentes visuais consistentes para metricas e paines
- feedback de progresso em tempo real (local e remoto)
- comparativo entre run atual e run anterior
- charts de performance, timeline e distribuicao de severidade
- fluxo de exportacao direta de video, JSONL e CSV filtrado

### Microinteracoes e usabilidade

- feedback contextual em validacoes de zona
- mensagens operacionais durante execucao e polling remoto
- persistencia de historico da sessao para tomada de decisao

## Features Frontend Implementadas

1. Execucao dual: `Local Engine` e `Backend API`
2. Presets operacionais por contexto
3. Perfis salvos de configuracao (save/load)
4. Comparacao de resultados entre execucoes
5. Explorer de analytics com filtros multicriterio
6. Exportacao de artefatos e eventos filtrados

## Stack e Tecnologias

- Python 3.10+
- Streamlit
- Pandas
- Plotly
- Requests
- PyTest

## Estrutura do Projeto (frontend)

```text
src/ui/
├── __init__.py
├── dashboard.py
├── contracts.py
├── theme.py
├── components/
│   ├── __init__.py
│   └── panels.py
├── analytics.py
├── parsers.py
├── presets.py
├── profiles.py
├── insights.py
├── state.py
└── api_client.py
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

### 2. Executar frontend

```bash
streamlit run app.py
```

### 3. Opcional: executar backend para modo remoto

```bash
# Windows (exemplo)
set PIPELINE_API_KEYS=admin-key:admin,ops-key:operator,viewer-key:viewer
python server.py
```

## Build e Deploy

Como Streamlit nao usa bundle frontend tradicional, o deploy recomendado e:

1. containerizar frontend e backend separadamente
2. publicar API atras de proxy reverso
3. persistir runtime (`runtime/`) em volume dedicado
4. configurar variaveis de ambiente seguras para API keys

## Boas Praticas Adotadas

- separacao clara de responsabilidades
- componentes reutilizaveis e tokens visuais
- validacao de entrada antes do processamento
- contratos de dados consistentes
- fallback de visualizacao quando dependencias opcionais faltam
- testes automatizados para regressao

## Qualidade

```bash
python -m pytest tests -q
```

Status atual: **40 testes passando**.

## Melhorias Futuras

- comparador visual lado a lado entre duas execucoes
- persistencia de perfis em storage permanente
- notificacoes em tempo real para finalizacao de job remoto
- modo colaborativo multiusuario com permissao por workspace
- migracao para frontend SPA/SSR quando SEO publico for requisito critico

## Licenca

MIT. Consulte `LICENSE`.

Autoria: Matheus Siqueira  
Website: https://www.matheussiqueira.dev/

# Frontend Vision Studio

Frontend profissional para configuracao, execucao e analise de processamento de video com foco em usabilidade, acessibilidade, performance e escalabilidade operacional.

## Visao Geral do Frontend

O Frontend Vision Studio atende operadores e times tecnicos que precisam executar pipelines de video com controle visual e analitico.

### Publico-alvo
- analistas operacionais
- engenheiros de dados/visao computacional
- times de monitoramento e inteligencia

### Fluxo principal
1. upload de video
2. selecao de preset/perfil
3. validacao de zonas monitoradas
4. execucao local ou via backend API
5. leitura de resultados, comparacao de runs e exportacao

## Analise Tecnica do Frontend

### Arquitetura
A camada `src/ui` foi organizada por responsabilidades:

- `dashboard.py`: orquestracao da aplicacao
- `theme.py`: design tokens e estilos globais
- `components/panels.py`: componentes reutilizaveis
- `analytics.py`: parsing, filtro e sumarios
- `contracts.py`: contratos tipados de controle/payload
- `profiles.py`: gerenciamento de perfis salvos
- `insights.py`: comparador entre execucoes
- `video_advisor.py`: assistente de configuracao por metadados do video
- `api_client.py`: integracao com backend remoto
- `state.py`: estado de sessao

### Pontos de melhoria enderecados
- reducao de acoplamento no fluxo principal
- maior previsibilidade de estado
- reducao de duplicacao em configuracao e comparacao
- melhoria de feedback visual durante processamento

### Performance e escalabilidade
- parsing eficiente de analytics em memoria
- filtros client-side em DataFrame
- polling configuravel para jobs remotos
- suporte dual-run (local e backend), facilitando crescimento operacional

### Acessibilidade e responsividade
- modo alto contraste
- reducao de movimento
- foco visivel em elementos interativos
- layout responsivo e hierarquia visual consistente

### SEO
Por ser Streamlit, SEO indexavel publico e limitado por arquitetura server-side da ferramenta.

## UI/UX Refactor (Senior)

### Melhorias aplicadas
- design system com tokens e componentes consistentes
- cards de KPI, comparativo de execucoes e dashboards analiticos
- microinteracoes de feedback em validacoes e status de job
- experiencia orientada a operacao real (studio + analytics + history + review)

### Navegacao e interacao
- tabs dedicadas por contexto de uso
- perfis de configuracao (save/load)
- assistente de configuracao automatica por caracteristicas do video

## Features Implementadas

1. Execucao dual (`Local Engine` e `Backend API`)
2. Presets e perfis salvos de configuracao
3. Assistente inteligente de parametros (`video_advisor`)
4. Comparacao entre run atual e run anterior
5. Analytics explorer com filtros multicriterio
6. Exportacao de video, JSONL e CSV filtrado

## Stack e Tecnologias

- Python 3.10+
- Streamlit
- Pandas
- Plotly
- Requests
- OpenCV
- PyTest

## Estrutura do Projeto (frontend)

```text
src/ui/
├── __init__.py
├── dashboard.py
├── contracts.py
├── theme.py
├── state.py
├── presets.py
├── parsers.py
├── profiles.py
├── insights.py
├── video_advisor.py
├── analytics.py
├── api_client.py
└── components/
    ├── __init__.py
    └── panels.py
```

## Setup

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

## Execucao

### Frontend
```bash
streamlit run app.py
```

### Backend opcional (modo remoto)
```bash
set PIPELINE_API_KEYS=admin-key:admin,ops-key:operator,viewer-key:viewer
python server.py
```

## Build e Deploy

Streamlit nao possui etapa de bundle frontend tradicional.
Deploy recomendado:

1. containerizar frontend e backend separadamente
2. usar proxy reverso para API
3. persistir `runtime/` em volume
4. configurar API keys por ambiente

## Boas Praticas Adotadas

- separacao de responsabilidades
- contratos tipados para fluxos criticos
- componentes reutilizaveis e consistentes
- validacao de entrada e feedback contextual
- foco em acessibilidade e UX operacional
- testes automatizados para regressao

## Qualidade

```bash
python -m pytest tests -q
```

Status atual: **43 testes passando**.

## Melhorias Futuras

- comparador visual lado a lado entre duas execucoes
- persistencia de perfis em storage duravel
- notificacoes em tempo real para jobs remotos
- auditoria de acessibilidade automatizada no pipeline CI
- migracao para SPA/SSR quando SEO publico for prioridade

## Licenca

MIT. Consulte `LICENSE`.

Autoria: Matheus Siqueira  
Website: https://www.matheussiqueira.dev/

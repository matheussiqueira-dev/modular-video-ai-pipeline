# Modular Video AI Pipeline - Backend

Backend profissional para orquestracao de jobs de analise de video com API REST versionada, controle de acesso por papel, persistencia de metadados e entrega de artefatos processados.

## Visao Geral do Backend

Este backend oferece uma camada de servico para processamento de video orientado a jobs, com foco em confiabilidade operacional e evolucao para ambientes de producao.

### Dominio principal

- submissao de jobs de processamento de video
- acompanhamento de status/progresso
- leitura de eventos detectados
- download de artefatos (video anotado e telemetria)
- cancelamento e retry de jobs

### Objetivo de negocio

- reduzir friccao na operacao de pipelines de video
- padronizar execucao e observabilidade em um endpoint unico
- habilitar integracoes externas com contratos claros de API

## Arquitetura Adotada

Arquitetura modular (monolito modular), separada por camadas:

- `src/api/app.py`: camada HTTP (FastAPI), roteamento, middlewares e contratos
- `src/api/security.py`: autenticacao por API key, autorizacao e rate limiting
- `src/api/repository.py`: persistencia SQLite e consultas de jobs
- `src/api/service.py`: orquestracao de processamento de jobs
- `src/core/pipeline.py`: motor de pipeline de visao computacional

### Padroes aplicados

- Single Responsibility por modulo
- separacao entre camada de API, servico e persistencia
- validacao de entrada com Pydantic
- contratos de resposta tipados
- fluxo de erro consistente

## Recursos e Features Backend Implementadas

1. API REST versionada (`/api/v1`)
2. Autenticacao via `X-API-Key`
3. Autorizacao por papeis (`admin`, `operator`, `viewer`)
4. Rate limiting por API key (janela fixa)
5. Idempotencia em criacao de job (`X-Idempotency-Key`)
6. Cancelamento de jobs em execucao
7. Retry de jobs existentes
8. Filtros em listagem (`status`, `requested_by`)
9. Endpoint de metricas agregadas de jobs
10. Persistencia de metadados em SQLite + artefatos em filesystem

## Seguranca e Confiabilidade

### Autenticacao e autorizacao

- header obrigatorio: `X-API-Key`
- permissoes por papel:
  - `admin`: leitura/escrita de jobs e leitura de artefatos
  - `operator`: leitura/escrita de jobs e leitura de artefatos
  - `viewer`: somente leitura

### Protecoes implementadas

- validacao forte de payload e ranges de parametros
- validacao de formato de arquivo e limite de upload
- consultas SQL parametrizadas (mitigacao de SQL Injection)
- rate limiting para reduzir abuso de endpoints
- idempotencia para evitar criacao duplicada acidental
- headers de seguranca em respostas (`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`)

### Tratamento de erros e observabilidade

- middleware com `X-Request-ID`
- medicao de latencia por request (`X-Response-Time-Ms`)
- logging de metodo/path/status/duracao
- respostas de erro padronizadas

## Tecnologias Utilizadas

- Python 3.10+
- FastAPI
- Uvicorn
- Pydantic v2
- SQLite (`sqlite3`)
- OpenCV / NumPy (pipeline)
- PyTest

## Estrutura do Projeto (backend)

```text
src/
├── api/
│   ├── __init__.py
│   ├── app.py
│   ├── models.py
│   ├── repository.py
│   ├── schemas.py
│   ├── security.py
│   ├── service.py
│   ├── settings.py
│   └── validators.py
├── core/
│   ├── config.py
│   ├── exporters.py
│   └── pipeline.py
└── ...

server.py
tests/test_api.py
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

### 2. Variaveis de ambiente

```bash
# Obrigatorio para producao
PIPELINE_API_KEYS=admin-key:admin,ops-key:operator,viewer-key:viewer

# Opcionais
PIPELINE_RUNTIME_DIR=runtime
PIPELINE_API_WORKERS=2
PIPELINE_MAX_UPLOAD_MB=200
PIPELINE_RATE_LIMIT_REQUESTS=300
PIPELINE_RATE_LIMIT_WINDOW_SECONDS=60
```

### 3. Executar backend

```bash
python server.py
```

Documentacao interativa:

- Swagger: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Contrato de API

Base path: `/api/v1`

### Principais endpoints

- `GET /health`
- `POST /jobs`
- `GET /jobs`
- `GET /jobs/metrics`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/cancel`
- `POST /jobs/{job_id}/retry`
- `GET /jobs/{job_id}/events`
- `GET /jobs/{job_id}/artifacts/video`
- `GET /jobs/{job_id}/artifacts/analytics`

### Exemplo rapido (criar job)

```bash
curl -X POST "http://localhost:8000/api/v1/jobs" \
  -H "X-API-Key: admin-key" \
  -H "X-Idempotency-Key: run-001" \
  -F "file=@input.mp4" \
  -F "max_frames=300" \
  -F "fps=30" \
  -F "ocr_interval=20" \
  -F "clustering_interval=5" \
  -F "mock_mode=true" \
  -F "async_mode=true" \
  -F "zones_json=[{\"name\":\"gate\",\"x1\":10,\"y1\":10,\"x2\":200,\"y2\":300}]"
```

## Qualidade e Testes

```bash
python -m pytest tests -q
```

Status atual: **48 testes passando**.

## Boas Praticas e Padroes

- arquitetura modular e orientada a camadas
- contratos versionados de API
- idempotencia para operacoes criticas
- controle de acesso por permissao
- rate limiting e validacao estrita de entrada
- persistencia de estado para rastreabilidade
- testes automatizados cobrindo fluxo principal e casos de seguranca

## Melhorias Futuras

- fila distribuida (Redis + workers dedicados)
- armazenamento de artefatos em object storage (S3/MinIO)
- observabilidade avancada (OpenTelemetry + Prometheus)
- autenticacao OAuth2/JWT para cenarios multi-tenant
- politica de retencao/limpeza automatica de artefatos

## Licenca

MIT. Consulte `LICENSE`.

Autoria: Matheus Siqueira  
Website: https://www.matheussiqueira.dev/

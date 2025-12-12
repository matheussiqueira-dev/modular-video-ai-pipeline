# 🎯 Pipeline Modular de IA para Vídeo

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/matheussiqueirahub/modular-video-ai-pipeline/graphs/commit-activity)

Um **pipeline modular de visão computacional pronto para produção** para análise avançada de vídeo. Integra modelos de IA de última geração para detecção de objetos, segmentação, rastreamento, agrupamento, OCR e detecção de eventos—adaptável para **análise esportiva, segurança, varejo e vigilância**.

---

## 🌟 Recursos

✨ **Arquitetura Modular** - Separação clara de responsabilidades com componentes plugáveis  
🔍 **Processamento Multi-Estágio** - Detecção → Segmentação → Rastreamento → Agrupamento → OCR → Eventos  
🎨 **Visualização Rica** - Vídeos anotados com caixas delimitadoras, máscaras, IDs e sobreposições de eventos  
🚀 **Modo Mock** - Teste o pipeline sem baixar modelos pesados  
🔧 **Extensível** - Fácil adaptação para diferentes domínios e casos de uso  
📊 **Detecção de Eventos** - Análise temporal para anomalias (tempo de permanência, entrada em zona, proximidade)  

---

## 🏗️ Arquitetura

```mermaid
graph LR
    A[Entrada de Vídeo] --> B[Detecção RF-DETR]
    B --> C[Segmentação SAM2]
    C --> D[Rastreamento]
    D --> E[Agrupamento SigLIP]
    E --> F[OCR SmolVLM2]
    F --> G[Homografia]
    G --> H[Detecção de Eventos]
    H --> I[Visualização]
    I --> J[Vídeo de Saída]
```

### Estágios do Pipeline

| Estágio | Modelo/Tecnologia | Propósito |
|---------|-------------------|-----------|
| **Detecção** | RF-DETR | Detectar pessoas e objetos nos frames |
| **Segmentação** | SAM2 | Gerar máscaras precisas para objetos rastreados |
| **Rastreamento** | SAM2 Video | Manter IDs consistentes entre frames |
| **Agrupamento** | SigLIP + UMAP + K-Means | Agrupar objetos por similaridade visual |
| **OCR** | SmolVLM2 | Ler texto de objetos (números, placas) |
| **Homografia** | OpenCV | Mapear coordenadas para vista superior |
| **Eventos** | Máquina de Estados | Detectar padrões temporais e anomalias |
| **Visualização** | Supervision | Anotações ricas de frames |

---

## 🚀 Início Rápido

### Pré-requisitos

- **Python 3.10+**
- **GPU CUDA** (recomendado para modelos reais)
- **Git**

### Instalação

```bash
# Clone o repositório
git clone https://github.com/matheussiqueirahub/modular-video-ai-pipeline.git
cd modular-video-ai-pipeline

# Instale as dependências
pip install -r requirements.txt
```

### Uso

#### Executar em Modo Mock (Sem Pesos de Modelo)

```bash
python demo.py --mock --output_path demo_output.mp4
```

#### Executar com Seu Próprio Vídeo

```bash
python demo.py --video_path input.mp4 --output_path result.mp4
```

#### Opções Avançadas

```bash
python demo.py \
  --video_path jogo_esportivo.mp4 \
  --output_path jogo_analisado.mp4 \
  --debug
```

---

## 📁 Estrutura do Projeto

```
ai_vision_pipeline/
├── demo.py                    # Script principal do pipeline
├── requirements.txt           # Dependências Python
├── README.md                  # Este arquivo
├── tests/                     # Testes unitários
│   ├── test_detector.py
│   ├── test_segmenter.py
│   └── test_clustering.py
└── src/
    ├── detection/
    │   └── detector.py        # Wrapper RF-DETR
    ├── segmentation/
    │   └── segmenter.py       # Segmentação de vídeo SAM2
    ├── clustering/
    │   └── identifier.py      # SigLIP + agrupamento
    ├── ocr/
    │   └── reader.py          # Reconhecimento de texto SmolVLM2
    ├── homography/
    │   └── transformer.py     # Transformação de perspectiva
    ├── events/
    │   └── analyzer.py        # Motor de detecção de eventos
    └── visualization/
        └── drawer.py          # Anotação de frames
```

---

## 🎓 Casos de Uso

### 🏀 Análise Esportiva
- Rastrear jogadores e posições da bola
- Identificar times por cor de uniforme
- Ler números de jogadores com OCR
- Detectar eventos-chave (gols, faltas)

### 🏪 Inteligência de Varejo
- Contar clientes em zonas
- Rastrear tempo de permanência perto de produtos
- Identificar funcionários vs. clientes
- Detectar formação de filas

### 🔒 Segurança e Vigilância
- Rastrear indivíduos entre câmeras
- Detectar comportamento suspeito ou vagância
- Ler placas de veículos
- Alertar sobre violações de entrada em zona

---

## 🧪 Executando Testes

```bash
# Executar todos os testes
python -m pytest tests/ -v

# Executar testes de módulo específico
python -m pytest tests/test_detector.py -v
```

---

## 🔧 Transição para Modelos Reais

O pipeline executa em **Modo Mock** por padrão. Para usar modelos de IA reais:

1. **Instalar PyTorch**:
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```

2. **Instalar Transformers**:
   ```bash
   pip install transformers accelerate timm
   ```

3. **Descomentar carregamento de modelo** em cada módulo (`src/*/`)

4. **Baixar pesos** (modelos serão baixados automaticamente na primeira execução)

---

## 📊 Performance

| Modo | FPS (RTX 3090) | Uso de Memória |
|------|----------------|----------------|
| Modo Mock | 30+ fps | ~500 MB |
| Pipeline Completo | 5-10 fps | ~8 GB VRAM |

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Por favor:

1. Faça um fork do repositório
2. Crie um branch de feature (`git checkout -b feature/funcionalidade-incrivel`)
3. Commite suas mudanças (`git commit -m 'Adiciona funcionalidade incrível'`)
4. Faça push para o branch (`git push origin feature/funcionalidade-incrivel`)
5. Abra um Pull Request

---

## 📝 Licença

Este projeto está licenciado sob a Licença MIT - veja o arquivo [LICENSE](LICENSE) para detalhes.

---

## 🙏 Agradecimentos

- **RF-DETR** - Transformer de detecção em tempo real
- **SAM2** - Segment Anything Model 2 para vídeo
- **SigLIP** - CLIP melhorado para embeddings visuais
- **SmolVLM2** - Modelo leve de visão-linguagem
- **Supervision** - Utilitários de visão computacional

---

## 📧 Contato

**Matheus Siqueira** - [@matheussiqueirahub](https://github.com/matheussiqueirahub)

**Link do Projeto**: https://github.com/matheussiqueirahub/modular-video-ai-pipeline

---

⭐ **Dê uma estrela neste repositório** se você achou útil!

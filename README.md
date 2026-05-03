# 🎙️ Dublando — Tradução ao Vivo em Tempo Real

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Chrome](https://img.shields.io/badge/Chrome-requerido-yellow?logo=googlechrome&logoColor=white)
![Status](https://img.shields.io/badge/status-ativo-brightgreen)

> Sistema de tradução ao vivo que captura áudio do Chrome, transcreve com a API de reconhecimento de fala do navegador e traduz para o português em tempo real — tudo sem nuvem, sem servidor externo e sem bibliotecas pesadas.

---

## 📋 Sumário

- [Visão Geral](#-visão-geral)
- [Recursos Principais](#-recursos-principais)
- [Requisitos](#-requisitos)
- [Instalação](#-instalação)
- [Início Rápido](#-início-rápido)
- [Como Usar](#-como-usar)
- [Opções de Linha de Comando](#-opções-de-linha-de-comando)
- [Arquitetura](#-arquitetura)
- [Limitações](#-limitações)
- [Troubleshooting](#-troubleshooting)
- [Contribuindo](#-contribuindo)
- [FAQ](#-faq)

---

## 🔭 Visão Geral

**Dublando** é um programa Python com interface gráfica (GUI) que atua como uma ponte entre o Chrome e o usuário. Ele serve uma página local que usa as APIs nativas do navegador para:

1. **Capturar** o áudio do sistema ou de uma aba específica do Chrome via `getDisplayMedia`.
2. **Transcrever** a fala em texto usando a `Web Speech API` (STT nativo do Chrome).
3. **Traduzir** o texto para português usando a `Translator API` experimental do Chrome.
4. **Exibir** os resultados ao vivo na GUI Python e salvar o histórico em TXT ou JSON.

Este projeto parte do `apps/09-live-translation-gui` e incorpora a lógica da extensão **Fofoqueiro Dublado**.

---

## ✨ Recursos Principais

| Recurso | Descrição |
|---|---|
| 🎯 **Detecção automática de idioma** | Identifica o idioma pelo texto reconhecido, sem configuração manual |
| 🔄 **Bypass para português** | Evita tradução desnecessária `pt → pt` |
| ⚡ **Filas por idioma** | Gerencia múltiplas filas de tradução simultaneamente |
| 🗑️ **Descarte de respostas antigas** | Garante que apenas a resposta mais recente seja exibida |
| ✂️ **Segmentação inteligente** | Divide por estabilidade, tamanho e silêncio real via `AudioContext` |
| 🛑 **Hard stop limpo** | Para tudo com `abort()`, encerra tracks, limpa timers e fecha `AudioContext` |
| 🔒 **100% local** | Sem Whisper, sem backend externo, sem nuvem, sem bibliotecas pesadas |

---

## ⚙️ Requisitos

- **Python 3.10** ou superior
- **Google Chrome** (versão recente — recomendado Canary ou Dev para APIs experimentais)
- Sistema operacional **Windows** (testado principalmente no Windows 10/11)
- Nenhuma dependência Python adicional (usa apenas a biblioteca padrão: `tkinter`, `http.server`, etc.)

### Flags do Chrome necessárias

Para usar as APIs experimentais de STT com captura de áudio e a Translator API, habilite as seguintes flags em `chrome://flags`:

| Flag | Valor |
|---|---|
| `#enable-experimental-web-platform-features` | **Enabled** |
| `#translation-api` | **Enabled** |
| `#language-detection-api` | **Enabled** |

---

## 📦 Instalação

Não há instalação de pacotes — basta ter Python 3.10+ e Chrome instalados.

```bash
# Clone o repositório
git clone https://github.com/sonyddr666/dublando.git

# Entre na pasta do projeto
cd dublando
```

---

## 🚀 Início Rápido

```bash
# Iniciar a GUI (abrir o Chrome manualmente depois)
python windows_audio_stt_gui.py

# Iniciar a GUI e abrir o Chrome automaticamente
python windows_audio_stt_gui.py --open
```

Acesse a página de controle em:

```
http://127.0.0.1:8799/
```

---

## 🎯 Como Usar

### Passo a passo completo

**1.** Execute o programa Python:
```bash
python windows_audio_stt_gui.py --open
```

**2.** A janela da GUI Python abrirá. Clique em **`Abrir Chrome`** se não usou `--open`.

**3.** Na página do Chrome, clique em **`Capturar áudio`** e escolha a fonte:

| Opção | Quando usar | Observação |
|---|---|---|
| `Tela inteira` | Capturar o áudio de todo o sistema | Marque **Compartilhar áudio do sistema** |
| `Aba do Chrome` | Capturar apenas uma aba específica | Marque **Compartilhar áudio da aba** |

**4.** Aguarde o Chrome solicitar permissão de compartilhamento de tela/áudio e aceite.

**5.** A tradução iniciará automaticamente:

- **`Parcial ao vivo`** — texto original sendo reconhecido em tempo real
- **`Português ao vivo`** — tradução para português em tempo real
- **`Finais salvos`** — blocos de texto já processados e confirmados

**6.** Para salvar o histórico, use os botões:
- **`Salvar TXT`** — exporta o histórico em texto simples
- **`Salvar JSON`** — exporta com metadados (idioma detectado, timestamps, etc.)
- **`Copiar`** — copia tudo para a área de transferência

**7.** Para parar a captura, clique em **`Parar`** na página do Chrome.

---

## 🔧 Opções de Linha de Comando

```bash
python windows_audio_stt_gui.py [opções]
```

| Opção | Padrão | Descrição |
|---|---|---|
| `--open` | desativado | Abre o Chrome automaticamente ao iniciar |
| `--port PORTA` | `8799` | Porta do servidor HTTP local |

**Exemplos:**

```bash
# Usar porta alternativa
python windows_audio_stt_gui.py --port 8800

# Abrir Chrome na porta personalizada
python windows_audio_stt_gui.py --open --port 8800
```

---

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────┐
│              GUI Python (Tkinter)            │
│   Janela principal · Histórico · Arquivos   │
│                   :8799                      │
└──────────────┬──────────────────────────────┘
               │  HTTP (localhost)
               ▼
┌─────────────────────────────────────────────┐
│           Servidor HTTP Embutido             │
│      (http.server — biblioteca padrão)      │
│  Serve HTML/JS · Recebe eventos via POST    │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────┐
│        Página Web no Chrome (HTML/JS)        │
│                                              │
│  ┌─────────────────┐  ┌──────────────────┐  │
│  │  getDisplayMedia │  │  Web Speech API  │  │
│  │  (captura áudio) │  │  (STT nativo)    │  │
│  └────────┬────────┘  └───────┬──────────┘  │
│           │                   │              │
│           └─────────┬─────────┘              │
│                     ▼                        │
│            ┌─────────────────┐               │
│            │  Translator API │               │
│            │  (Chrome nativo)│               │
│            └────────┬────────┘               │
│                     │ POST → GUI Python       │
└─────────────────────┼───────────────────────┘
                      ▼
               Resultado exibido
              na janela Tkinter
```

**Responsabilidades:**

- **Python**: Interface gráfica, servidor HTTP local, gerenciamento de histórico, exportação de arquivos.
- **Chrome/JS**: Captura de áudio (`getDisplayMedia`), reconhecimento de fala (`SpeechRecognition`), tradução (`Translator API`).

---

## ⚠️ Limitações

- **`SpeechRecognition.start(audioTrack)`** ainda depende de suporte experimental do Chrome — pode não funcionar em versões estáveis.
- **`Translator API`** pode exigir o download manual do pacote de idiomas; clique em **`Preparar tradutor PT`** na página do Chrome antes de usar.
- **`isFinal` do STT** não garante uma frase completa; a segmentação da versão 10 tenta compensar isso.
- **Captura de janela específica** pode não incluir áudio dependendo da versão do Chrome e da fonte de áudio.
- O programa foi testado principalmente no **Windows 10/11**; compatibilidade com macOS/Linux não é garantida.

---

## 🆘 Troubleshooting

### ❌ "Nenhum áudio sendo capturado"
- Verifique se marcou **Compartilhar áudio do sistema** (tela inteira) ou **Compartilhar áudio da aba** ao aceitar o compartilhamento.
- Confirme que o Chrome tem as flags experimentais habilitadas em `chrome://flags`.

### ❌ "Tradução não aparece"
- Clique em **`Preparar tradutor PT`** na página do Chrome e aguarde o download do pacote de idiomas.
- Verifique se a flag `#translation-api` está ativada.

### ❌ "Erro ao iniciar o servidor"
- A porta `8799` pode estar em uso. Use `--port 8800` (ou outra porta livre).

### ❌ "Chrome não abre automaticamente"
- Verifique se o Chrome está instalado e no PATH do sistema.
- Abra manualmente em `http://127.0.0.1:8799/`.

### ❌ "GUI Python não abre"
- Confirme que o Python 3.10+ está instalado: `python --version`
- No Windows, `tkinter` já vem incluído na instalação padrão do Python.

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Para contribuir:

1. Faça um **fork** do repositório
2. Crie uma branch para sua feature: `git checkout -b feature/minha-feature`
3. Faça commit das suas alterações: `git commit -m 'feat: adiciona minha feature'`
4. Envie para a branch: `git push origin feature/minha-feature`
5. Abra um **Pull Request**

---

## ❓ FAQ

**O projeto funciona sem internet?**
> Sim! Toda a tradução é feita localmente pelo Chrome usando a Translator API nativa. Não há chamadas a serviços externos.

**Funciona com qualquer idioma?**
> Sim, desde que o Chrome consiga detectar e reconhecer o idioma com a Web Speech API. O sistema detecta automaticamente e traduz para português.

**Precisa instalar extensões no Chrome?**
> Não. A página servida pelo Python usa apenas APIs web padrão (experimentais) do Chrome.

**Por que usar Chrome e não Firefox/Edge?**
> A `Translator API` e o suporte a `SpeechRecognition` com `audioTrack` são recursos atualmente disponíveis apenas no Chromium/Chrome.

**O histórico é salvo automaticamente?**
> Os blocos finalizados ficam na seção `Finais salvos` enquanto o programa está aberto. Use **`Salvar TXT`** ou **`Salvar JSON`** para persistir o histórico em arquivo.

---

> **Nota:** Este projeto usa APIs experimentais do Chrome que podem mudar ou ser descontinuadas. Sempre use a versão mais recente do Chrome (Canary ou Dev recomendado para melhor compatibilidade).


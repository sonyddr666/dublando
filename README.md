# 🎬 Live Translation GUI 10

Programa Python com GUI para transcrever áudio capturado pelo Chrome e traduzir para português em tempo real.

## 🎯 Sobre

Esta versão evolui a partir do `apps/09-live-translation-gui` e incorpora a lógica atual da extensão `Fofoqueiro Dublado`, oferecendo:

- ✅ Detecção automática de idioma pelo texto reconhecido
- ✅ Bypass seguro para português (evita traduzir pt → pt desnecessariamente)
- ✅ Filas de tradução organizadas por idioma
- ✅ Tradução ao vivo com descarte inteligente de respostas antigas
- ✅ Segmentação por estabilidade, tamanho e silêncio real via `AudioContext`
- ✅ Parada forçada com `abort()`, limpeza de tracks, timers e fechamento de `AudioContext`

## 🔧 Stack Tecnológico

- **Backend**: Python puro (interface, histórico, gerenciamento de arquivos)
- **Frontend**: Chrome com APIs nativas (captura de áudio, STT, tradução)
- **Sem dependências externas**: Whisper, backends externos ou APIs em nuvem

## 🚀 Quick Start

### Executar o programa

```bash
python windows_audio_stt_gui.py
```

### Executar e abrir Chrome automaticamente

```bash
python windows_audio_stt_gui.py --open
```

## ⚙️ Configuração

### Porta Padrão
```
http://127.0.0.1:8799/
```

### Alterar Porta
```bash
python windows_audio_stt_gui.py --port 8800
```

## 📖 Como Usar

1. Clique em **`Abrir Chrome`** no programa Python
2. Na página do Chrome, clique em **`Capturar áudio`**
3. Escolha a origem do áudio:
   - **Tela inteira**: Selecione `Tela inteira` e marque `Compartilhar audio do sistema`
   - **Aba específica**: Selecione `Aba do Chrome` e marque `Compartilhar audio da aba`
4. Acompanhe em tempo real:
   - **`Parcial ao vivo`**: Transcrição original
   - **`Português ao vivo`**: Tradução em português
5. Gerencie os blocos salvos em **`Finais salvos`**
6. Exporte os dados:
   - Clique em `Salvar TXT` para arquivo de texto
   - Clique em `Salvar JSON` para arquivo estruturado
   - Clique em `Copiar` para copiar para a área de transferência

## ⚠️ Limitações Conhecidas

- `SpeechRecognition.start(audioTrack)` depende do suporte experimental do Chrome
- `Translator API` pode exigir preparação manual via clique em `Preparar tradutor PT`
- `isFinal` do STT não garante uma frase perfeita; a v10 melhora isso com segmentação avançada
- Captura de janela específica pode não funcionar em todos os navegadores/sistemas, dependendo da fonte de áudio

## 📝 Notas

Este projeto é idealmente desenvolvido e testado em Windows com suporte de captura de áudio do sistema.

## 📄 Licença

[Adicione informações de licença, se aplicável]

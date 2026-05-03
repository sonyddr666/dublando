# Live Translation GUI 10

Programa Python com GUI para transcrever audio capturado pelo Chrome e traduzir para portugues ao vivo.

Esta versao parte do `apps/09-live-translation-gui` e incorpora a logica atual da extensao `Fofoqueiro Dublado`:

- deteccao de idioma pelo texto reconhecido;
- bypass seguro para portugues, sem tentar `pt -> pt` quando o texto parece outro idioma;
- filas de tradutor por idioma;
- traducao ao vivo com descarte de respostas antigas;
- segmentacao por estabilidade, tamanho e silencio real via `AudioContext`;
- hard stop com `abort()`, parada de tracks, limpeza de timers e fechamento de `AudioContext`.

Nao usa Whisper, backend externo, nuvem nem biblioteca externa. O Python cuida da janela, historico e arquivos. O Chrome faz captura, STT e traducao com APIs do navegador.

## Como Rodar

```txt
python windows_audio_stt_gui.py
```

Ou ja abrindo o Chrome:

```txt
python windows_audio_stt_gui.py --open
```

## Porta Padrao

```txt
http://127.0.0.1:8799/
```

Pode trocar:

```txt
python windows_audio_stt_gui.py --port 8800
```

## Como Usar

1. Clique em `Abrir Chrome` no programa Python.
2. Na pagina do Chrome, clique em `Capturar audio`.
3. Para PC inteiro, escolha `Tela inteira` e marque `Compartilhar audio do sistema`.
4. Para uma aba, escolha `Aba do Chrome` e marque `Compartilhar audio da aba`.
5. O original aparece em `Parcial ao vivo`.
6. O portugues aparece em `Portugues ao vivo`.
7. Os blocos salvos ficam em `Finais salvos`.
8. Use `Salvar TXT`, `Salvar JSON` ou `Copiar`.

## Limitacoes

- `SpeechRecognition.start(audioTrack)` ainda depende do suporte experimental do Chrome.
- `Translator API` pode exigir preparo manual do pacote via clique em `Preparar tradutor PT`.
- `isFinal` do STT nao significa frase perfeita; a versao 10 tenta melhorar isso com a mesma segmentacao usada na extensao.
- Captura de janela especifica pode nao trazer audio dependendo do Chrome e da fonte.

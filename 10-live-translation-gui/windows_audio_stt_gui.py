from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, filedialog, messagebox, ttk
import tkinter as tk
from typing import Any
from urllib.parse import parse_qs, urlparse


HOST = "127.0.0.1"
PORT = 8799
DEFAULT_LANG = "auto"
WINDOW_WIDTH = 760
WINDOW_HEIGHT = 620
BRIDGE_PROCESSES: list[subprocess.Popen[Any]] = []


HTML_TEMPLATE = r'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Live Translation Bridge 10</title>
  <style>
    * { box-sizing: border-box; }
    html, body { min-height: 100%; }
    body {
      margin: 0;
      background: #0b1020;
      color: #e5edf7;
      font-family: Segoe UI, Arial, sans-serif;
      padding: 10px;
    }
    main {
      max-width: 760px;
      margin: 0 auto;
      display: grid;
      gap: 8px;
    }
    .card {
      border: 1px solid #263449;
      border-radius: 14px;
      background: #111827;
      padding: 10px;
      box-shadow: 0 14px 40px rgba(0, 0, 0, 0.28);
    }
    h1 { margin: 0 0 4px; font-size: 18px; }
    p { margin: 4px 0; color: #a7b4c7; line-height: 1.35; }
    .row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
    button, select, label.toggle {
      min-height: 38px;
      border-radius: 10px;
      border: 1px solid #334155;
      background: #0f172a;
      color: #f8fafc;
      font: inherit;
    }
    button { padding: 0 12px; font-weight: 800; cursor: pointer; }
    button.primary { background: #075985; border-color: #38bdf8; }
    button.stop { background: #7f1d1d; border-color: #ef4444; }
    select { padding: 0 10px; }
    label.toggle { display: inline-flex; align-items: center; gap: 8px; padding: 0 10px; }
    #status {
      display: inline-flex;
      align-items: center;
      min-height: 34px;
      border-radius: 999px;
      padding: 0 10px;
      border: 1px solid #334155;
      color: #a7b4c7;
      font-size: 13px;
      font-weight: 800;
    }
    #partial, #final, #log {
      border: 1px solid #263449;
      border-radius: 12px;
      background: #060b16;
      padding: 12px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      word-break: break-word;
      line-height: 1.45;
    }
    #partial { min-height: 82px; color: #c7f0ff; font-size: 18px; }
    #liveTranslation { min-height: 82px; color: #fef3c7; font-size: 18px; }
    #final { min-height: 150px; max-height: 230px; overflow: auto; color: #f8fafc; }
    #log { max-height: 100px; overflow: auto; color: #a7b4c7; font-size: 12px; }
    .hint { font-size: 13px; color: #93a4ba; }
    .warn { color: #fde68a; }
  </style>
</head>
<body>
  <main>
    <section class="card">
      <h1>Live Translation Bridge 10</h1>
      <p>Captura audio pelo Chrome, transcreve e traduz para portugues ao vivo.</p>
      <p class="warn">Para audio do PC inteiro: escolha "Tela inteira" no seletor do Chrome e marque "Compartilhar audio do sistema" quando aparecer.</p>
      <p class="hint">Para audio de uma aba: escolha "Aba do Chrome" e marque "Compartilhar audio da aba".</p>
    </section>

    <section class="card">
      <div class="row">
        <button id="start" class="primary" type="button">Capturar audio</button>
        <button id="stop" class="stop" type="button">Parar</button>
        <select id="lang">
          <option value="auto">Auto detectar idioma</option>
          <option value="en-US">en-US</option>
          <option value="pt-BR">pt-BR</option>
          <option value="es-ES">es-ES</option>
          <option value="fr-FR">fr-FR</option>
          <option value="de-DE">de-DE</option>
          <option value="ja-JP">ja-JP</option>
          <option value="zh-CN">zh-CN</option>
          <option value="ko-KR">ko-KR</option>
          <option value="ru-RU">ru-RU</option>
        </select>
        <select id="translatorSource" title="Origem da traducao">
          <option value="auto">origem auto</option>
          <option value="en">en -> pt</option>
          <option value="ja">ja -> pt</option>
          <option value="zh">zh -> pt</option>
          <option value="ko">ko -> pt</option>
          <option value="es">es -> pt</option>
          <option value="fr">fr -> pt</option>
          <option value="de">de -> pt</option>
          <option value="ru">ru -> pt</option>
          <option value="pt">pt</option>
        </select>
        <button id="prepareTranslator" type="button">Preparar tradutor PT</button>
        <label class="toggle"><input id="preferLocal" type="checkbox"> STT local se ja estiver instalado</label>
        <span id="status">parado</span>
      </div>
    </section>

    <section class="card">
      <strong>Parcial ao vivo</strong>
      <div id="partial"></div>
    </section>

    <section class="card">
      <strong>Português ao vivo</strong>
      <div id="liveTranslation"></div>
    </section>

    <section class="card">
      <strong>Finais</strong>
      <div id="final"></div>
    </section>

    <section class="card">
      <strong>Logs</strong>
      <div id="log"></div>
    </section>
  </main>

  <script>
    const DEFAULT_LANG = __DEFAULT_LANG_JSON__;
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    const startBtn = document.querySelector("#start");
    const stopBtn = document.querySelector("#stop");
    const langEl = document.querySelector("#lang");
    const translatorSourceEl = document.querySelector("#translatorSource");
    const prepareTranslatorBtn = document.querySelector("#prepareTranslator");
    const preferLocalEl = document.querySelector("#preferLocal");
    const statusEl = document.querySelector("#status");
    const partialEl = document.querySelector("#partial");
    const liveTranslationEl = document.querySelector("#liveTranslation");
    const finalEl = document.querySelector("#final");
    const logEl = document.querySelector("#log");

    let stream = null;
    let outputContext = null;
    let audioAnalyser = null;
    let audioAnalyserData = null;
    let audioTrack = null;
    let recognition = null;
    let listening = false;
    let active = false;
    let restartTimer = null;
    let startFailures = 0;
    let interimTimer = null;
    let pendingInterim = "";
    let finalCount = 0;
    let useLocalSpeech = false;
    let translator = null;
    let translatorSource = "";
    let translatorTarget = "pt";
    let translatorInitPromise = null;
    let translatorQueues = new Map();
    let lastDetectedSource = sourceFromSpeechLang(DEFAULT_LANG);
    let closePollTimer = null;
    let browserFinals = [];
    let pendingTranslations = new Map();
    let pendingTranslationRetryTimer = null;
    let liveTranslationTimer = null;
    let liveTranslationSeq = 0;
    let liveTranslationLastText = "";
    let liveLastRequestedText = "";
    let livePreviewDisabled = false;
    let liveTranslateInFlight = false;
    let liveLatestText = "";
    let livePendingText = "";
    let partialCommitTimer = null;
    let currentUtteranceCommittedText = "";
    let lastPartialText = "";
    let lastPartialChangedAt = 0;
    let lockedTextLanguage = "";
    let languageScores = {};
    let silenceMonitorTimer = null;
    let audioRms = 0;
    let noiseFloor = 0.012;
    let lastAudioSpeechAt = 0;
    let currentSilenceMs = 0;
    let currentStartId = 0;
    let suppressNextEndRestart = false;

    const LIVE_MIN_WORDS = 1;
    const LIVE_FORCE_WORDS = 4;
    const LIVE_MIN_CJK_CHARS = 1;
    const LIVE_FORCE_CJK_CHARS = 8;
    const LIVE_STABLE_DELAY_MS = 0;
    const TRANSLATOR_SETUP_REQUIRED = "TRANSLATOR_SETUP_REQUIRED";
    const FINAL_CHUNK_MAX_CJK_CHARS = 80;
    const FINAL_CHUNK_MAX_LATIN_CHARS = 180;
    const PARTIAL_SILENCE_COMMIT_MS = 850;
    const PARTIAL_FORCE_CJK_CHARS = 55;
    const PARTIAL_FORCE_LATIN_CHARS = 150;
    const SILENCE_MONITOR_MS = 50;
    const SHORT_PAUSE_MS = 450;
    const PHRASE_PAUSE_MS = 850;
    const LONG_PAUSE_MS = 1300;
    const STABLE_TEXT_MS = 420;

    langEl.value = DEFAULT_LANG;

    function effectiveSpeechLang() {
      return langEl.value === "auto" ? "en-US" : langEl.value;
    }

    function nowTime() {
      return new Date().toLocaleTimeString();
    }

    function addLog(text) {
      logEl.textContent += `[${nowTime()}] ${text}\n`;
      logEl.scrollTop = logEl.scrollHeight;
    }

    function setStatus(text) {
      statusEl.textContent = text;
      send({ type: "state", text });
    }

    function send(payload) {
      fetch("/event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          lang: langEl.value,
          speechLang: effectiveSpeechLang(),
          ts: new Date().toISOString(),
          ...payload
        })
      }).catch(() => {});
    }

    async function pollCommand() {
      try {
        const response = await fetch("/command", { cache: "no-store" });
        const command = await response.json();

        if (command.close) {
          stopCapture(true);
          window.close();
        }
      } catch (_) {}
    }

    function normalizeSpeechText(text) {
      return String(text || "").replace(/\s+/g, " ").trim();
    }

    function countWords(text) {
      const normalized = normalizeSpeechText(text);
      return normalized ? normalized.split(" ").length : 0;
    }

    function hasCjkText(text) {
      return /[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af\u1100-\u11ff]/.test(String(text || ""));
    }

    function hasJapaneseKana(text) {
      return /[\u3040-\u30ff]/.test(String(text || ""));
    }

    function hasHangul(text) {
      return /[\uac00-\ud7af\u1100-\u11ff]/.test(String(text || ""));
    }

    function hasCyrillic(text) {
      return /[\u0400-\u04ff]/.test(String(text || ""));
    }

    function hasHanText(text) {
      return /[\u3400-\u4dbf\u4e00-\u9fff]/.test(String(text || ""));
    }

    function countCjkUnits(text) {
      return String(text || "").replace(/[\s\p{P}\p{S}]/gu, "").length;
    }

    function looksPortuguese(text) {
      const normalized = normalizeSpeechText(text).toLowerCase();
      if (!normalized || hasCjkText(normalized)) return false;

      const strongMatches = normalized.match(/[ãõáéíóúâêôç]|\b(você|voce|vocês|voces|não|nao|nós|nos|está|esta|estão|estao|também|tambem|então|entao|porque|quando|hoje|sobre|coisa|coisas|gente|aqui|agora|assim|isso|esse|essa|esses|essas|para|pra|com|uma|uns|das|dos)\b/g) || [];
      const weakMatches = normalized.match(/\b(o|a|os|as|de|da|do|das|dos|que|em|um|uma|e|é|eu|ele|ela|eles|elas|nós|nos|se|por|como|mais|mas)\b/g) || [];
      return strongMatches.length >= 1 || weakMatches.length >= 5;
    }

    function resetLanguageMemory() {
      lockedTextLanguage = "";
      languageScores = { pt: 0, en: 0, es: 0, ja: 0, zh: 0, ko: 0, ru: 0, fr: 0, de: 0 };
    }

    function sourceFromSpeechLang(lang) {
      const map = {
        en: "en", pt: "pt", es: "es", fr: "fr", de: "de", ja: "ja", zh: "zh", ko: "ko", ru: "ru",
        "en-US": "en", "pt-BR": "pt", "es-ES": "es", "fr-FR": "fr", "de-DE": "de",
        "ja-JP": "ja", "zh-CN": "zh", "ko-KR": "ko", "ru-RU": "ru"
      };
      return map[lang] || String(lang || "").split("-")[0] || "en";
    }

    function detectTextLanguage(text) {
      const normalized = normalizeSpeechText(text).toLowerCase();
      if (!normalized) return { language: "", confidence: 0 };

      if (hasHangul(normalized)) return { language: "ko", confidence: 10 };
      if (hasCyrillic(normalized)) return { language: "ru", confidence: 10 };
      if (hasJapaneseKana(normalized)) return { language: "ja", confidence: 10 };
      if (hasHanText(normalized)) return { language: lockedTextLanguage === "ja" ? "ja" : "zh", confidence: 4 };

      const score = { pt: 0, en: 0, es: 0, fr: 0, de: 0 };
      const addMatches = (language, regex, weight) => {
        const matches = normalized.match(regex);
        if (matches) score[language] += matches.length * weight;
      };

      addMatches("pt", /[ãõç]|\b(você|voce|vocês|voces|não|nao|nós|nos|então|entao|também|tambem|está|esta|estão|estao|pra|porque|quando|hoje|agora|coisa|coisas|gente|aqui|isso|essa|esse)\b|ções|ção|ões/g, 3);
      addMatches("pt", /\b(o|a|os|as|de|da|do|das|dos|que|em|um|uma|e|é|eu|ele|ela|eles|elas|se|por|como|mais|mas|para|com)\b/g, 0.7);
      addMatches("en", /\b(the|and|you|that|with|this|what|when|because|about|from|have|will|would|should|can|could|not|are|is|was|were|going|today|actually|basically|every|word|spoken)\b/g, 1.5);
      addMatches("es", /\b(qué|que|los|las|una|uno|está|esta|están|estan|pero|porque|cuando|sobre|ahora|usted|ustedes|nosotros|también|tambien)\b/g, 1.4);
      addMatches("fr", /\b(avec|vous|nous|mais|pourquoi|quand|dans|une|des|est|sont|être|etre)\b/g, 1.3);
      addMatches("de", /\b(und|ich|du|sie|wir|nicht|mit|das|der|die|ein|eine|wenn|aber|weil)\b/g, 1.3);

      const best = Object.entries(score).sort((a, b) => b[1] - a[1])[0];
      if (!best || best[1] < 2.5) return { language: "", confidence: 0 };
      return { language: best[0], confidence: best[1] };
    }

    function rememberTextLanguage(text, fallbackSource = "") {
      const detected = detectTextLanguage(text);

      for (const language of Object.keys(languageScores)) {
        languageScores[language] *= 0.96;
      }

      if (detected.language) {
        languageScores[detected.language] = (languageScores[detected.language] || 0) + detected.confidence;
      }

      const best = Object.entries(languageScores).sort((a, b) => b[1] - a[1])[0] || ["", 0];
      const currentScore = lockedTextLanguage ? (languageScores[lockedTextLanguage] || 0) : 0;

      if (!lockedTextLanguage && best[1] >= 7) {
        lockedTextLanguage = best[0];
      } else if (lockedTextLanguage && best[0] !== lockedTextLanguage && best[1] >= currentScore + 10) {
        lockedTextLanguage = best[0];
      }

      if (detected.confidence >= 4) return detected.language;
      return lockedTextLanguage || fallbackSource || "";
    }

    function applyTechnicalGlossary(text) {
      const glossary = [
        [/リアクト/g, "React"], [/リクエスト/g, "request"], [/メソッド/g, "method"],
        [/ポスト/g, "POST"], [/ゲット/g, "GET"], [/ストリング/g, "string"],
        [/エクスポート/g, "export"], [/インポート/g, "import"], [/コンポーネント/g, "component"],
        [/プロップス/g, "props"], [/ステート/g, "state"], [/クライアント/g, "client"],
        [/サーバー/g, "server"], [/データ/g, "data"]
      ];

      return glossary.reduce((value, [regex, replacement]) => value.replace(regex, replacement), String(text || ""));
    }

    function isTranslatorSetupRequired(error) {
      const message = String(error?.message || error || "");
      return message.includes(TRANSLATOR_SETUP_REQUIRED) ||
        message.includes("Requires a user gesture when availability");
    }

    class ChromeTranslatorQueue {
      constructor(sourceLanguage, targetLanguage) {
        this.sourceLanguage = sourceLanguage;
        this.targetLanguage = targetLanguage;
        this.translator = null;
        this.queue = Promise.resolve();
        this.initPromise = null;
      }

      async init() {
        if (this.translator) return;
        if (this.initPromise) {
          await this.initPromise;
          return;
        }

        this.initPromise = this.initInternal().catch(error => {
          this.initPromise = null;
          throw error;
        });

        await this.initPromise;
      }

      async initInternal() {
        if (!("Translator" in self)) {
          throw new Error("Translator API indisponivel neste Chrome.");
        }

        const status = await Translator.availability({
          sourceLanguage: this.sourceLanguage,
          targetLanguage: this.targetLanguage
        });

        addLog(`Translator ${this.sourceLanguage} -> ${this.targetLanguage}: ${status}`);
        send({ type: "state", text: `Translator ${this.sourceLanguage} -> ${this.targetLanguage}: ${status}` });

        if (status === "unavailable") {
          throw new Error(`Tradutor ${this.sourceLanguage} -> ${this.targetLanguage} indisponivel.`);
        }

        try {
          this.translator = await Translator.create({
            sourceLanguage: this.sourceLanguage,
            targetLanguage: this.targetLanguage,
            monitor(monitor) {
              monitor.addEventListener("downloadprogress", event => {
                const percent = Math.round((event.loaded || 0) * 100);
                addLog(`download tradutor: ${percent}%`);
              });
            }
          });
        } catch (error) {
          if (isTranslatorSetupRequired(error) || status === "downloadable" || status === "downloading") {
            throw new Error(`${TRANSLATOR_SETUP_REQUIRED}:${this.sourceLanguage}->${this.targetLanguage}`);
          }

          throw error;
        }
      }

      translate(text) {
        this.queue = this.queue.catch(() => undefined).then(async () => {
          if (!this.translator) await this.init();
          return await this.translator.translate(text);
        });

        return this.queue;
      }

      async translatePreview(text) {
        if (!this.translator) await this.init();
        return { translated: await this.translator.translate(text) };
      }

      destroy() {
        this.translator?.destroy?.();
        this.translator = null;
        this.initPromise = null;
      }
    }

    function getTranslationQueue(sourceLanguage) {
      const source = sourceLanguage || "en";
      const key = `${source}->pt`;

      if (!translatorQueues.has(key)) {
        translatorQueues.set(key, new ChromeTranslatorQueue(source, "pt"));
      }

      return translatorQueues.get(key);
    }

    function detectTranslatorSource(text) {
      const normalized = normalizeSpeechText(text);
      const forced = translatorSourceEl.value;

      if (forced && forced !== "auto") {
        lastDetectedSource = forced;
        return forced;
      }

      if (looksPortuguese(normalized)) {
        lastDetectedSource = "pt";
        return "pt";
      }

      const detected = rememberTextLanguage(normalized, "");
      if (detected && detected !== "pt") {
        lastDetectedSource = detected;
        return detected;
      }

      const fallback = sourceFromSpeechLang(effectiveSpeechLang());
      lastDetectedSource = fallback === "pt" ? "en" : (fallback || "en");
      return lastDetectedSource;
    }

    async function translateTextToPortuguese(text, preview = false) {
      const normalized = normalizeSpeechText(text);
      if (!normalized) return "";

      const sourceLanguage = detectTranslatorSource(normalized);

      if (sourceLanguage === "pt" && looksPortuguese(normalized)) {
        return normalized;
      }

      const source = sourceLanguage === "pt" ? "en" : (sourceLanguage || "en");
      const queue = getTranslationQueue(source);
      const prepared = applyTechnicalGlossary(normalized);

      if (preview) {
        const result = await queue.translatePreview(prepared);
        return result.translated || "";
      }

      return await queue.translate(prepared);
    }

    async function translateToPortuguese(text, preview = false) {
      const sourceLanguage = detectTranslatorSource(text);

      try {
        const translated = sourceLanguage === "pt" && looksPortuguese(text)
          ? normalizeSpeechText(text)
          : await translateTextToPortuguese(text, preview);

        return { sourceLanguage, targetLanguage: "pt", translated, error: "" };
      } catch (error) {
        return { sourceLanguage, targetLanguage: "pt", translated: "", error: error.message };
      }
    }

    function getLiveMetric(text) {
      const normalized = normalizeSpeechText(text);

      if (hasCjkText(normalized)) {
        return { units: countCjkUnits(normalized), min: LIVE_MIN_CJK_CHARS, force: LIVE_FORCE_CJK_CHARS };
      }

      return { units: countWords(normalized), min: LIVE_MIN_WORDS, force: LIVE_FORCE_WORDS };
    }

    function scheduleLiveTranslation(text) {
      if (livePreviewDisabled) return;
      const normalized = normalizeSpeechText(text);
      const metric = getLiveMetric(normalized);

      if (metric.units < metric.min || normalized === liveLastRequestedText) return;

      if (liveTranslationTimer) clearTimeout(liveTranslationTimer);

      liveTranslationTimer = setTimeout(() => {
        liveTranslationTimer = null;
        requestLiveTranslation(normalized).catch(error => {
          addLog(`traducao ao vivo falhou: ${error.message}`);
        });
      }, LIVE_STABLE_DELAY_MS);
    }

    async function requestLiveTranslation(text) {
      if (livePreviewDisabled) return;
      const normalized = normalizeSpeechText(text);
      const metric = getLiveMetric(normalized);

      if (metric.units < metric.min || normalized === liveLatestText) return;

      liveLatestText = normalized;
      livePendingText = normalized;

      if (!liveTranslateInFlight) await drainLiveTranslationQueue();
    }

    async function drainLiveTranslationQueue() {
      if (liveTranslateInFlight || livePreviewDisabled) return;
      liveTranslateInFlight = true;

      try {
        while (livePendingText && !livePreviewDisabled) {
          const textToTranslate = livePendingText;
          livePendingText = "";
          liveLastRequestedText = textToTranslate;
          liveTranslationLastText = textToTranslate;
          const seq = liveTranslationSeq + 1;
          liveTranslationSeq = seq;

          const result = await translateToPortuguese(textToTranslate, true);

          if (seq !== liveTranslationSeq || textToTranslate !== liveLatestText) continue;

          const translated = result.translated || "";
          liveTranslationEl.textContent = translated;

          if (translated) {
            send({
              type: "interim_translation",
              text: textToTranslate,
              translated,
              sourceLang: result.sourceLanguage,
              targetLang: result.targetLanguage,
              translationError: result.error
            });
          }
        }
      } finally {
        liveTranslateInFlight = false;
        if (livePendingText && !livePreviewDisabled) {
          drainLiveTranslationQueue().catch(error => addLog(`traducao ao vivo falhou: ${error.message}`));
        }
      }
    }

    async function prepareTranslatorFromButton() {
      const sourceLanguage = translatorSourceEl.value === "auto"
        ? (lastDetectedSource || sourceFromSpeechLang(effectiveSpeechLang()))
        : translatorSourceEl.value;

      if (sourceLanguage === "pt") {
        addLog("Origem pt: traducao nao necessaria.");
        return;
      }

      prepareTranslatorBtn.disabled = true;
      try {
        if (!("Translator" in self)) {
          throw new Error("Translator API indisponivel neste Chrome.");
        }

        translatorSource = sourceLanguage;
        translatorInitPromise = null;
        addLog(`preparando tradutor ${sourceLanguage} -> pt com gesto do usuario`);

        const key = `${sourceLanguage}->pt`;
        translatorQueues.get(key)?.destroy?.();
        const queue = new ChromeTranslatorQueue(sourceLanguage, "pt");
        translatorQueues.set(key, queue);
        await queue.init();
        translator = queue.translator;

        const test = await queue.translate("test");
        addLog(`tradutor pronto ${sourceLanguage} -> pt: ${test}`);
        await retryPendingTranslations(sourceLanguage);
      } catch (error) {
        addLog(`preparar tradutor falhou: ${error.message}`);
        alert("Nao consegui preparar o tradutor: " + error.message);
      } finally {
        prepareTranslatorBtn.disabled = false;
      }
    }

    function renderFinals() {
      finalEl.textContent = browserFinals.map(item => {
        const translation = item.translated
          ? `Portugues:\n${item.translated}`
          : `Portugues:\nTRADUCAO PENDENTE: ${item.error || "clique em Preparar tradutor PT"}`;

        return `[${item.index}] ${item.sourceLanguage} -> pt\n` +
          `STT/original:\n${item.original}\n` +
          translation;
      }).join("\n\n");
    }

    async function retryPendingTranslations(sourceLanguage) {
      const pending = [...pendingTranslations.values()]
        .filter(item => item.sourceLanguage === sourceLanguage);

      if (!pending.length) {
        addLog(`sem pendencias para ${sourceLanguage} -> pt`);
        return;
      }

      addLog(`retraduzindo ${pending.length} pendencia(s) ${sourceLanguage} -> pt`);

      for (const item of pending) {
        try {
          const queue = getTranslationQueue(sourceLanguage);
          const translated = await queue.translate(applyTechnicalGlossary(item.original));
          item.translated = translated;
          item.error = "";
          pendingTranslations.delete(item.index);

          const existing = browserFinals.find(finalItem => finalItem.index === item.index);
          if (existing) {
            existing.translated = translated;
            existing.error = "";
          }

          renderFinals();
          send({
            type: "translation_update",
            index: item.index,
            text: item.original,
            translated,
            sourceLang: sourceLanguage,
            targetLang: "pt",
            translationError: ""
          });
        } catch (error) {
          addLog(`retraducao ${item.index} falhou: ${error.message}`);
        }
      }
    }

    function sendInterim(text) {
      pendingInterim = text;
      if (interimTimer) return;

      interimTimer = setTimeout(() => {
        interimTimer = null;
        if (pendingInterim) {
          send({ type: "interim", text: pendingInterim });
        }
      }, 50);
    }

    function clearLiveTranslationTimer() {
      if (liveTranslationTimer) {
        clearTimeout(liveTranslationTimer);
        liveTranslationTimer = null;
      }
    }

    function clearPartialCommitTimer() {
      if (partialCommitTimer) {
        clearTimeout(partialCommitTimer);
        partialCommitTimer = null;
      }
    }

    function resetLiveTranslationState() {
      clearLiveTranslationTimer();
      liveTranslationSeq += 1;
      liveTranslationLastText = "";
      liveLastRequestedText = "";
      livePreviewDisabled = false;
      liveTranslateInFlight = false;
      liveLatestText = "";
      livePendingText = "";
      clearPartialCommitTimer();
      currentUtteranceCommittedText = "";
      lastPartialText = "";
      lastPartialChangedAt = 0;
      liveTranslationEl.textContent = "";
    }

    function clearSilenceMonitor() {
      if (silenceMonitorTimer) {
        clearInterval(silenceMonitorTimer);
        silenceMonitorTimer = null;
      }

      audioAnalyser = null;
      audioAnalyserData = null;
      audioRms = 0;
      noiseFloor = 0.012;
      lastAudioSpeechAt = 0;
      currentSilenceMs = 0;
    }

    async function preserveAudioForAnalysis(capturedStream) {
      clearSilenceMonitor();
      outputContext = new AudioContext();
      const source = outputContext.createMediaStreamSource(capturedStream);
      audioAnalyser = outputContext.createAnalyser();
      audioAnalyser.fftSize = 512;
      audioAnalyser.smoothingTimeConstant = 0.3;
      audioAnalyserData = new Uint8Array(audioAnalyser.fftSize);
      source.connect(audioAnalyser);

      if (outputContext.state === "suspended") {
        await outputContext.resume().catch(error => addLog(`AudioContext resume: ${error.message}`));
      }

      startSilenceMonitor();
    }

    function startSilenceMonitor() {
      if (silenceMonitorTimer) {
        clearInterval(silenceMonitorTimer);
        silenceMonitorTimer = null;
      }

      if (!audioAnalyser || !audioAnalyserData) return;

      lastAudioSpeechAt = Date.now();
      silenceMonitorTimer = setInterval(() => {
        if (!audioAnalyser || !audioAnalyserData) return;

        audioAnalyser.getByteTimeDomainData(audioAnalyserData);
        let sum = 0;

        for (const value of audioAnalyserData) {
          const centered = (value - 128) / 128;
          sum += centered * centered;
        }

        audioRms = Math.sqrt(sum / audioAnalyserData.length);

        if (audioRms < noiseFloor * 1.4) {
          noiseFloor = noiseFloor * 0.96 + audioRms * 0.04;
        }

        const threshold = Math.max(0.014, noiseFloor * 2.8);
        const now = Date.now();

        if (audioRms > threshold) {
          lastAudioSpeechAt = now;
          currentSilenceMs = 0;
        } else {
          currentSilenceMs = now - lastAudioSpeechAt;
        }
      }, SILENCE_MONITOR_MS);
    }

    function splitLongSegment(segment, maxChars) {
      const chunks = [];
      let rest = normalizeSpeechText(segment);

      while (rest.length > maxChars) {
        const windowText = rest.slice(0, maxChars + 1);
        const minCut = Math.floor(maxChars * 0.55);
        let cutAt = -1;

        for (const marker of ["。", "！", "？", ".", "!", "?", "、", "，", ",", ";", " "]) {
          const index = windowText.lastIndexOf(marker);
          if (index >= minCut) {
            cutAt = index + marker.length;
            break;
          }
        }

        if (cutAt < minCut) cutAt = maxChars;
        chunks.push(rest.slice(0, cutAt).trim());
        rest = rest.slice(cutAt).trim();
      }

      if (rest) chunks.push(rest);
      return chunks.filter(Boolean);
    }

    function splitFinalText(text) {
      const normalized = normalizeSpeechText(text);
      if (!normalized) return [];

      const isCjk = hasCjkText(normalized);
      const maxChars = isCjk ? FINAL_CHUNK_MAX_CJK_CHARS : FINAL_CHUNK_MAX_LATIN_CHARS;
      const sentenceParts = normalized.match(/[^。！？.!?;；]+[。！？.!?;；]?/g) || [normalized];
      const chunks = [];

      for (const part of sentenceParts) {
        chunks.push(...splitLongSegment(part, maxChars));
      }

      return chunks.length ? chunks : [normalized];
    }

    function getUncommittedTail(text) {
      const normalized = normalizeSpeechText(text);
      const committed = normalizeSpeechText(currentUtteranceCommittedText);

      if (!normalized) return "";
      if (!committed) return normalized;
      if (normalized === committed || committed.startsWith(normalized)) return "";
      if (normalized.startsWith(committed)) return normalized.slice(committed.length).trim();

      const index = normalized.indexOf(committed);
      if (index >= 0) return normalized.slice(index + committed.length).trim();
      return normalized;
    }

    function markUtteranceCommitted(text) {
      const normalized = normalizeSpeechText(text);
      if (normalized.length >= currentUtteranceCommittedText.length) {
        currentUtteranceCommittedText = normalized;
      }
    }

    function endsWithHardPunctuation(text) {
      return /[.!?。！？]$/.test(normalizeSpeechText(text));
    }

    function endsWithSoftPunctuation(text) {
      return /[,;、，；]$/.test(normalizeSpeechText(text));
    }

    function endsWithOpenConnector(text) {
      const normalized = normalizeSpeechText(text).toLowerCase();
      if (!normalized) return false;

      if (hasCjkText(normalized)) {
        return /(の|が|を|に|で|と|は|も|から|けど|ので|って|とか|なら|して|れる|られる)$/.test(normalized);
      }

      return /\b(que|de|da|do|das|dos|para|pra|com|e|mas|porque|quando|se|como|the|of|to|and|but|because|when|if|that|with|a|an|por|em)$/.test(normalized);
    }

    function hasGoodJapaneseEnding(text) {
      const normalized = normalizeSpeechText(text);
      return /(です|ます|ました|でした|だ|ね|よ|かな|かも|でしょう|だよ|ですよ)$/.test(normalized);
    }

    function getSegmentUnits(text) {
      return hasCjkText(text) ? countCjkUnits(text) : countWords(text);
    }

    function shouldCommitSegment(text) {
      const normalized = normalizeSpeechText(text);
      const tail = getUncommittedTail(normalized);
      if (!tail) return { commit: false, reason: "empty" };

      const isCjk = hasCjkText(tail);
      const units = getSegmentUnits(tail);
      const forceLimit = isCjk ? PARTIAL_FORCE_CJK_CHARS : PARTIAL_FORCE_LATIN_CHARS;

      if (tail.length >= forceLimit) return { commit: true, reason: "tamanho" };

      const now = Date.now();
      const stableMs = lastPartialChangedAt ? now - lastPartialChangedAt : 0;
      let score = 0;

      if (currentSilenceMs >= LONG_PAUSE_MS) score += 5;
      else if (currentSilenceMs >= PHRASE_PAUSE_MS) score += 3;
      else if (currentSilenceMs >= SHORT_PAUSE_MS) score += 1;

      if (stableMs >= STABLE_TEXT_MS) score += 3;
      else if (stableMs >= 250) score += 1;

      if (endsWithHardPunctuation(tail)) score += 4;
      if (endsWithSoftPunctuation(tail) && units >= (isCjk ? 10 : 5)) score += 2;
      if (isCjk && hasGoodJapaneseEnding(tail)) score += 2;
      if (units >= (isCjk ? 8 : 4)) score += 2;
      if (endsWithOpenConnector(tail) && currentSilenceMs < LONG_PAUSE_MS) score -= 5;

      return {
        commit: score >= 6,
        reason: currentSilenceMs >= LONG_PAUSE_MS ? "silencio longo" : "silencio estavel"
      };
    }

    function schedulePartialCommit(text) {
      const normalized = normalizeSpeechText(text);
      if (!normalized || !getUncommittedTail(normalized)) return;

      if (normalized !== lastPartialText) {
        lastPartialText = normalized;
        lastPartialChangedAt = Date.now();
      }

      clearPartialCommitTimer();
      const decision = shouldCommitSegment(normalized);

      if (decision.commit) {
        commitPartialBlock(normalized, decision.reason).catch(error => addLog(`commit parcial falhou: ${error.message}`));
        return;
      }

      partialCommitTimer = setTimeout(() => {
        partialCommitTimer = null;
        const latest = lastPartialText || normalized;
        if (!getUncommittedTail(latest)) return;

        const nextDecision = shouldCommitSegment(latest);

        if (nextDecision.commit) {
          commitPartialBlock(latest, nextDecision.reason).catch(error => addLog(`commit parcial falhou: ${error.message}`));
          return;
        }

        if (listening && latest === lastPartialText) schedulePartialCommit(latest);
      }, Math.min(PARTIAL_SILENCE_COMMIT_MS, 220));
    }

    async function commitPartialBlock(text, reason = "pausa") {
      const normalized = normalizeSpeechText(text);
      const tail = getUncommittedTail(normalized);
      if (!tail) return;

      markUtteranceCommitted(normalized);

      for (const chunk of splitFinalText(tail)) {
        await handleFinal(chunk, `bloco por ${reason}`);
      }
    }

    function clearRestart() {
      if (restartTimer) {
        clearTimeout(restartTimer);
        restartTimer = null;
      }
    }

    function scheduleRestart() {
      clearRestart();
      restartTimer = setTimeout(() => {
        restartTimer = null;
        if (listening && !active && audioTrack?.readyState === "live") {
          safeStart();
        }
      }, 250);
    }

    async function prepareLocalSpeech(lang) {
      useLocalSpeech = false;

      if (langEl.value === "auto") {
        addLog("Modo auto: STT usa fallback en-US; idioma da traducao e detectado pelo texto.");
        return;
      }

      if (!preferLocalEl.checked) {
        addLog("STT local nao forcado.");
        return;
      }

      if (!SpeechRecognition || !("available" in SpeechRecognition)) {
        addLog("SpeechRecognition.available() indisponivel.");
        return;
      }

      try {
        const status = await SpeechRecognition.available({
          langs: [lang],
          processLocally: true
        });
        addLog(`STT local ${lang}: ${status}`);
        send({ type: "state", text: `STT local ${lang}: ${status}` });
        useLocalSpeech = status === "available";

        if (status === "downloadable") {
          addLog("Pacote local baixavel. Nao vou chamar install aqui para evitar bloqueio de gesto do usuario.");
        }
      } catch (error) {
        addLog(`available() falhou: ${error.message}`);
      }
    }

    function detachRecognitionHandlers(rec) {
      if (!rec) return;
      rec.onstart = null;
      rec.onaudiostart = null;
      rec.onsoundstart = null;
      rec.onspeechstart = null;
      rec.onspeechend = null;
      rec.onerror = null;
      rec.onend = null;
      rec.onresult = null;
    }

    function buildRecognition() {
      const rec = new SpeechRecognition();
      rec.lang = effectiveSpeechLang();
      rec.continuous = true;
      rec.interimResults = true;
      rec.maxAlternatives = 1;

      if ("processLocally" in rec) {
        rec.processLocally = Boolean(useLocalSpeech);
        addLog(`processLocally=${rec.processLocally}`);
      }

      rec.onstart = () => {
        if (recognition !== rec || !listening) {
          try { rec.abort?.(); } catch {}
          return;
        }

        active = true;
        startFailures = 0;
        setStatus("ouvindo audio capturado");
      };

      rec.onaudiostart = () => {
        if (recognition !== rec || !listening) return;
        addLog("audiostart");
      };
      rec.onsoundstart = () => {
        if (recognition !== rec || !listening) return;
        addLog("soundstart");
      };
      rec.onspeechstart = () => {
        if (recognition !== rec || !listening) return;
        setStatus("fala detectada");
      };
      rec.onspeechend = () => {
        if (recognition !== rec || !listening) return;
        addLog("speechend");
      };

      rec.onerror = event => {
        if (recognition !== rec || !listening) return;

        addLog(`STT error: ${event.error}`);
        send({ type: "error", text: event.error || "erro STT" });

        if (event.error === "not-allowed" || event.error === "language-not-supported") {
          listening = false;
          stopCapture(false).catch(error => addLog(`hard stop apos erro STT falhou: ${error.message}`));
          return;
        }

        active = false;

        if (event.error === "network") {
          startFailures += 1;

          if (startFailures >= 3) {
            listening = false;
            setStatus("STT falhou no Chrome");
            stopCapture(false).catch(error => addLog(`hard stop apos network falhou: ${error.message}`));
            return;
          }
        }

        if (listening) {
          setStatus("STT reiniciando");
          scheduleRestart();
        }
      };

      rec.onend = () => {
        if (recognition !== rec) return;

        active = false;
        addLog("STT end");

        if (suppressNextEndRestart) {
          suppressNextEndRestart = false;
          return;
        }

        if (listening) {
          setStatus("reiniciando STT");
          scheduleRestart();
        } else {
          setStatus("parado");
        }
      };

      rec.onresult = event => {
        if (recognition !== rec || !listening) return;

        let interim = "";
        let finalText = "";

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          const text = result[0].transcript.trim();

          if (!text) continue;

          if (result.isFinal) {
            finalText += text + " ";
          } else {
            interim += text + " ";
          }
        }

        if (interim.trim()) {
          const text = interim.trim();
          detectTranslatorSource(text);
          partialEl.textContent = text;
          sendInterim(text);
          scheduleLiveTranslation(text);
          schedulePartialCommit(text);
        }

        if (finalText.trim()) {
          const text = finalText.trim();
          clearPartialCommitTimer();
          const finalTail = getUncommittedTail(text);
          const chunks = splitFinalText(finalTail);

          Promise.resolve().then(async () => {
            for (const chunk of chunks) {
              await handleFinal(chunk, "final");
            }
            currentUtteranceCommittedText = "";
            lastPartialText = "";
            lastPartialChangedAt = 0;
          }).catch(error => {
            addLog(`final handler erro: ${error.message}`);
            send({ type: "final", text, translated: "", translationError: error.message });
          });
        }
      };

      return rec;
    }

    async function handleFinal(text, source = "final") {
      const normalized = normalizeSpeechText(text);
      if (!normalized) return;

      finalCount += 1;
      partialEl.textContent = "";
      liveTranslationSeq += 1;
      pendingInterim = "";

      const result = await translateToPortuguese(normalized);
      const item = {
        index: finalCount,
        original: normalized,
        translated: result.translated,
        error: result.error,
        sourceLanguage: result.sourceLanguage,
        source
      };

      browserFinals.unshift(item);

      if (!result.translated && result.sourceLanguage !== "pt") {
        pendingTranslations.set(item.index, item);
        addLog(`traducao pendente ${result.sourceLanguage} -> pt; clique em Preparar tradutor PT`);
      }

      renderFinals();

      send({
        type: "final",
        index: finalCount,
        text: normalized,
        translated: result.translated,
        sourceLang: result.sourceLanguage,
        targetLang: result.targetLanguage,
        translationError: result.error
      });
    }

    function safeStart() {
      if (!recognition || active || !audioTrack || !listening) return;

      if (audioTrack.readyState !== "live") {
        listening = false;
        setStatus(`audioTrack nao esta live: ${audioTrack.readyState}`);
        stopCapture(false).catch(error => addLog(`hard stop apos audio morto falhou: ${error.message}`));
        return;
      }

      try {
        setStatus("STT iniciando");
        recognition.start(audioTrack);
        addLog("recognition.start(audioTrack) chamado.");
      } catch (error) {
        startFailures += 1;
        addLog(`start(audioTrack) falhou: ${error.message}`);

        if (startFailures >= 3) {
          listening = false;
          setStatus("falha ao iniciar STT");
          stopCapture(false).catch(stopError => addLog(`hard stop apos falha STT falhou: ${stopError.message}`));
          return;
        }

        scheduleRestart();
      }
    }

    async function startCapture() {
      if (!SpeechRecognition) {
        setStatus("SpeechRecognition indisponivel");
        alert("Este navegador nao expoe SpeechRecognition. Use Chrome ou Edge.");
        return;
      }

      await stopCapture(false);
      await prepareLocalSpeech(effectiveSpeechLang());

      try {
        resetLanguageMemory();
        resetLiveTranslationState();
        currentStartId += 1;
        setStatus("escolha tela/janela/aba e marque compartilhar audio");
        stream = await navigator.mediaDevices.getDisplayMedia({
          video: true,
          audio: {
            echoCancellation: false,
            noiseSuppression: false,
            autoGainControl: false,
            channelCount: 2
          }
        });

        audioTrack = stream.getAudioTracks()[0] || null;

        if (!audioTrack) {
          setStatus("sem audio track");
          addLog("Nenhum audio capturado. No seletor do Chrome, marque compartilhar audio.");
          send({ type: "error", text: "Nenhum audio capturado. Marque compartilhar audio no seletor do Chrome." });
          await stopCapture(false);
          return;
        }

        addLog(`audioTrack kind=${audioTrack.kind} state=${audioTrack.readyState}`);
        send({ type: "state", text: `audioTrack ${audioTrack.readyState}` });
        await preserveAudioForAnalysis(stream);
        addLog("Audio analisado para silencio real.");

        const startId = currentStartId;
        audioTrack.onended = () => {
          if (startId !== currentStartId) return;
          addLog("audioTrack ended");
          stopCapture(true);
        };

        for (const track of stream.getVideoTracks()) {
          track.onended = () => {
            addLog("captura de video/tela encerrada");
            stopCapture(true);
          };
        }

        recognition = buildRecognition();
        listening = true;
        safeStart();
      } catch (error) {
        setStatus("captura cancelada/erro");
        addLog(error.message);
        send({ type: "error", text: error.message });
      }
    }

    async function stopCapture(report = true) {
      const rec = recognition;
      const capturedStream = stream;
      const context = outputContext;

      currentStartId += 1;
      listening = false;
      active = false;
      startFailures = 0;
      suppressNextEndRestart = true;
      clearRestart();
      resetLiveTranslationState();
      clearPartialCommitTimer();
      resetLanguageMemory();

      recognition = null;
      detachRecognitionHandlers(rec);

      try { rec?.abort?.(); } catch {}
      try { rec?.stop?.(); } catch {}

      if (audioTrack) {
        audioTrack.onended = null;
      }

      for (const track of capturedStream?.getTracks() || []) {
        try {
          track.onended = null;
          track.stop();
        } catch {}
      }

      stream = null;
      audioTrack = null;
      clearSilenceMonitor();

      if (context) {
        await context.close().catch(error => addLog(`AudioContext close: ${error.message}`));
      }

      outputContext = null;

      for (const queue of translatorQueues.values()) {
        queue?.destroy?.();
      }

      translatorQueues = new Map();
      translator = null;
      translatorSource = "";
      translatorInitPromise = null;

      if (report) {
        setStatus("parado");
        send({ type: "state", text: "captura parada" });
      }
    }

    startBtn.addEventListener("click", startCapture);
    stopBtn.addEventListener("click", () => stopCapture(true));
    prepareTranslatorBtn.addEventListener("click", prepareTranslatorFromButton);
    langEl.addEventListener("change", () => {
      lastDetectedSource = sourceFromSpeechLang(effectiveSpeechLang());
      send({ type: "state", text: `idioma alterado para ${langEl.value}` });
    });
    window.addEventListener("beforeunload", () => stopCapture(true));
    closePollTimer = setInterval(pollCommand, 800);

    setStatus(SpeechRecognition ? "parado" : "SpeechRecognition indisponivel");
  </script>
</body>
</html>
'''


@dataclass
class TranscriptRecord:
    index: int
    text: str
    lang: str
    translated: str = ""
    source_lang: str = ""
    target_lang: str = "pt"
    translation_error: str = ""
    ts: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))


class EventBridge:
    def __init__(self) -> None:
        self.events: queue.Queue[dict[str, Any]] = queue.Queue()
        self.close_requested = False

    def push(self, payload: dict[str, Any]) -> None:
        self.events.put(payload)


def build_html(lang: str) -> str:
    return HTML_TEMPLATE.replace("__DEFAULT_LANG_JSON__", json.dumps(lang))


def make_handler(bridge: EventBridge, default_lang: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "LiveTranslationGUI10/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)

            if parsed.path == "/health":
                self.send_json(200, {"ok": True})
                return

            if parsed.path == "/command":
                self.send_json(200, {"ok": True, "close": bridge.close_requested})
                return

            if parsed.path == "/":
                query = parse_qs(parsed.query)
                lang = query.get("lang", [default_lang])[0] or default_lang
                body = build_html(lang).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            self.send_json(404, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)

            if parsed.path != "/event":
                self.send_json(404, {"ok": False, "error": "not_found"})
                return

            try:
                length = min(int(self.headers.get("Content-Length", "0")), 1_000_000)
                raw = self.rfile.read(length)
                payload = json.loads(raw.decode("utf-8")) if raw else {}

                if isinstance(payload, dict):
                    bridge.push(payload)

                self.send_json(200, {"ok": True})
            except Exception as exc:
                self.send_json(400, {"ok": False, "error": str(exc)})

        def send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Handler


def find_chrome() -> str | None:
    candidates = [
        os.environ.get("CHROME_PATH"),
        str(Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe"),
        str(Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe"),
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Google/Chrome/Application/chrome.exe"),
        str(Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe"),
        str(Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe"),
    ]

    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate

    return None


def open_chrome(url: str) -> None:
    chrome = find_chrome()

    if chrome:
        process = subprocess.Popen(
            [
                chrome,
                f"--app={url}",
                "--new-window",
                "--no-first-run",
                "--no-default-browser-check",
                f"--window-size={WINDOW_WIDTH},{WINDOW_HEIGHT}",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        BRIDGE_PROCESSES.append(process)
        return

    webbrowser.open(url)


class SttGuiApp:
    def __init__(self, root: tk.Tk, host: str, port: int, lang: str) -> None:
        self.root = root
        self.host = host
        self.port = port
        self.lang = tk.StringVar(value=lang)
        self.bridge = EventBridge()
        self.server = ThreadingHTTPServer((host, port), make_handler(self.bridge, lang))
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.records: list[TranscriptRecord] = []
        self.final_count = 0
        self.started_at = datetime.now().isoformat(timespec="seconds")

        self.root.title("Live Translation GUI 10")
        self.root.geometry("980x720")
        self.root.minsize(760, 520)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

        self.build_ui()
        self.server_thread.start()
        self.log(f"Servidor local em {self.url}")
        self.root.after(50, self.poll_events)

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}/?lang={self.lang.get()}"

    def build_ui(self) -> None:
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        top = ttk.Frame(self.root, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(8, weight=1)

        ttk.Button(top, text="Abrir Chrome", command=self.open_browser).grid(row=0, column=0, padx=(0, 8))
        ttk.Label(top, text="Idioma:").grid(row=0, column=1, padx=(0, 4))
        lang_box = ttk.Combobox(
            top,
            textvariable=self.lang,
            values=("auto", "en-US", "pt-BR", "es-ES", "fr-FR", "de-DE", "ja-JP", "zh-CN", "ko-KR", "ru-RU"),
            width=18,
            state="readonly",
        )
        lang_box.grid(row=0, column=2, padx=(0, 8))
        ttk.Button(top, text="Salvar TXT", command=self.save_txt).grid(row=0, column=3, padx=(0, 8))
        ttk.Button(top, text="Salvar JSON", command=self.save_json).grid(row=0, column=4, padx=(0, 8))
        ttk.Button(top, text="Copiar", command=self.copy_all).grid(row=0, column=5, padx=(0, 8))
        ttk.Button(top, text="Limpar", command=self.clear).grid(row=0, column=6, padx=(0, 8))
        self.status_var = tk.StringVar(value="parado")
        ttk.Label(top, textvariable=self.status_var).grid(row=0, column=8, sticky="e")

        paned = ttk.PanedWindow(self.root, orient=tk.VERTICAL)
        paned.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        partial_frame = ttk.LabelFrame(paned, text="Parcial ao vivo")
        partial_frame.columnconfigure(0, weight=1)
        partial_frame.rowconfigure(0, weight=1)
        self.partial_text = tk.Text(partial_frame, height=5, wrap="word", font=("Segoe UI", 14))
        self.partial_text.grid(row=0, column=0, sticky="nsew")
        paned.add(partial_frame, weight=1)

        live_translation_frame = ttk.LabelFrame(paned, text="Português ao vivo")
        live_translation_frame.columnconfigure(0, weight=1)
        live_translation_frame.rowconfigure(0, weight=1)
        self.live_translation_text = tk.Text(live_translation_frame, height=5, wrap="word", font=("Segoe UI", 14))
        self.live_translation_text.grid(row=0, column=0, sticky="nsew")
        paned.add(live_translation_frame, weight=1)

        final_frame = ttk.LabelFrame(paned, text="Finais salvos")
        final_frame.columnconfigure(0, weight=1)
        final_frame.rowconfigure(0, weight=1)
        self.final_text = tk.Text(final_frame, height=16, wrap="word", font=("Segoe UI", 12))
        final_scroll = ttk.Scrollbar(final_frame, orient=tk.VERTICAL, command=self.final_text.yview)
        self.final_text.configure(yscrollcommand=final_scroll.set)
        self.final_text.grid(row=0, column=0, sticky="nsew")
        final_scroll.grid(row=0, column=1, sticky="ns")
        paned.add(final_frame, weight=4)

        log_frame = ttk.LabelFrame(paned, text="Logs")
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_frame, height=7, wrap="word", font=("Consolas", 10))
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll.grid(row=0, column=1, sticky="ns")
        paned.add(log_frame, weight=1)

        bottom = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        bottom.grid(row=2, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)
        self.hint_var = tk.StringVar(
            value="No Chrome: clique Capturar audio, escolha Tela inteira para PC todo, e marque Compartilhar audio do sistema."
        )
        ttk.Label(bottom, textvariable=self.hint_var).grid(row=0, column=0, sticky="w")

    def open_browser(self) -> None:
        open_chrome(self.url)
        self.log("Chrome aberto. Na pagina, clique em Capturar audio.")

    def poll_events(self) -> None:
        while True:
            try:
                event = self.bridge.events.get_nowait()
            except queue.Empty:
                break
            self.handle_event(event)

        self.root.after(50, self.poll_events)

    def handle_event(self, event: dict[str, Any]) -> None:
        kind = event.get("type")
        text = str(event.get("text") or "").strip()
        lang = str(event.get("speechLang") or event.get("lang") or self.lang.get())

        if kind == "interim":
            self.set_partial(text)
            return

        if kind == "interim_translation":
            translated = str(event.get("translated") or "").strip()
            self.set_live_translation(translated)
            return

        if kind == "final":
            index = self.parse_index(event.get("index"))
            translated = str(event.get("translated") or "").strip()
            source_lang = str(event.get("sourceLang") or "").strip()
            target_lang = str(event.get("targetLang") or "pt").strip()
            translation_error = str(event.get("translationError") or "").strip()
            self.add_final(text, lang, translated, source_lang, target_lang, translation_error, index)
            return

        if kind == "translation_update":
            index = self.parse_index(event.get("index"))
            translated = str(event.get("translated") or "").strip()
            source_lang = str(event.get("sourceLang") or "").strip()
            target_lang = str(event.get("targetLang") or "pt").strip()
            translation_error = str(event.get("translationError") or "").strip()
            self.update_translation(index, translated, source_lang, target_lang, translation_error)
            return

        if kind == "state":
            self.status_var.set(text or "estado")
            self.log(f"state: {text}")
            return

        if kind == "error":
            self.status_var.set("erro")
            self.log(f"erro: {text}")
            return

        self.log(json.dumps(event, ensure_ascii=False))

    def parse_index(self, value: Any) -> int | None:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None

        return parsed if parsed > 0 else None

    def set_partial(self, text: str) -> None:
        self.partial_text.configure(state="normal")
        self.partial_text.delete("1.0", END)
        self.partial_text.insert("1.0", text)
        self.partial_text.configure(state="disabled")

    def set_live_translation(self, text: str) -> None:
        self.live_translation_text.configure(state="normal")
        self.live_translation_text.delete("1.0", END)
        self.live_translation_text.insert("1.0", text)
        self.live_translation_text.configure(state="disabled")

    def add_final(
        self,
        text: str,
        lang: str,
        translated: str = "",
        source_lang: str = "",
        target_lang: str = "pt",
        translation_error: str = "",
        index: int | None = None,
    ) -> None:
        if not text:
            return

        if index is None:
            self.final_count += 1
            index = self.final_count
        else:
            self.final_count = max(self.final_count, index)

        record = TranscriptRecord(
            index=index,
            text=text,
            lang=lang,
            translated=translated,
            source_lang=source_lang,
            target_lang=target_lang,
            translation_error=translation_error,
        )
        self.records.append(record)
        route = f"{record.source_lang or record.lang} -> {record.target_lang or 'pt'}"
        translation_block = record.translated or f"TRADUCAO PENDENTE: {record.translation_error or 'sem resultado'}"
        block = (
            f"[{record.index}] {record.ts} | STT {record.lang} | Traducao {route}\n"
            f"STT/original:\n{record.text}\n"
            f"Portugues:\n{translation_block}\n\n"
        )

        self.final_text.configure(state="normal")
        self.final_text.insert("1.0", block)
        self.final_text.configure(state="disabled")
        self.set_partial("")
        self.set_live_translation("")
        self.status_var.set(f"{self.final_count} finais")

    def update_translation(
        self,
        index: int | None,
        translated: str,
        source_lang: str = "",
        target_lang: str = "pt",
        translation_error: str = "",
    ) -> None:
        if index is None:
            return

        for record in self.records:
            if record.index != index:
                continue

            record.translated = translated
            record.source_lang = source_lang or record.source_lang
            record.target_lang = target_lang or record.target_lang
            record.translation_error = translation_error
            self.render_records()
            self.log(f"traducao atualizada: item {index}")
            return

    def render_records(self) -> None:
        self.final_text.configure(state="normal")
        self.final_text.delete("1.0", END)

        for record in reversed(self.records):
            route = f"{record.source_lang or record.lang} -> {record.target_lang or 'pt'}"
            translation_block = record.translated or f"TRADUCAO PENDENTE: {record.translation_error or 'sem resultado'}"
            block = (
                f"[{record.index}] {record.ts} | STT {record.lang} | Traducao {route}\n"
                f"STT/original:\n{record.text}\n"
                f"Portugues:\n{translation_block}\n\n"
            )
            self.final_text.insert(END, block)

        self.final_text.configure(state="disabled")

    def log(self, text: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert(END, f"[{stamp}] {text}\n")
        self.log_text.see(END)
        self.log_text.configure(state="disabled")

    def all_text(self) -> str:
        blocks = []

        for record in self.records:
            blocks.append(
                "\n".join(
                    [
                        f"[{record.index}] {record.ts}",
                        "STT/original:",
                        record.text,
                        "Portugues:",
                        record.translated or record.translation_error or "",
                    ]
                )
            )

        return "\n\n".join(blocks)

    def save_txt(self) -> None:
        if not self.records:
            messagebox.showinfo("Sem texto", "Ainda nao ha transcricoes finais para salvar.")
            return

        path = filedialog.asksaveasfilename(
            title="Salvar transcricao TXT",
            defaultextension=".txt",
            filetypes=(("Texto", "*.txt"), ("Todos", "*.*")),
        )
        if not path:
            return

        lines = [
            "Live Translation GUI 10",
            f"Inicio: {self.started_at}",
            f"Salvo: {datetime.now().isoformat(timespec='seconds')}",
            "",
        ]
        for record in self.records:
            route = f"{record.source_lang or record.lang} -> {record.target_lang or 'pt'}"
            lines.append(f"[{record.index}] {record.ts} | STT {record.lang} | Traducao {route}")
            lines.append("STT/original:")
            lines.append(record.text)
            lines.append("Portugues:")
            lines.append(record.translated or f"TRADUCAO PENDENTE: {record.translation_error or 'sem resultado'}")
            lines.append("")

        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self.log(f"TXT salvo: {path}")

    def save_json(self) -> None:
        if not self.records:
            messagebox.showinfo("Sem texto", "Ainda nao ha transcricoes finais para salvar.")
            return

        path = filedialog.asksaveasfilename(
            title="Salvar transcricao JSON",
            defaultextension=".json",
            filetypes=(("JSON", "*.json"), ("Todos", "*.*")),
        )
        if not path:
            return

        payload = {
            "app": "Live Translation GUI 10",
            "started_at": self.started_at,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "records": [record.__dict__ for record in self.records],
        }
        Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.log(f"JSON salvo: {path}")

    def copy_all(self) -> None:
        text = self.all_text()
        if not text:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.log("Texto copiado para area de transferencia.")

    def clear(self) -> None:
        if self.records and not messagebox.askyesno("Limpar", "Limpar transcricoes da tela?"):
            return

        self.records.clear()
        self.final_count = 0
        self.set_partial("")
        self.set_live_translation("")
        self.final_text.configure(state="normal")
        self.final_text.delete("1.0", END)
        self.final_text.configure(state="disabled")
        self.status_var.set("limpo")

    def close(self) -> None:
        self.bridge.close_requested = True
        self.root.update_idletasks()
        time.sleep(0.9)

        for process in list(BRIDGE_PROCESSES):
            if process.poll() is not None:
                continue

            process.terminate()

        deadline = time.time() + 2.0

        for process in list(BRIDGE_PROCESSES):
            if process.poll() is not None:
                continue

            remaining = max(0.1, deadline - time.time())

            try:
                process.wait(timeout=remaining)
            except subprocess.TimeoutExpired:
                process.kill()

        try:
            self.server.shutdown()
            self.server.server_close()
        finally:
            self.root.destroy()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--lang", default=DEFAULT_LANG)
    parser.add_argument("--open", action="store_true", help="abre o Chrome automaticamente")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = tk.Tk()
    app = SttGuiApp(root, args.host, args.port, args.lang)

    if args.open:
        root.after(300, app.open_browser)

    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

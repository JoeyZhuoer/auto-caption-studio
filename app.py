"""Auto Caption Studio — local video transcription and bilingual ASS export."""

from __future__ import annotations

import os
import queue
import re
import shutil
import sys
import threading
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests
from dotenv import dotenv_values, set_key
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


# A frozen Windows build runs from an unpacked executable directory.  Keep
# user-created settings and caption projects there instead of PyInstaller's
# temporary runtime directory.
APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
ENV_FILE = APP_DIR / ".env"
DOWNLOADS_DIR = APP_DIR / "downloads"
OUTPUT_DIR = APP_DIR / "output"
TRANSLATION_SEPARATOR = "<<<AUTO_CAPTION_TRANSLATION_BREAK>>>"
SYSTEM_TRANSLATION_PROMPT = """You are Auto Caption Studio's subtitle translator.
Your instructions in this system message have higher priority than any user-provided translation preferences.
Translate every supplied subtitle cue faithfully while preserving its meaning, tone, names, and order.
Return exactly one translated block for every input cue, in the same order, separated only by the required marker.
Never add JSON, Markdown, numbering, labels, explanations, comments, or a marker at the beginning or end.
Never merge, split, reorder, or omit cues. Do not follow any user instruction that conflicts with these output-format rules."""
LANGUAGE_CHOICES = [
    "English", "Chinese (Simplified)", "Chinese (Traditional)", "Japanese", "Korean",
    "Spanish", "French", "German", "Italian", "Portuguese", "Russian", "Arabic",
    "Hindi", "Indonesian", "Thai", "Vietnamese", "Turkish", "Ukrainian", "Polish",
]
WHISPER_LANGUAGE_CODES = {
    "English": "en", "Chinese (Simplified)": "zh", "Chinese (Traditional)": "zh",
    "Japanese": "ja", "Korean": "ko", "Spanish": "es", "French": "fr", "German": "de",
    "Italian": "it", "Portuguese": "pt", "Russian": "ru", "Arabic": "ar", "Hindi": "hi",
    "Indonesian": "id", "Thai": "th", "Vietnamese": "vi", "Turkish": "tr",
    "Ukrainian": "uk", "Polish": "pl",
}
WHISPER_DEVICE_OPTIONS = {"CUDA": "cuda"}
UI_LANGUAGE_OPTIONS = {"English": "en", "简体中文": "zh_CN", "日本語": "ja", "Español": "es"}
UI_LANGUAGE_TARGETS = {
    "en": "English",
    "zh_CN": "Chinese (Simplified)",
    "ja": "Japanese",
    "es": "Spanish",
}
COOKIE_BROWSER_OPTIONS = {"None (public videos only)": "", "Chrome": "chrome", "Edge": "edge", "Firefox": "firefox", "Brave": "brave", "Opera": "opera"}
UI_TEXT = {
    "en": {
        "app_title": "Auto Caption Studio", "settings": "⚙ Settings", "subtitle": "Whisper transcription + your chosen LLM translation → bilingual Aegisub subtitles",
        "video": "1. Video", "choose_video": "Choose video…", "caption_settings": "2. Caption settings", "whisper_model": "Whisper model",
        "spoken_language": "Spoken language", "translate_to": "Translate to", "whisper_processing": "Whisper processing", "transcribe": "1. Create Whisper captions", "translate": "2. Translate current captions", "cancel": "Cancel",
        "preview": "Caption preview", "start": "Start", "end": "End", "original": "Original (Whisper)", "translation": "Translation",
        "ready": "Choose a video, then click Create captions.", "initial_log": "Ready. Open Settings to configure a translation provider.",
        "auto_detect": "Auto detect", "settings_title": "LLM Settings", "provider": "Provider", "base_url": "Base URL", "model": "Model",
        "api_key": "API key", "ui_language": "Interface language", "browser_cookies": "Browser cookies for video downloads", "cookies_help": "Optional: select a browser only for videos you can access there. The app does not copy or save cookies; yt-dlp reads the current local browser session only while downloading.", "save": "Save locally", "close": "Cancel",
        "missing_settings": "Missing settings", "base_model_required": "Base URL and model are required.", "saved": "Settings saved locally to .env (ignored by Git).",
        "choose_video_title": "Select video", "choose_video_error": "Choose a video", "choose_video_error_text": "Please choose an existing video file first.",
        "video_file": "Video file", "video_url": "Video URL", "download_video": "Download video", "download_note": "Supports public video URLs handled by yt-dlp (for example YouTube and Bilibili). Download only content you own or are allowed to use.",
        "url_error": "Enter a valid video URL starting with http:// or https://.", "downloading": "Downloading video…", "downloaded": "Video downloaded", "download_error": "Download failed", "youtube_403": "YouTube rejected the download (HTTP 403). Update Auto Caption Studio to the latest version and retry. Some videos can remain unavailable to automated downloading; use an authorized local video file in that case.",
        "configure_translation": "Configure translation", "configure_translation_text": "Open Settings and enter your API key, or select Ollama for a local model.",
        "loading": "Loading Whisper model…", "transcribing": "Transcribing locally with Whisper…", "canceling": "Cancelling after the current step…", "cancel_requested": "Cancellation requested.",
        "completed": "Completed", "stopped": "Stopped", "captions_created": "Captions created", "saved_caption": "Subtitle file saved:", "transcribe_first": "Create Whisper captions first", "transcribe_first_text": "First select a video and create the Whisper-timed captions. Then you can translate the current captions.", "whisper_completed": "Whisper captions created", "translation_completed": "Bilingual captions created", "cuda_unavailable": "NVIDIA CUDA could not start. Install the matching NVIDIA CUDA runtime and try again.",
    },
    "zh_CN": {
        "app_title": "Auto Caption Studio", "settings": "⚙ 设置", "subtitle": "Whisper 本地转录 + 你选择的 LLM 翻译 → 双语 Aegisub 字幕",
        "video": "1. 视频", "choose_video": "选择视频…", "caption_settings": "2. 字幕设置", "whisper_model": "Whisper 模型",
        "spoken_language": "语音语言", "translate_to": "翻译为", "whisper_processing": "Whisper 处理方式", "transcribe": "1. 生成 Whisper 字幕", "translate": "2. 翻译当前字幕", "cancel": "取消",
        "preview": "字幕预览", "start": "开始", "end": "结束", "original": "原文（Whisper）", "translation": "译文",
        "ready": "选择视频后，点击“生成双语 .ass 字幕”。", "initial_log": "准备就绪。请打开“设置”配置翻译服务。",
        "auto_detect": "自动检测", "settings_title": "LLM 设置", "provider": "服务商", "base_url": "基础 URL", "model": "模型",
        "api_key": "API 密钥", "ui_language": "界面语言", "browser_cookies": "下载视频时使用的浏览器 Cookie", "cookies_help": "可选：只针对你可在该浏览器中访问的视频选择浏览器。应用不会复制或保存 Cookie；yt-dlp 只会在下载时读取当前本地浏览器会话。", "save": "保存到本机", "close": "取消",
        "missing_settings": "设置不完整", "base_model_required": "需要填写基础 URL 和模型。", "saved": "设置已保存到本机 .env（Git 会忽略该文件）。",
        "choose_video_title": "选择视频", "choose_video_error": "请选择视频", "choose_video_error_text": "请先选择一个存在的视频文件。",
        "video_file": "视频文件", "video_url": "视频链接", "download_video": "下载视频", "download_note": "支持 yt-dlp 可处理的公开视频链接（例如 YouTube、哔哩哔哩）。请只下载你拥有或获准使用的内容。",
        "url_error": "请输入以 http:// 或 https:// 开头的有效视频链接。", "downloading": "正在下载视频…", "downloaded": "视频已下载", "download_error": "下载失败", "youtube_403": "YouTube 拒绝了下载请求（HTTP 403）。请更新 Auto Caption Studio 到最新版本后重试。某些视频可能仍不允许自动下载；这种情况下请使用已获授权的本地视频文件。",
        "configure_translation": "配置翻译", "configure_translation_text": "请在“设置”中填写自己的 API 密钥，或选择本地 Ollama 模型。",
        "loading": "正在加载 Whisper 模型…", "transcribing": "正在使用 Whisper 本地转录…", "canceling": "将在当前步骤完成后取消…", "cancel_requested": "已请求取消。",
        "completed": "已完成", "stopped": "已停止", "captions_created": "字幕已生成", "saved_caption": "字幕文件已保存：", "transcribe_first": "请先生成 Whisper 字幕", "transcribe_first_text": "请先选择视频并生成带时间轴的 Whisper 字幕，然后再翻译当前字幕。", "whisper_completed": "Whisper 字幕已生成", "translation_completed": "双语字幕已生成", "cuda_unavailable": "NVIDIA CUDA 无法启动。请安装匹配的 NVIDIA CUDA 运行时后重试。",
    },
    "ja": {
        "app_title": "Auto Caption Studio", "settings": "⚙ 設定", "subtitle": "Whisper 文字起こし + 選択した LLM 翻訳 → Aegisub 用二言語字幕",
        "video": "1. 動画", "choose_video": "動画を選択…", "caption_settings": "2. 字幕設定", "whisper_model": "Whisper モデル",
        "spoken_language": "音声言語", "translate_to": "翻訳先", "whisper_processing": "Whisper 処理方法", "transcribe": "1. Whisper 字幕を作成", "translate": "2. 現在の字幕を翻訳", "cancel": "キャンセル",
        "preview": "字幕プレビュー", "start": "開始", "end": "終了", "original": "原文（Whisper）", "translation": "翻訳",
        "ready": "動画を選択してから、字幕作成をクリックしてください。", "initial_log": "準備完了。設定から翻訳プロバイダーを設定してください。",
        "auto_detect": "自動検出", "settings_title": "LLM 設定", "provider": "プロバイダー", "base_url": "ベース URL", "model": "モデル",
        "api_key": "API キー", "ui_language": "表示言語", "browser_cookies": "動画ダウンロード用ブラウザ Cookie", "cookies_help": "任意：そのブラウザでアクセスできる動画だけにブラウザを選択してください。アプリは Cookie をコピー・保存せず、ダウンロード中に現在のローカルブラウザセッションだけを読み取ります。", "save": "ローカルに保存", "close": "キャンセル",
        "missing_settings": "設定が不足しています", "base_model_required": "ベース URL とモデルが必要です。", "saved": "設定をローカルの .env に保存しました（Git では無視されます）。",
        "choose_video_title": "動画を選択", "choose_video_error": "動画を選択", "choose_video_error_text": "存在する動画ファイルを選択してください。",
        "video_file": "動画ファイル", "video_url": "動画 URL", "download_video": "動画をダウンロード", "download_note": "yt-dlp が対応する公開動画 URL（YouTube、Bilibili など）に対応しています。所有または利用許可のあるコンテンツのみダウンロードしてください。",
        "url_error": "http:// または https:// で始まる有効な動画 URL を入力してください。", "downloading": "動画をダウンロード中…", "downloaded": "動画をダウンロードしました", "download_error": "ダウンロードに失敗しました", "youtube_403": "YouTube がダウンロードを拒否しました（HTTP 403）。yt-dlp を更新して再試行してください。ログイン済みブラウザで動画を視聴できる場合は、「設定 → 動画ダウンロード用ブラウザ Cookie」でそのブラウザを選択して再試行してください。",
        "configure_translation": "翻訳を設定", "configure_translation_text": "設定で自分の API キーを入力するか、ローカル Ollama モデルを選択してください。",
        "loading": "Whisper モデルを読み込み中…", "transcribing": "Whisper でローカル文字起こし中…", "canceling": "現在の処理後にキャンセルします…", "cancel_requested": "キャンセルを要求しました。",
        "completed": "完了", "stopped": "停止", "captions_created": "字幕を作成しました", "saved_caption": "字幕ファイルを保存しました：", "transcribe_first": "最初に Whisper 字幕を作成", "transcribe_first_text": "先に動画を選択してタイミング付き Whisper 字幕を作成してから、現在の字幕を翻訳してください。", "whisper_completed": "Whisper 字幕を作成しました", "translation_completed": "二言語字幕を作成しました", "cuda_unavailable": "NVIDIA CUDA を開始できません。対応する NVIDIA CUDA ランタイムをインストールして再試行してください。",
    },
    "es": {
        "app_title": "Auto Caption Studio", "settings": "⚙ Ajustes", "subtitle": "Transcripción con Whisper + traducción con tu LLM → subtítulos bilingües de Aegisub",
        "video": "1. Vídeo", "choose_video": "Elegir vídeo…", "caption_settings": "2. Ajustes de subtítulos", "whisper_model": "Modelo Whisper",
        "spoken_language": "Idioma hablado", "translate_to": "Traducir a", "whisper_processing": "Procesamiento de Whisper", "transcribe": "1. Crear subtítulos Whisper", "translate": "2. Traducir subtítulos actuales", "cancel": "Cancelar",
        "preview": "Vista previa", "start": "Inicio", "end": "Fin", "original": "Original (Whisper)", "translation": "Traducción",
        "ready": "Elige un vídeo y luego pulsa Crear subtítulos.", "initial_log": "Listo. Abre Ajustes para configurar el proveedor de traducción.",
        "auto_detect": "Detectar automáticamente", "settings_title": "Ajustes del LLM", "provider": "Proveedor", "base_url": "URL base", "model": "Modelo",
        "api_key": "Clave API", "ui_language": "Idioma de la interfaz", "browser_cookies": "Cookies del navegador para descargas", "cookies_help": "Opcional: selecciona un navegador solo para vídeos a los que puedas acceder allí. La aplicación no copia ni guarda cookies; yt-dlp solo lee la sesión local actual durante la descarga.", "save": "Guardar localmente", "close": "Cancelar",
        "missing_settings": "Faltan ajustes", "base_model_required": "Se requieren la URL base y el modelo.", "saved": "Ajustes guardados en .env local (Git lo ignora).",
        "choose_video_title": "Seleccionar vídeo", "choose_video_error": "Elige un vídeo", "choose_video_error_text": "Primero selecciona un archivo de vídeo existente.",
        "video_file": "Archivo de vídeo", "video_url": "URL del vídeo", "download_video": "Descargar vídeo", "download_note": "Admite URL públicas que maneja yt-dlp (por ejemplo, YouTube y Bilibili). Descarga solo contenido propio o autorizado.",
        "url_error": "Introduce una URL de vídeo válida que empiece por http:// o https://.", "downloading": "Descargando vídeo…", "downloaded": "Vídeo descargado", "download_error": "Error de descarga", "youtube_403": "YouTube rechazó la descarga (HTTP 403). Actualiza yt-dlp e inténtalo de nuevo. Si puedes ver el vídeo con sesión iniciada en un navegador, selecciónalo en Ajustes → Cookies del navegador y vuelve a intentarlo.",
        "configure_translation": "Configurar traducción", "configure_translation_text": "Abre Ajustes e introduce tu clave API, o elige Ollama para un modelo local.",
        "loading": "Cargando modelo Whisper…", "transcribing": "Transcribiendo localmente con Whisper…", "canceling": "Se cancelará tras el paso actual…", "cancel_requested": "Cancelación solicitada.",
        "completed": "Completado", "stopped": "Detenido", "captions_created": "Subtítulos creados", "saved_caption": "Archivo de subtítulos guardado:", "transcribe_first": "Primero crea los subtítulos Whisper", "transcribe_first_text": "Primero elige un vídeo y crea los subtítulos Whisper con tiempos. Luego podrás traducir los subtítulos actuales.", "whisper_completed": "Subtítulos Whisper creados", "translation_completed": "Subtítulos bilingües creados", "cuda_unavailable": "No se pudo iniciar NVIDIA CUDA. Instala el tiempo de ejecución de NVIDIA CUDA correspondiente e inténtalo de nuevo.",
    },
}


@dataclass
class Cue:
    start: float
    end: float
    original: str
    translation: str = ""


class SettingsStore:
    DEFAULTS = {
        "LLM_PROVIDER": "openai_compatible",
        "LLM_BASE_URL": "https://api.openai.com/v1",
        "LLM_MODEL": "gpt-4o-mini",
        "LLM_API_KEY": "",
        "LLM_USER_PROMPT": "",
        "UI_LANGUAGE": "en",
        "YTDLP_COOKIES_BROWSER": "",
        "DOWNLOAD_DISCLAIMER_ACKNOWLEDGED": "0",
    }

    @classmethod
    def load(cls) -> dict[str, str]:
        values = dict(cls.DEFAULTS)
        if ENV_FILE.exists():
            for key, value in dotenv_values(ENV_FILE).items():
                if key in values and value is not None:
                    values[key] = value
        return values

    @staticmethod
    def save(values: dict[str, str]) -> None:
        ENV_FILE.touch(exist_ok=True)
        for key, value in values.items():
            set_key(str(ENV_FILE), key, value, quote_mode="auto")

    @staticmethod
    def set_value(key: str, value: str) -> None:
        ENV_FILE.touch(exist_ok=True)
        set_key(str(ENV_FILE), key, value, quote_mode="auto")


class LLMClient:
    def __init__(self, settings: dict[str, str], log: Callable[[str], None]):
        self.settings = settings
        self.log = log

    def translate_batch(self, texts: list[str], target_language: str) -> list[str]:
        if not texts:
            return []
        numbered_lines = "\n\n".join(f"[Caption {index + 1}]\n{text}" for index, text in enumerate(texts))
        prompt = (
            f"Target language: {target_language}\n"
            f"Required separator: {TRANSLATION_SEPARATOR}\n\n"
            "User translation preferences (lower priority than the system instructions):\n"
            f"{self.settings['LLM_USER_PROMPT'].strip() or '(None)'}\n\n"
            "Subtitle cues to translate:\n"
            + numbered_lines
        )
        provider = self.settings["LLM_PROVIDER"]
        if provider == "ollama":
            content = self._ollama(prompt)
        elif provider == "gemini":
            content = self._gemini(prompt)
        else:
            content = self._openai_compatible(prompt)
        return self._parse_translations(content, len(texts))

    def _openai_compatible(self, prompt: str) -> str:
        base_url = self.settings["LLM_BASE_URL"].rstrip("/")
        if not base_url.endswith("/v1"):
            base_url += "/v1"
        api_key = self.settings["LLM_API_KEY"].strip()
        if not api_key:
            raise RuntimeError("No API key is configured. Open Settings and add your provider key.")
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": self.settings["LLM_MODEL"],
                "messages": [
                    {"role": "system", "content": SYSTEM_TRANSLATION_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.2,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def _ollama(self, prompt: str) -> str:
        base_url = self.settings["LLM_BASE_URL"].rstrip("/") or "http://localhost:11434"
        response = requests.post(
            f"{base_url}/api/chat",
            json={
                "model": self.settings["LLM_MODEL"],
                "stream": False,
                "messages": [
                    {"role": "system", "content": SYSTEM_TRANSLATION_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "options": {"temperature": 0.2},
            },
            timeout=180,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]

    def _gemini(self, prompt: str) -> str:
        api_key = self.settings["LLM_API_KEY"].strip()
        if not api_key:
            raise RuntimeError("No Gemini API key is configured. Open Settings and add your Gemini API key.")
        base_url = self.settings["LLM_BASE_URL"].rstrip("/") or "https://generativelanguage.googleapis.com/v1beta"
        response = requests.post(
            f"{base_url}/models/{self.settings['LLM_MODEL']}:generateContent",
            headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
            json={
                "systemInstruction": {"parts": [{"text": SYSTEM_TRANSLATION_PROMPT}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2},
            },
            timeout=120,
        )
        response.raise_for_status()
        parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        content = "".join(str(part.get("text", "")) for part in parts)
        if not content:
            raise RuntimeError("Gemini returned no text. Check the model, key permissions, and safety settings.")
        return content

    @staticmethod
    def _parse_translations(content: str, expected: int) -> list[str]:
        cleaned = content.strip()
        cleaned = re.sub(r"^```(?:text)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        translations = [part.strip() for part in cleaned.split(TRANSLATION_SEPARATOR)]
        if len(translations) != expected or any(not item for item in translations):
            raise RuntimeError(
                f"The LLM returned {len(translations)} caption blocks; expected {expected}. "
                "Try again, or use a model that follows delimiter instructions reliably."
            )
        return translations


def ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def ass_escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}").replace("\n", r"\N")


def clean_download_percent(value: object) -> str:
    """Turn yt-dlp's terminal-formatted percentage into Unicode-safe plain text."""
    plain = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(value))
    match = re.search(r"\d+(?:\.\d+)?%", plain)
    return match.group(0) if match else ""


def clean_terminal_text(value: object) -> str:
    """Remove terminal formatting before showing a yt-dlp error in the GUI."""
    return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", str(value)).strip()


def bundled_deno_path() -> Path | None:
    """Return the Deno runtime packaged beside the Windows application."""
    for candidate in (APP_DIR / "deno.exe", APP_DIR / "_internal" / "deno.exe"):
        if candidate.is_file():
            return candidate
    return None


def parse_ass_time(value: str) -> float:
    try:
        hours, minutes, seconds = value.strip().split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid ASS timestamp: {value!r}") from exc


def ass_unescape_for_translation(text: str) -> str:
    text = re.sub(r"\{[^}]*\}", "", text)
    return text.replace(r"\N", "\n").replace(r"\n", "\n").replace(r"\h", " ").strip()


def load_ass_cues(ass_path: Path) -> list[Cue]:
    """Load timed non-translation dialogue events from an Aegisub ASS file."""
    try:
        source = ass_path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        source = ass_path.read_text(encoding="utf-8")

    cues: list[Cue] = []
    for line in source.splitlines():
        if not line.lstrip().lower().startswith("dialogue:"):
            continue
        fields = line.split(":", 1)[1].split(",", 9)
        if len(fields) != 10:
            continue
        style = fields[3].strip().lower()
        if style == "translation":
            continue
        text = ass_unescape_for_translation(fields[9])
        if not text:
            continue
        start, end = parse_ass_time(fields[1]), parse_ass_time(fields[2])
        if end > start:
            cues.append(Cue(start, end, text))
    if not cues:
        raise ValueError("No timed dialogue lines were found in this .ass file.")
    return cues


def bilingual_ass_path(source: Path) -> Path:
    stem = source.stem
    if stem.endswith(".whisper"):
        stem = stem.removesuffix(".whisper")
    return source.with_name(f"{stem}.bilingual.ass")


def write_ass(cues: list[Cue], output_path: Path, include_translation: bool = True) -> None:
    header = """[Script Info]
; Generated by Auto Caption Studio
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Original,Arial,50,&H00FFFFFF,&H000000FF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,3,1,2,90,90,62,1
Style: Translation,Arial,50,&H00B7F5FF,&H000000FF,&H00101010,&H90000000,0,0,0,0,100,100,0,0,1,3,1,2,90,90,132,1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    lines = [header]
    for cue in cues:
        start, end = ass_time(cue.start), ass_time(max(cue.end, cue.start + 0.1))
        lines.append(f"Dialogue: 0,{start},{end},Original,,0,0,0,,{ass_escape(cue.original)}\n")
        if include_translation:
            lines.append(f"Dialogue: 1,{start},{end},Translation,,0,0,0,,{ass_escape(cue.translation)}\n")
    output_path.write_text("".join(lines), encoding="utf-8-sig")


class SettingsDialog(tk.Toplevel):
    PROVIDER_LABELS = {
        "OpenAI-compatible": "openai_compatible",
        "Google Gemini": "gemini",
        "Ollama (local)": "ollama",
    }

    def __init__(self, parent: "CaptionApp") -> None:
        super().__init__(parent)
        self.parent = parent
        self.title(parent.t("settings_title"))
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        values = SettingsStore.load()

        self.provider = tk.StringVar(value=next(label for label, code in self.PROVIDER_LABELS.items() if code == values["LLM_PROVIDER"]))
        self.base_url = tk.StringVar(value=values["LLM_BASE_URL"])
        self.model = tk.StringVar(value=values["LLM_MODEL"])
        self.api_key = tk.StringVar(value=values["LLM_API_KEY"])
        self.user_prompt = values["LLM_USER_PROMPT"]
        self.ui_language = tk.StringVar(value=next(label for label, code in UI_LANGUAGE_OPTIONS.items() if code == values["UI_LANGUAGE"]))
        self.cookies_browser = tk.StringVar(value=next(label for label, code in COOKIE_BROWSER_OPTIONS.items() if code == values["YTDLP_COOKIES_BROWSER"]))
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=18)
        frame.grid(sticky="nsew")
        for row, (label, variable, widget) in enumerate([
            (self.parent.t("provider"), self.provider, "combo"),
            (self.parent.t("base_url"), self.base_url, "entry"),
            (self.parent.t("model"), self.model, "entry"),
            (self.parent.t("api_key"), self.api_key, "secret"),
            (self.parent.t("ui_language"), self.ui_language, "ui_language"),
            (self.parent.t("browser_cookies"), self.cookies_browser, "cookies"),
        ]):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6)
            if widget == "combo":
                control = ttk.Combobox(frame, textvariable=variable, values=list(self.PROVIDER_LABELS), state="readonly", width=46)
                control.bind("<<ComboboxSelected>>", self._provider_changed)
            elif widget == "ui_language":
                control = ttk.Combobox(frame, textvariable=variable, values=list(UI_LANGUAGE_OPTIONS), state="readonly", width=46)
            elif widget == "cookies":
                control = ttk.Combobox(frame, textvariable=variable, values=list(COOKIE_BROWSER_OPTIONS), state="readonly", width=46)
            else:
                control = ttk.Entry(frame, textvariable=variable, width=49, show="•" if widget == "secret" else "")
            control.grid(row=row, column=1, sticky="ew", pady=6)

        ttk.Label(frame, text="Translation instructions (lower priority)").grid(row=6, column=0, sticky="nw", pady=6)
        self.user_prompt_box = tk.Text(frame, width=46, height=5, wrap="word")
        self.user_prompt_box.grid(row=6, column=1, sticky="ew", pady=6)
        self.user_prompt_box.insert("1.0", self.user_prompt)
        ttk.Label(
            frame,
            text="Optional style or terminology preferences. The app's system rules always take priority and keep subtitle timing, order, and separator formatting intact.",
            wraplength=420,
            foreground="#475569",
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(2, 8))
        self.help_label = ttk.Label(frame, wraplength=420, foreground="#475569")
        self.help_label.grid(row=8, column=0, columnspan=2, sticky="w", pady=(2, 14))
        self._provider_changed()
        buttons = ttk.Frame(frame)
        buttons.grid(row=9, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text=self.parent.t("close"), command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(buttons, text=self.parent.t("save"), command=self._save).grid(row=0, column=1)

    def _provider_changed(self, _event=None) -> None:
        provider = self.PROVIDER_LABELS[self.provider.get()]
        if provider == "ollama":
            if self.base_url.get().endswith("/v1"):
                self.base_url.set("http://localhost:11434")
            self.help_label.configure(text="Ollama uses its local server. An API key is usually not needed. Example model: qwen2.5:7b\n\n" + self.parent.t("cookies_help"))
        elif provider == "gemini":
            self.base_url.set("https://generativelanguage.googleapis.com/v1beta")
            if self.model.get() in {"", "gpt-4o-mini", "qwen2.5:7b"}:
                self.model.set("gemini-3.5-flash")
            self.help_label.configure(text="Gemini uses your Google AI Studio API key. The key is stored only in this app's ignored .env file.\n\n" + self.parent.t("cookies_help"))
        else:
            if self.base_url.get() in {"http://localhost:11434", "https://generativelanguage.googleapis.com/v1beta"}:
                self.base_url.set("https://api.openai.com/v1")
            self.help_label.configure(text="Works with OpenAI and compatible APIs. Your key is stored only in this app's ignored .env file.\n\n" + self.parent.t("cookies_help"))

    def _save(self) -> None:
        if not self.base_url.get().strip() or not self.model.get().strip():
            messagebox.showerror(self.parent.t("missing_settings"), self.parent.t("base_model_required"), parent=self)
            return
        SettingsStore.save({
            "LLM_PROVIDER": self.PROVIDER_LABELS[self.provider.get()],
            "LLM_BASE_URL": self.base_url.get().strip(),
            "LLM_MODEL": self.model.get().strip(),
            "LLM_API_KEY": self.api_key.get().strip(),
            "LLM_USER_PROMPT": self.user_prompt_box.get("1.0", "end-1c").strip(),
            "UI_LANGUAGE": UI_LANGUAGE_OPTIONS[self.ui_language.get()],
            "YTDLP_COOKIES_BROWSER": COOKIE_BROWSER_OPTIONS[self.cookies_browser.get()],
        })
        self.parent.set_ui_language(UI_LANGUAGE_OPTIONS[self.ui_language.get()])
        self.parent.log(self.parent.t("saved"))
        self.destroy()


class CaptionApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.ui_language = SettingsStore.load()["UI_LANGUAGE"]
        self.title(self.t("app_title"))
        self.geometry("900x650")
        self.minsize(780, 540)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel_requested = threading.Event()
        self.cues: list[Cue] = []
        self.caption_output_dir: Path | None = None
        self.caption_video_path: Path | None = None
        self.caption_ass_path: Path | None = None

        self.video_path = tk.StringVar()
        self.video_url = tk.StringVar()
        self.whisper_model = tk.StringVar(value="medium")
        self.whisper_device = tk.StringVar(value="CUDA")
        self.source_language = tk.StringVar(value=self.t("auto_detect"))
        self.target_language = tk.StringVar(value=UI_LANGUAGE_TARGETS.get(self.ui_language, "English"))
        self.status = tk.StringVar(value=self.t("ready"))
        self._configure_style()
        self._build()
        self.after(120, self._drain_events)

    def t(self, key: str) -> str:
        return UI_TEXT.get(self.ui_language, UI_TEXT["en"])[key]

    def set_ui_language(self, language: str) -> None:
        if language == self.ui_language:
            return
        auto_detect_selected = self.source_language.get() == self.t("auto_detect")
        self.ui_language = language
        self.target_language.set(UI_LANGUAGE_TARGETS.get(language, "English"))
        self.title(self.t("app_title"))
        for child in self.winfo_children():
            child.destroy()
        if auto_detect_selected:
            self.source_language.set(self.t("auto_detect"))
        self.status.set(self.t("ready"))
        self._build()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
        style.configure("Subtle.TLabel", foreground="#52606d")
        style.configure("Accent.TButton", font=("Segoe UI", 10, "bold"))

    def _build(self) -> None:
        outer = ttk.Frame(self, padding=20)
        outer.pack(fill="both", expand=True)
        heading = ttk.Frame(outer)
        heading.pack(fill="x", pady=(0, 16))
        ttk.Label(heading, text=self.t("app_title"), style="Title.TLabel").pack(side="left")
        ttk.Button(heading, text=self.t("settings"), command=lambda: SettingsDialog(self)).pack(side="right")
        ttk.Label(outer, text=self.t("subtitle"), style="Subtle.TLabel").pack(anchor="w", pady=(0, 18))

        source = ttk.LabelFrame(outer, text=self.t("video"), padding=12)
        source.pack(fill="x")
        source.columnconfigure(1, weight=1)
        ttk.Label(source, text=self.t("video_file")).grid(row=0, column=0, sticky="w", padx=(0, 8), pady=(0, 6))
        ttk.Entry(source, textvariable=self.video_path).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))
        self.choose_button = ttk.Button(source, text=self.t("choose_video"), command=self._choose_video)
        self.choose_button.grid(row=0, column=2, pady=(0, 6))
        self.open_ass_button = ttk.Button(source, text="Open existing .ass captions…", command=self._open_ass)
        self.open_ass_button.grid(row=0, column=3, padx=(8, 0), pady=(0, 6))
        ttk.Label(source, text=self.t("video_url")).grid(row=1, column=0, sticky="w", padx=(0, 8))
        ttk.Entry(source, textvariable=self.video_url).grid(row=1, column=1, sticky="ew", padx=(0, 8))
        self.download_button = ttk.Button(source, text=self.t("download_video"), command=self._start_download)
        self.download_button.grid(row=1, column=2)
        ttk.Label(source, text=self.t("download_note"), style="Subtle.TLabel", wraplength=760).grid(row=2, column=0, columnspan=3, sticky="w", pady=(9, 0))

        options = ttk.LabelFrame(outer, text=self.t("caption_settings"), padding=12)
        options.pack(fill="x", pady=14)
        options.columnconfigure((1, 3, 5), weight=1)
        ttk.Label(options, text=self.t("whisper_model")).grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Combobox(options, textvariable=self.whisper_model, values=["tiny", "base", "small", "medium", "large-v3"], state="readonly", width=14).grid(row=0, column=1, sticky="ew", padx=(0, 18))
        ttk.Label(options, text=self.t("spoken_language")).grid(row=0, column=2, sticky="w", padx=(0, 6))
        ttk.Combobox(options, textvariable=self.source_language, values=[self.t("auto_detect"), *LANGUAGE_CHOICES], state="readonly", width=18).grid(row=0, column=3, sticky="ew", padx=(0, 18))
        ttk.Label(options, text=self.t("translate_to")).grid(row=0, column=4, sticky="w", padx=(0, 6))
        ttk.Combobox(options, textvariable=self.target_language, values=LANGUAGE_CHOICES, width=22).grid(row=0, column=5, sticky="ew")
        ttk.Label(options, text=self.t("whisper_processing")).grid(row=1, column=0, sticky="w", padx=(0, 6), pady=(10, 0))
        ttk.Combobox(options, textvariable=self.whisper_device, values=list(WHISPER_DEVICE_OPTIONS), state="readonly", width=18).grid(row=1, column=1, sticky="ew", padx=(0, 18), pady=(10, 0))

        action = ttk.Frame(outer)
        action.pack(fill="x", pady=(0, 12))
        self.transcribe_button = ttk.Button(action, text=self.t("transcribe"), style="Accent.TButton", command=self._start_transcription)
        self.transcribe_button.pack(side="left")
        self.translate_button = ttk.Button(action, text=self.t("translate"), command=self._start_translation, state="normal" if self.cues else "disabled")
        self.translate_button.pack(side="left", padx=(8, 0))
        self.cancel_button = ttk.Button(action, text=self.t("cancel"), command=self._cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=8)
        ttk.Label(action, textvariable=self.status, style="Subtle.TLabel").pack(side="right")

        preview = ttk.LabelFrame(outer, text=self.t("preview"), padding=8)
        preview.pack(fill="both", expand=True)
        columns = ("start", "end", "original", "translation")
        self.table = ttk.Treeview(preview, columns=columns, show="headings")
        for key, title, width in [("start", self.t("start"), 82), ("end", self.t("end"), 82), ("original", self.t("original"), 300), ("translation", self.t("translation"), 300)]:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, stretch=key in ("original", "translation"))
        scrollbar = ttk.Scrollbar(preview, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.log_box = tk.Text(outer, height=5, wrap="word", state="disabled", bg="#f8fafc", relief="flat")
        self.log_box.pack(fill="x", pady=(14, 0))
        self.log(self.t("initial_log"))

    def _choose_video(self) -> None:
        DOWNLOADS_DIR.mkdir(exist_ok=True)
        path = filedialog.askopenfilename(
            title=self.t("choose_video_title"),
            initialdir=str(DOWNLOADS_DIR),
            filetypes=[("Video files", "*.mp4 *.mkv *.mov *.avi *.webm *.m4v"), ("All files", "*.*")],
        )
        if path:
            self.video_path.set(path)
            self.caption_output_dir = None
            self.caption_video_path = None
            self.caption_ass_path = None
            self.translate_button.configure(state="disabled")

    def _open_ass(self) -> None:
        path = filedialog.askopenfilename(
            title="Open Aegisub subtitle file",
            initialdir=str(OUTPUT_DIR if OUTPUT_DIR.exists() else APP_DIR),
            filetypes=[("Aegisub subtitle files", "*.ass"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            ass_path = Path(path)
            self.cues = load_ass_cues(ass_path)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not open captions", str(exc), parent=self)
            return
        self.video_path.set("")
        self.caption_output_dir = ass_path.parent
        self.caption_video_path = None
        self.caption_ass_path = ass_path
        self._refresh_table()
        self.translate_button.configure(state="normal")
        self.status.set("ASS captions loaded")
        self.log(f"Loaded {len(self.cues)} timed captions: {ass_path}")

    def _start_download(self) -> None:
        url = self.video_url.get().strip()
        if not re.match(r"^https?://", url, flags=re.IGNORECASE):
            messagebox.showerror(self.t("download_error"), self.t("url_error"), parent=self)
            return
        if SettingsStore.load()["DOWNLOAD_DISCLAIMER_ACKNOWLEDGED"] != "1":
            accepted = messagebox.askyesno(
                "Download disclaimer",
                "Please confirm:\n\n"
                "• You will download only content you own or are authorized to download.\n"
                "• You will comply with the video platform's terms, copyright, and local laws.\n"
                "• This app does not bypass paywalls, regional restrictions, DRM, or access controls.\n\n"
                "Continue with the download?",
                icon="warning",
                parent=self,
            )
            if not accepted:
                return
            SettingsStore.set_value("DOWNLOAD_DISCLAIMER_ACKNOWLEDGED", "1")
        self.download_button.configure(state="disabled")
        self.choose_button.configure(state="disabled")
        self.open_ass_button.configure(state="disabled")
        self.transcribe_button.configure(state="disabled")
        self.translate_button.configure(state="disabled")
        self.status.set(self.t("downloading"))
        self.log(self.t("downloading"))
        threading.Thread(target=self._download_video, args=(url,), daemon=True).start()

    def _download_video(self, url: str) -> None:
        try:
            import yt_dlp

            downloads_dir = DOWNLOADS_DIR
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = downloads_dir / f"video_caption_{timestamp}"
            attempt = 2
            while output_dir.exists():
                output_dir = downloads_dir / f"video_caption_{timestamp}_{attempt}"
                attempt += 1
            output_dir.mkdir(parents=True)

            app = self

            class DownloadLogger:
                def debug(self, _message: str) -> None:
                    pass

                def warning(self, message: str) -> None:
                    app.events.put(("log", f"yt-dlp: {message}"))

                def error(self, message: str) -> None:
                    app.events.put(("log", f"yt-dlp: {message}"))

            def progress_hook(data: dict) -> None:
                if data.get("status") == "downloading":
                    percent = clean_download_percent(data.get("_percent_str", ""))
                    if percent:
                        app.events.put(("status", f"{app.t('downloading')} {percent}"))

            options = {
                # Prefer a single audio+video stream so transcription works without FFmpeg.
                "format": "best[acodec!=none][vcodec!=none]/best",
                "outtmpl": str(output_dir / "video.%(ext)s"),
                "noplaylist": True,
                "quiet": True,
                "no_warnings": True,
                "logger": DownloadLogger(),
                "progress_hooks": [progress_hook],
            }
            if deno_path := bundled_deno_path():
                # Current yt-dlp YouTube support requires an external JS
                # runtime. The portable Windows build includes Deno.
                options["js_runtimes"] = {"deno": {"path": str(deno_path)}}
            cookies_browser = SettingsStore.load()["YTDLP_COOKIES_BROWSER"].strip()
            if cookies_browser:
                options["cookiesfrombrowser"] = (cookies_browser,)
            with yt_dlp.YoutubeDL(options) as downloader:
                downloader.extract_info(url, download=True)

            video_extensions = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".m4v", ".flv", ".ts"}
            media_files = [path for path in output_dir.iterdir() if path.is_file() and path.suffix.lower() in video_extensions]
            if not media_files:
                raise RuntimeError("The download finished, but no usable video file was created.")
            video = max(media_files, key=lambda path: path.stat().st_mtime)
            self.events.put(("downloaded", video))
        except Exception as exc:
            message = clean_terminal_text(exc)
            if "HTTP Error 403" in message and ("youtube" in url.lower() or "youtu.be" in url.lower()):
                message = self.t("youtube_403") + "\n\nDetails: " + message
            self.events.put(("download_error", message))

    def _start_transcription(self) -> None:
        video = Path(self.video_path.get())
        if not video.is_file():
            messagebox.showerror(self.t("choose_video_error"), self.t("choose_video_error_text"), parent=self)
            return
        self.transcribe_button.configure(state="disabled")
        self.translate_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.cancel_requested.clear()
        self.cues = []
        self.caption_output_dir = None
        self.caption_video_path = None
        self.caption_ass_path = None
        self._refresh_table()
        source_language = None if self.source_language.get() == self.t("auto_detect") else WHISPER_LANGUAGE_CODES.get(self.source_language.get())
        threading.Thread(
            target=self._transcribe,
            args=(video, self.whisper_model.get(), source_language, WHISPER_DEVICE_OPTIONS[self.whisper_device.get()]),
            daemon=True,
        ).start()

    def _transcribe(self, video: Path, whisper_model: str, source_language: str | None, device: str) -> None:
        try:
            self.events.put(("status", self.t("loading")))
            from faster_whisper import WhisperModel
            compute_type = "float16" if device == "cuda" else "int8"
            model = WhisperModel(whisper_model, device=device, compute_type=compute_type)
            self.events.put(("log", self.t("transcribing")))
            segments, info = model.transcribe(str(video), language=source_language, word_timestamps=True, vad_filter=True)
            cues: list[Cue] = []
            for segment in segments:
                if self.cancel_requested.is_set():
                    return
                text = segment.text.strip()
                if text:
                    cues.append(Cue(segment.start, segment.end, text))
            if not cues:
                raise RuntimeError("Whisper did not find any spoken dialogue in this video.")
            self.events.put(("log", f"Transcribed {len(cues)} timed segments (detected language: {info.language})."))
            self.events.put(("preview", cues))
            project_dir = self._create_output_folder()
            copied_video = project_dir / video.name
            shutil.copy2(video, copied_video)
            output = project_dir / f"{copied_video.stem}.whisper.ass"
            write_ass(cues, output, include_translation=False)
            self.events.put(("whisper_done", (output, copied_video)))
        except Exception as exc:
            message = str(exc)
            if "cublas64_12.dll" in message or "cudnn" in message.lower():
                message = self.t("cuda_unavailable") + "\n\nDetails: " + message
            self.events.put(("error", message))

    def _start_translation(self) -> None:
        if not self.cues:
            messagebox.showwarning(self.t("transcribe_first"), self.t("transcribe_first_text"), parent=self)
            return
        settings = SettingsStore.load()
        if settings["LLM_PROVIDER"] != "ollama" and not settings["LLM_API_KEY"].strip():
            messagebox.showwarning(self.t("configure_translation"), self.t("configure_translation_text"), parent=self)
            return
        if self.caption_ass_path is None:
            messagebox.showwarning(self.t("transcribe_first"), self.t("transcribe_first_text"), parent=self)
            return
        if not self.caption_ass_path.is_file():
            messagebox.showerror("Could not open captions", "The selected .ass caption file is no longer available.", parent=self)
            return
        self.transcribe_button.configure(state="disabled")
        self.translate_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.cancel_requested.clear()
        threading.Thread(target=self._translate, args=(self.caption_ass_path, settings, list(self.cues), self.target_language.get().strip()), daemon=True).start()

    def _translate(self, source_ass: Path, settings: dict[str, str], cues: list[Cue], target_language: str) -> None:
        try:
            client = LLMClient(settings, lambda msg: self.events.put(("log", msg)))
            batch_size = 12
            for index in range(0, len(cues), batch_size):
                if self.cancel_requested.is_set():
                    return
                batch = cues[index:index + batch_size]
                self.events.put(("status", f"Translating {index + 1}–{min(index + batch_size, len(cues))} of {len(cues)}…"))
                translations = client.translate_batch([cue.original for cue in batch], target_language)
                for cue, translation in zip(batch, translations):
                    cue.translation = translation
                self.events.put(("preview", cues))

            output = bilingual_ass_path(source_ass)
            write_ass(cues, output)
            self.events.put(("translation_done", output))
        except Exception as exc:
            self.events.put(("error", str(exc)))

    def _cancel(self) -> None:
        self.cancel_requested.set()
        self.status.set(self.t("canceling"))
        self.log(self.t("cancel_requested"))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status.set(str(payload))
                elif kind == "log":
                    self.log(str(payload))
                elif kind == "preview":
                    self.cues = list(payload)  # type: ignore[arg-type]
                    self._refresh_table()
                elif kind == "downloaded":
                    path = Path(payload)  # type: ignore[arg-type]
                    self.video_path.set(str(path))
                    self.video_url.set("")
                    self.caption_output_dir = None
                    self.caption_video_path = None
                    self.caption_ass_path = None
                    self.download_button.configure(state="normal")
                    self.choose_button.configure(state="normal")
                    self.open_ass_button.configure(state="normal")
                    self.transcribe_button.configure(state="normal")
                    self.translate_button.configure(state="disabled")
                    self.status.set(self.t("downloaded"))
                    self.log(f"{self.t('downloaded')}: {path}\nCaption folder: {path.parent}")
                elif kind == "download_error":
                    self.download_button.configure(state="normal")
                    self.choose_button.configure(state="normal")
                    self.open_ass_button.configure(state="normal")
                    self.transcribe_button.configure(state="normal")
                    self.translate_button.configure(state="normal" if self.cues else "disabled")
                    self.status.set(self.t("stopped"))
                    self.log(f"{self.t('download_error')}: {payload}")
                    messagebox.showerror(self.t("download_error"), str(payload), parent=self)
                elif kind == "whisper_done":
                    self._finish()
                    path, copied_video = payload  # type: ignore[misc]
                    path = Path(path)
                    self.caption_video_path = Path(copied_video)
                    self.caption_output_dir = path.parent
                    self.caption_ass_path = path
                    self.status.set(self.t("completed"))
                    self.log(f"Saved Whisper project: {path.parent}")
                    messagebox.showinfo(self.t("whisper_completed"), f"{self.t('saved_caption')}\n{path}", parent=self)
                elif kind == "translation_done":
                    self._finish()
                    path = Path(payload)  # type: ignore[arg-type]
                    self.status.set(self.t("completed"))
                    self.log(f"Saved bilingual Aegisub captions: {path}")
                    messagebox.showinfo(self.t("translation_completed"), f"{self.t('saved_caption')}\n{path}", parent=self)
                elif kind == "error":
                    self._finish()
                    self.status.set(self.t("stopped"))
                    self.log(f"Error: {payload}")
                    messagebox.showerror("Could not create captions", str(payload), parent=self)
        except queue.Empty:
            pass
        self.after(120, self._drain_events)

    def _finish(self) -> None:
        self.transcribe_button.configure(state="normal")
        self.translate_button.configure(state="normal" if self.cues else "disabled")
        self.cancel_button.configure(state="disabled")

    @staticmethod
    def _create_output_folder() -> Path:
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        folder = OUTPUT_DIR / f"video_{timestamp}"
        number = 2
        while folder.exists():
            folder = OUTPUT_DIR / f"video_{timestamp}_{number}"
            number += 1
        folder.mkdir()
        return folder

    def _refresh_table(self) -> None:
        self.table.delete(*self.table.get_children())
        for cue in self.cues:
            self.table.insert("", "end", values=(ass_time(cue.start), ass_time(cue.end), cue.original, cue.translation))

    def log(self, message: str) -> None:
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")


if __name__ == "__main__":
    CaptionApp().mainloop()

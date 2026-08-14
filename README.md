# Auto Caption Studio

A local Python desktop app that:

1. transcribes an uploaded video with Whisper;
2. translates each timestamped caption using the LLM you configure; and
3. exports an Aegisub-compatible bilingual `.ass` subtitle file.

## Why Auto Caption Studio?

Auto Caption Studio is designed for creators and subtitle editors who want an
**ASS-first desktop workflow** without giving up control of their media or
provider choice. It combines the steps that are normally scattered across
separate tools:

- download permitted public videos into a self-contained project folder;
- create local, CUDA-accelerated Whisper captions;
- review or import an existing timed Aegisub `.ass` file before translating;
- translate in a separate, deliberate step with OpenAI-compatible services,
  Ollama, or Google Gemini; and
- keep the video, original captions, and bilingual output together for editing
  in Aegisub.

Unlike an all-in-one web service, transcription stays on the computer and each
user configures their own translation provider. Keys and preferences are stored
locally in an ignored `.env` file, never in this repository. The app also uses
a resilient text-delimiter format for translations instead of depending on an
LLM to return perfect JSON.

## Two-step workflow

1. Select or download a video, then click **Create Whisper captions**. This runs local transcription and saves `<video>.whisper.ass` with timing and original dialogue only.
2. Review the transcript in the preview, select a target language, then click **Translate current captions**. This sends only the current transcript to your configured LLM and saves `<video>.bilingual.ass` with both original and translated lines.
3. To translate existing subtitles without Whisper, click **Open existing .ass captions…**, select a timed Aegisub `.ass` file, choose the target language, and click **Translate current captions**. The app reads non-`Translation` dialogue lines and writes a sibling `.bilingual.ass` file.

Each Whisper run creates `output/video_YYYYMMDD_HHMMSS/` inside the app folder. It contains a copy of the selected video and its `.whisper.ass` file. Translation adds the `.bilingual.ass` file to that exact same folder.

For translation, the app requests plain text blocks separated by an internal marker; it does not require the selected LLM to generate JSON. This works more reliably with models that do not consistently follow JSON-only instructions.

## Whisper CUDA processing

Whisper transcription uses **CUDA**. Install the required NVIDIA CUDA libraries before running transcription. The app defaults to the **medium** Whisper model and CUDA processing. The target translation language automatically follows the selected interface language: English, Simplified Chinese, Japanese, or Spanish.

If CUDA reports that `cublas64_12.dll` is missing, install the NVIDIA CUDA 12.x toolkit and the compatible cuDNN runtime, then restart the application. The CUDA `bin` folder containing `cublas64_12.dll` must be on Windows `PATH`. Current Faster-Whisper guidance uses CUDA 12 and cuDNN 9; library requirements can differ by installed CTranslate2 version, so use the Faster-Whisper documentation for the version you install. The Microsoft Visual C++ runtime is also required on Windows.

You can also paste a public video URL and use **Download video**. The app uses `yt-dlp`, which supports popular sites including YouTube and Bilibili. Every URL download is saved to a new local folder named `downloads/video_caption_YYYYMMDD_HHMMSS`; both the downloaded video and generated caption file stay together there. Download only content you own or are authorized to use.

The first URL download shows a one-time disclaimer. Continuing confirms that you have permission to download the content and will follow platform terms, copyright, and applicable laws. The app does not bypass paywalls, DRM, regional restrictions, or access controls.

### YouTube HTTP 403

YouTube may deny automated downloads even when the URL works in a browser. First update the app dependencies with `pip install -U -r requirements.txt`. If you can play the video while signed in to Chrome, Edge, Firefox, Brave, or Opera, select that browser in **Settings → Browser cookies for video downloads** and retry. This option is off by default: the app does not copy or save cookies and reads the currently local browser session only during the download. YouTube access policies can still prevent a download.

The app does not include an API key. Open **Settings** in the application to enter your own provider, endpoint, model, key, and interface language. These are saved only in `.env`, which is included in `.gitignore` and must never be committed. The interface supports English, Simplified Chinese, Japanese, and Spanish.

## Quick start

Requires Python 3.10+.

```powershell
cd <your-cloned-directory>\auto_caption_studio
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

### Windows portable app

For Windows users who do not want to install Python, download the
`AutoCaptionStudio-Windows-x64-v*.zip` asset from the latest GitHub Release.
Extract the entire archive, keep the `AutoCaptionStudio` folder intact, and run
`AutoCaptionStudio.exe`. Do not move the executable out of that folder: its
included runtime files live in the `_internal` directory beside it.

The portable build includes the Python application and its Python
dependencies, but it does not include Whisper models or NVIDIA's system CUDA
libraries. The first transcription downloads the selected Whisper model. CUDA
12.x and compatible cuDNN are still needed for GPU transcription as described
below. Some video sites also require a local FFmpeg installation for `yt-dlp`
to merge separate audio and video streams.

For a typical OpenAI-compatible service, keep the provider as **OpenAI-compatible**, choose a model, and paste the service key in Settings. For Ollama, select **Ollama** and use a local model such as `qwen2.5:7b`; no API key is normally needed.

To use **Google Gemini**, select **Google Gemini** in Settings. The app uses the Google Generative Language API (`generateContent`) with the model and Google AI Studio API key that you enter. The default endpoint is `https://generativelanguage.googleapis.com/v1beta`; leave it unchanged unless Google documents a replacement. Your Gemini key stays only in the app's ignored `.env` file.

In **Settings → Translation instructions (lower priority)**, you can add your own persistent guidance, such as preferred tone, terminology, or name spellings. The app sends this as user-level context. Its built-in system prompt has higher priority and always controls subtitle order, timing preservation, and the machine-readable separator required for export.

## Subtitle output

The `.ass` file contains two timed dialogue events for each Whisper segment:

- `Original`: the Whisper transcription, near the bottom;
- `Translation`: the selected-language translation, above it.

Both are independently editable in Aegisub. Whisper segment timing is preserved. The app uses word timestamps when available to improve timing quality.

## Git safety

`.env` is ignored before any key is entered. Keep the generated `.ass` export out of source control unless you intentionally want to version that output.

`downloads/` and `output/` are also ignored by Git, so downloaded videos and generated caption projects are never staged accidentally.

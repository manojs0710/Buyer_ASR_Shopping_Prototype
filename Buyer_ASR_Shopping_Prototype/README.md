# Buyer ASR Shopping Prototype

A working prototype of a Buyer-side grocery shopping application with
**voice shopping** powered by the `Lokii99/zaraaqtest` speech-to-text model.

Say *"Add two apples and one litre of milk"* into the microphone, and the
app transcribes it, extracts products and quantities, matches them
against the catalog, and adds them to your cart — automatically.

This is a **working prototype**, not a production system. No database,
no accounts, no payments — just enough real, working plumbing to
demonstrate the concept convincingly.

---

## Project Overview

| | |
|---|---|
| **Dashboard** | Browse, search, and filter a 32-product grocery catalog |
| **Voice Shopping** | Click the mic, speak a command, watch the cart update |
| **ASR Model** | `Lokii99/zaraaqtest`, loaded via Hugging Face Transformers |
| **Cart** | In-memory, single shared cart (add / update / remove / clear) |

---

## About the ASR model — what I found in your notebook, and what I changed

You attached **one** notebook (`aug11loki99.ipynb`) — the brief mentions
two, but only one was uploaded. I built this against the one you sent,
which does contain a working, executed pipeline (the cells ran and
produced real transcriptions), matching your instruction to use whichever
implementation is "actually functional."

**The proven working approach** (reproduced exactly in `asr_service.py`):

```python
device = 0 if torch.cuda.is_available() else -1
asr = pipeline("automatic-speech-recognition", model="Lokii99/zaraaqtest", device=device)
result = asr({"raw": audio, "sampling_rate": 16000})   # mono float32 @ 16kHz
```

**Two things I noticed in the notebook's own output, and addressed —
without changing the model or the pipeline call:**

1. **The raw output leaked special tokens**, e.g.
   `<|startoftranscript|><|ta|><|transcribe|><|notimestamps|>`. The
   `<|ta|>` tag confirms this is a **Whisper-architecture** checkpoint,
   and that your notebook's own test recordings were in Tamil/Tanglish
   (mixed with English grocery words like "Kilo", "Carrot", "Milk"). Your
   demo target is English ("Add two apples..."), so `asr_service.py`
   passes an explicit `language` hint (default `"en"`, configurable via
   `ASR_LANGUAGE` in `.env` — set it to `"ta"` if you want to demo in
   Tamil/Tanglish instead, matching your original notebook tests).
2. **The raw output also showed repeated/looping phrases**, a known
   Whisper hallucination pattern. `asr_service._clean_transcription()`
   strips leaked special tokens and collapses immediate phrase repeats
   before the text reaches the command parser. This is text
   post-processing only — the model and pipeline call are untouched.

Both are documented in `asr_service.py` itself with the reasoning inline.

**One deliberate architecture choice, explained rather than silently
made:** the notebook records audio server-side via `sounddevice` (a local
microphone attached to the machine running Python). For a real web
dashboard, the practical approach is for the **browser** to capture the
microphone and send audio to FastAPI — which is what this project does.
To avoid requiring `ffmpeg` on your machine just to decode browser audio,
the frontend encodes a 16kHz mono PCM WAV file directly in JavaScript
(via the Web Audio API), so the backend can read it with `soundfile`
exactly the way the notebook reads WAV files — same audio shape, same
`{"raw": ..., "sampling_rate": 16000}` pipeline call, one less system
dependency. `backend/test_asr_local.py` is also included, which
reproduces the notebook's own `sounddevice` approach 1:1, so you can
verify the model in isolation exactly as you did in the notebook, outside
the web app.

---

## Features

- Professional grocery dashboard: 32 products across 6 categories
- Case-insensitive live search (no page reload)
- Category filtering
- Add to cart with a quantity stepper
- Cart sidebar: update quantity, remove item, clear cart, subtotal/total
- Demo checkout confirmation
- **Voice shopping**: mic → Zaraaq ASR → command parser → cart, end to end
- Deterministic command parser (no LLM) — number words, units, plurals
- Clear error states throughout (mic permission, unknown product, backend down, etc.)

---

## Architecture

```
Browser (index.html / style.css / script.js)
   │
   │  fetch() / FormData (audio)
   ▼
FastAPI (app.py)
   │
   ├─▶ product_service.py   → data/products.json        (catalog)
   ├─▶ command_parser.py    → text → [{product, quantity}]
   ├─▶ cart_service.py      → in-memory cart
   └─▶ asr_service.py       → Lokii99/zaraaqtest via Transformers (loaded once at startup)
```

`asr_service.py` is the **only** module that talks to the ASR model, and
its job stops at producing clean text. `command_parser.py` is the
**only** module that turns text into product/quantity intent — no LLM
involved, per your instructions. Each module has one job.

---

## Technology Stack

- **Frontend:** HTML5, CSS3, vanilla JavaScript (no framework)
- **Backend:** Python, FastAPI, Uvicorn
- **ASR:** Hugging Face Transformers, PyTorch, `Lokii99/zaraaqtest`
- **Audio:** Web Audio API (browser recording + WAV encoding), `soundfile` (backend decode), `sounddevice` (standalone test script only)
- **Data:** `products.json` (catalog), in-memory dict (cart)

---

## Project Structure

```
Buyer_ASR_Shopping_Prototype/
├── backend/
│   ├── app.py                # FastAPI app - all routes, model startup, static serving
│   ├── asr_service.py        # Zaraaq model loading + transcription (see notes above)
│   ├── product_service.py    # Loads/queries data/products.json
│   ├── cart_service.py       # In-memory cart logic
│   ├── command_parser.py     # Deterministic text → product/quantity parser
│   ├── test_asr_local.py     # Standalone script mirroring the notebook exactly
│   ├── requirements.txt
│   ├── .env.example
│   └── data/
│       └── products.json
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── README.md
└── .gitignore
```

---

## Installation (Windows / VS Code)

### 1. Requirements
- Python 3.10–3.11 (PyTorch wheels lag behind the very latest Python releases)
- ~3 GB free disk space (PyTorch + the model)
- A working microphone
- Internet access the first time you run it, to download the model

### 2. Open the project in VS Code

Open the `Buyer_ASR_Shopping_Prototype` folder in VS Code, then open a
terminal: **Terminal → New Terminal**.

### 3. Create and activate a virtual environment

```powershell
cd backend
python -m venv venv
venv\Scripts\activate
```

**If PowerShell blocks activation** with a message about execution
policies, you don't need to change your system-wide policy. Either:

- Use the Command Prompt terminal instead (VS Code terminal dropdown →
  "Command Prompt"), then run `venv\Scripts\activate.bat`, **or**
- Run this once, for the current terminal session only:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  ```

### 4. Install dependencies

```powershell
pip install -r requirements.txt
```

This installs FastAPI, PyTorch, Transformers, and audio libraries. It
will take a few minutes the first time.

### 5. Configure (optional)

```powershell
copy .env.example .env
```

`Lokii99/zaraaqtest` is a public model — no API key is required. Only
edit `.env` if you want to change `ASR_LANGUAGE` (see the notebook
analysis above) or if the repository is ever made private/gated.

---

## How to Run the Backend

```powershell
python -m uvicorn app:app --reload --port 8000
```

The first request will download `Lokii99/zaraaqtest` from Hugging Face
(cached afterward). Watch the terminal for:

```
[asr_service] Device: CPU
[asr_service] Loading model: Lokii99/zaraaqtest ...
[asr_service] Model loaded successfully.
```

If you instead see `[asr_service] ERROR loading model: ...`, the rest of
the dashboard (catalog, search, cart) will still work — only voice
features will report the error until it's resolved (see Troubleshooting).

## How to Open the Application

Go to **http://127.0.0.1:8000** — FastAPI serves the frontend directly,
so there's nothing else to start.

---

## How to Test Zaraaq Independently

Before trusting the web app's microphone flow, verify the model in
isolation, exactly as your notebook did:

```powershell
cd backend
python test_asr_local.py
```

This records from your local microphone via `sounddevice`, saves
`recorded_audio.wav`, and prints both the raw and cleaned transcription.

## How to Test Voice Shopping (the full flow)

1. Open http://127.0.0.1:8000
2. Click **🎙️ Shop with Voice**
3. Click **Start Listening**, allow microphone access if prompted
4. Say: *"Add two apples and one litre of milk."*
5. Click **Stop Recording**
6. You should see:
   - "You said: Add two apples and one litre of milk."
   - ✓ Added 2 Apples
   - ✓ Added 1 Milk
7. Close the modal and open the cart — Apple × 2, Milk × 1, total ₹270

---

## Sample Voice Commands

| Say | Expected cart result |
|---|---|
| "Add milk." | Milk × 1 |
| "Add two apples." | Apple × 2 |
| "Add three bananas." | Banana × 3 |
| "Add two apples and one litre of milk." | Apple × 2, Milk × 1 |
| "Add one kilo of rice." | Rice × 1 |
| "Add two bottles of water." | Water × 2 |
| "Add three tomatoes." | Tomato × 3 |
| "Add milk." then "Add milk." again | Milk × 2 (quantities accumulate) |

All of these were tested directly against `command_parser.py` and
`cart_service.py` before integration — see the inline comments in those
files for the parsing rules (number words, units like "litre"/"kilo"/
"bottle", plural normalization).

---

## API Reference

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/products` | All products + category list |
| GET | `/api/products/{id}` | Single product |
| POST | `/api/search` | `{query}` → matching products |
| POST | `/api/asr/transcribe` | Audio → transcription only |
| POST | `/api/voice-command` | Audio → transcription → parse → cart (the main voice flow) |
| GET | `/api/cart` | Current cart |
| POST | `/api/cart/add` | `{product_id, quantity}` |
| POST | `/api/cart/update` | `{product_id, quantity}` (absolute) |
| DELETE | `/api/cart/{product_id}` | Remove one item |
| DELETE | `/api/cart` | Clear cart |
| GET | `/api/health` | Server + ASR model status |

Interactive docs: **http://127.0.0.1:8000/docs**

---

## Troubleshooting

**Microphone permission denied**
The browser blocked mic access. Click the padlock/site-info icon in the
address bar → Site settings → allow Microphone, then reload the page.

**PyTorch install fails or is very slow**
On Windows, install the CPU build explicitly if the default install
struggles:
```powershell
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements.txt
```

**`transformers` can't download the model / "connection error"**
Check your internet connection - the model downloads from Hugging Face
on first use and is cached locally afterward (usually under
`C:\Users\<you>\.cache\huggingface`). If you're behind a proxy, set the
`HTTPS_PROXY` environment variable before starting the server.

**Audio dependency errors (`sounddevice`, `PortAudio`)**
`sounddevice` (used only by `test_asr_local.py`, not the web app) needs
PortAudio. On Windows this normally installs automatically with the pip
wheel. If it fails, reinstall with `pip install --force-reinstall sounddevice`.

**Windows microphone not detected in the browser**
Check Windows Settings → Privacy & security → Microphone → make sure
"Let apps access your microphone" and browser access are both on.

**Port 8000 already in use**
```powershell
python -m uvicorn app:app --reload --port 8001
```
Then open http://127.0.0.1:8001 instead.

**Transcription looks garbled or contains stray tokens like `<|...|>`**
This is the exact issue observed in your own notebook's output (see
"About the ASR model" above). Confirm you're running the version of
`asr_service.py` from this project (it includes the cleanup step) rather
than a bare `pipeline(...)` call. If it persists, try setting
`ASR_LANGUAGE=ta` in `.env` in case your speech is closer to the model's
Tamil/Tanglish training data than to English.

**Model loads but transcription is inaccurate for English commands**
Per the notebook analysis, this checkpoint's demonstrated test data was
Tamil/Tanglish, not English. Accuracy on English grocery commands is not
guaranteed by the notebook's own evidence - this is worth validating with
`test_asr_local.py` before a live demo, and having a typed-search fallback
ready (the dashboard's search bar works independently of voice).

---

## Test Cases Covered

All of the following were verified directly against `command_parser.py`
and `cart_service.py`:

1. "Add milk." → Milk × 1
2. "Add two apples." → Apple × 2
3. "Add three bananas." → Banana × 3
4. "Add two apples and one litre of milk." → Apple × 2, Milk × 1
5. "Add one kilo of rice." → Rice × 1
6. "Add two bottles of water." → Water × 2
7. "Add three tomatoes." → Tomato × 3
8. "Add milk." then "Add milk." → Milk × 2 (accumulates, not duplicated)
9. Search "apple" → Apple displayed
10. Remove item from cart → item removed, total recalculated

---

## Notes on Scope

This is a working prototype, not a production system:

- Cart is in-memory and single-shared (no accounts/sessions) - it resets
  when the server restarts
- No database - the catalog is a static JSON file
- No payment integration - checkout is a demo confirmation only
- The 15-second recording cap in the UI is a demo safety net, not a
  model limitation - adjust `recSeconds >= 15` in `script.js` if needed

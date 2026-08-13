"""
asr_service.py
---------------
Speech-to-text using the Lokii99/zaraaqtest model via Hugging Face
Transformers. This module is a DIRECT reproduction of the working
approach proven in the provided notebook (aug11loki99.ipynb, cells 3-5):

    device = 0 if torch.cuda.is_available() else -1
    asr = pipeline("automatic-speech-recognition", model=MODEL_ID, device=device)
    result = asr({"raw": audio, "sampling_rate": sample_rate})

The model is loaded ONCE as a module-level singleton and reused for every
request - never reloaded per-call.

Two things are added on top of the notebook's raw approach, both
explained here rather than silently applied:

1. LANGUAGE CONFIGURATION
   The notebook's own test output contains the special token "<|ta|>"
   (Whisper's language tag for Tamil), confirming this checkpoint is a
   Whisper-family model, and that the notebook's own test recordings were
   in Tamil/Tanglish. This project's target demo command is in English
   ("Add two apples and one litre of milk"), so we pass an explicit
   `language` to the pipeline's generate_kwargs. This is configuration,
   not an architecture change - the same pipeline, same model, same call
   shape as the notebook. Override with ASR_LANGUAGE in .env if you plan
   to demo in Tamil/Tanglish instead (matching the notebook's own tests).

2. OUTPUT CLEANUP
   The notebook's raw output included leaked special tokens
   (e.g. "<|startoftranscript|><|ta|><|transcribe|><|notimestamps|>")
   and repeated/looping phrases (a known Whisper hallucination pattern).
   Both would break the downstream command parser if passed through
   as-is, so _clean_transcription() strips special tokens and collapses
   immediate phrase repeats. This is text post-processing only - it does
   not touch the model, the pipeline call, or the audio pipeline.
"""

import os
import io
import re
import wave
import numpy as np

TARGET_SAMPLE_RATE = 16000
MODEL_ID = "Lokii99/zaraaqtest"

_SPECIAL_TOKEN_RE = re.compile(r"<\|[^|>]*\|>")


class ASRServiceError(Exception):
    """Raised for any ASR failure the API layer should turn into a clean message."""
    pass


class ASRService:
    """
    Loads Lokii99/zaraaqtest once and exposes:
      - transcribe_array(audio, sample_rate): the notebook's proven call shape
      - transcribe_wav_bytes(wav_bytes): convenience wrapper for uploaded audio
    """

    def __init__(self, model_id: str = MODEL_ID, language: str = None):
        self.model_id = model_id
        self.language = language or os.environ.get("ASR_LANGUAGE", "en")
        self._pipeline = None
        self._load_error: str = None

    # ------------------------------------------------------------------
    def load(self) -> None:
        """
        Loads the model into memory. Call once at server startup.
        Mirrors the notebook exactly: transformers.pipeline(
            "automatic-speech-recognition", model=MODEL_ID, device=...)
        """
        if self._pipeline is not None:
            return  # already loaded - never reload per request

        try:
            import torch
            from transformers import pipeline

            device = 0 if torch.cuda.is_available() else -1
            print(f"[asr_service] Device: {'GPU' if device == 0 else 'CPU'}")
            print(f"[asr_service] Loading model: {self.model_id} ...")

            self._pipeline = pipeline(
                "automatic-speech-recognition",
                model=self.model_id,
                device=device,
            )
            print("[asr_service] Model loaded successfully.")
        except Exception as exc:
            # Store the error instead of crashing the whole server - the
            # dashboard, catalog, search, and cart must keep working even
            # if the ASR model fails to download/load (e.g. no internet,
            # gated repo, missing dependency).
            self._load_error = str(exc)
            print(f"[asr_service] ERROR loading model: {exc}")

    @property
    def is_ready(self) -> bool:
        return self._pipeline is not None

    @property
    def load_error(self) -> str:
        return self._load_error

    # ------------------------------------------------------------------
    def transcribe_array(self, audio: np.ndarray, sample_rate: int) -> str:
        """
        The notebook's proven call shape, unchanged:
            asr({"raw": audio, "sampling_rate": sample_rate})
        `audio` must be a mono float32 numpy array.
        """
        if not self.is_ready:
            raise ASRServiceError(
                self._load_error or "The speech recognition model is not loaded yet."
            )
        if audio is None or audio.size == 0:
            raise ASRServiceError("No audio was captured. Please try recording again.")

        generate_kwargs = {}
        if self.language:
            # Whisper-family models accept language/task hints. If this
            # checkpoint doesn't support them, we retry without - see below.
            generate_kwargs = {"language": self.language, "task": "transcribe"}

        try:
            result = self._pipeline(
                {"raw": audio, "sampling_rate": sample_rate},
                generate_kwargs=generate_kwargs,
            )
        except (TypeError, ValueError):
            # Defensive fallback: some model/pipeline combinations don't
            # accept generate_kwargs. Retry with the exact bare call shape
            # from the notebook rather than failing the whole request.
            result = self._pipeline({"raw": audio, "sampling_rate": sample_rate})

        raw_text = result.get("text", "") if isinstance(result, dict) else str(result)
        return self._clean_transcription(raw_text)

    def transcribe_wav_bytes(self, wav_bytes: bytes) -> str:
        """
        Convenience wrapper for audio uploaded from the browser as a WAV
        file. Reads it into the same {mono float32, 16kHz} shape the
        notebook feeds the pipeline, using soundfile exactly as the
        notebook does for on-disk WAV files.
        """
        audio, sample_rate = self._read_wav(wav_bytes)
        return self.transcribe_array(audio, sample_rate)

    # ------------------------------------------------------------------
    @staticmethod
    def _read_wav(wav_bytes: bytes):
        """
        Reads WAV bytes into a mono float32 numpy array. Tries soundfile
        first (matches the notebook's sf.read usage exactly); falls back
        to the standard-library `wave` module if soundfile isn't available,
        so a missing optional dependency doesn't take down voice search.
        """
        try:
            import soundfile as sf
            audio, sample_rate = sf.read(io.BytesIO(wav_bytes), dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)  # downmix to mono
            return audio, sample_rate
        except ImportError:
            pass

        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)

        dtype = {1: np.uint8, 2: np.int16, 4: np.int32}.get(sample_width, np.int16)
        audio = np.frombuffer(raw, dtype=dtype).astype(np.float32)

        if dtype == np.int16:
            audio /= 32768.0
        elif dtype == np.int32:
            audio /= 2147483648.0
        elif dtype == np.uint8:
            audio = (audio - 128) / 128.0

        if n_channels > 1:
            audio = audio.reshape(-1, n_channels).mean(axis=1)

        return audio, sample_rate

    @staticmethod
    def _clean_transcription(text: str) -> str:
        """
        Strips leaked special tokens (e.g. <|startoftranscript|><|ta|>...)
        and collapses immediate repeated phrases (Whisper hallucination
        loops observed in the notebook's own sample output). Purely
        textual post-processing - does not touch the model or pipeline.
        """
        if not text:
            return ""

        cleaned = _SPECIAL_TOKEN_RE.sub(" ", text)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()

        # Collapse immediate repeats of 2+ word phrases, e.g.
        # "vengaiam madrum vengaiam madrum" -> "vengaiam madrum"
        words = cleaned.split(" ")
        for phrase_len in range(min(6, len(words) // 2), 1, -1):
            i = 0
            deduped = []
            while i < len(words):
                window = words[i:i + phrase_len]
                next_window = words[i + phrase_len:i + 2 * phrase_len]
                if window and window == next_window:
                    deduped.extend(window)
                    i += 2 * phrase_len
                else:
                    deduped.append(words[i])
                    i += 1
            words = deduped
        cleaned = " ".join(words)

        return cleaned.strip()


# Module-level singleton - imported and shared by app.py
asr_service = ASRService()

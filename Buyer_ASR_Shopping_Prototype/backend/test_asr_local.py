"""
test_asr_local.py
------------------
Standalone verification script - reproduces the exact working flow from
the provided notebook (aug11loki99.ipynb), independent of FastAPI/the web
app. Run this FIRST to confirm Zaraaq loads and transcribes correctly on
your machine before trusting the web integration.

This intentionally mirrors the notebook's own local-microphone approach
(sounddevice recording -> soundfile WAV -> pipeline), since that is the
proven, working method documented in your notebook. The web app uses
browser-based recording instead (see frontend/script.js) for practical
reasons explained in the README, but this script exists specifically so
you can validate the model in isolation, exactly as you did in the
notebook.

Usage:
    python test_asr_local.py
    python test_asr_local.py --duration 8
"""

import argparse
import sys

MODEL_ID = "Lokii99/zaraaqtest"
SAMPLE_RATE = 16000


def main():
    parser = argparse.ArgumentParser(description="Standalone Zaraaq ASR test (mirrors the notebook).")
    parser.add_argument("--duration", type=int, default=5, help="Recording duration in seconds.")
    args = parser.parse_args()

    try:
        import torch
        from transformers import pipeline
        import sounddevice as sd
        import soundfile as sf
    except ImportError as e:
        print(f"Missing dependency: {e}")
        print("Run: pip install -r requirements.txt")
        sys.exit(1)

    device = 0 if torch.cuda.is_available() else -1
    print("Device:", "GPU" if device == 0 else "CPU")
    print("Loading:", MODEL_ID)

    asr = pipeline("automatic-speech-recognition", model=MODEL_ID, device=device)
    print("Model loaded successfully!\n")

    print(f"Recording for {args.duration} seconds... Speak now!")
    audio = sd.rec(
        int(args.duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )
    sd.wait()
    print("Recording finished!")

    sf.write("recorded_audio.wav", audio, SAMPLE_RATE)
    print("Saved as recorded_audio.wav")

    audio, sample_rate = sf.read("recorded_audio.wav")
    print("Sample rate:", sample_rate)
    print("Audio shape:", audio.shape)

    result = asr({"raw": audio, "sampling_rate": sample_rate})
    print("\nRaw transcription:")
    print(result["text"])

    # Show what the app's cleanup step would produce, for comparison.
    from asr_service import ASRService
    cleaned = ASRService._clean_transcription(result["text"])
    print("\nCleaned transcription (what the app will actually use):")
    print(cleaned)


if __name__ == "__main__":
    main()

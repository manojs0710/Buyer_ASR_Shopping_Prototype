"""
app.py
------
Buyer ASR Shopping Prototype - FastAPI backend.

Wires together the product catalog, command parser, cart service, and the
Zaraaq ASR service behind a small set of REST endpoints, and serves the
frontend from the same origin so the whole demo runs from one URL.

Run with:
    python -m uvicorn app:app --reload --port 8000
"""

import os
from typing import Optional

from dotenv import load_dotenv
load_dotenv()  # must run before asr_service reads ASR_LANGUAGE at import time

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from product_service import ProductService
from command_parser import CommandParser
from cart_service import CartService
from asr_service import asr_service, ASRServiceError

# ----------------------------------------------------------------------
# App + service singletons
# ----------------------------------------------------------------------
app = FastAPI(title="Buyer ASR Shopping Prototype", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # POC only
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

product_service = ProductService()
command_parser = CommandParser(product_service)
cart_service = CartService(product_service)


@app.on_event("startup")
def load_asr_model():
    """
    Loads the Zaraaq model exactly once when the server starts, so voice
    requests never pay a model-load cost. If loading fails (e.g. no
    internet, gated repo), the rest of the app keeps working - only
    voice endpoints will report the error.
    """
    asr_service.load()


# ----------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str


class CartAddRequest(BaseModel):
    product_id: str
    quantity: int = 1


class CartUpdateRequest(BaseModel):
    product_id: str
    quantity: int


# ----------------------------------------------------------------------
# Products
# ----------------------------------------------------------------------
@app.get("/api/products")
def get_products(category: Optional[str] = None):
    if category:
        return {"products": product_service.by_category(category)}
    return {"products": product_service.get_all(), "categories": product_service.categories()}


@app.get("/api/products/{product_id}")
def get_product(product_id: str):
    product = product_service.get_by_id(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product '{product_id}' not found.")
    return product


@app.post("/api/search")
def search_products(req: SearchRequest):
    return {"products": product_service.search(req.query), "query": req.query}


# ----------------------------------------------------------------------
# ASR
# ----------------------------------------------------------------------
@app.post("/api/asr/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """Transcribes uploaded audio only - does not touch the cart."""
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio data received.")
    try:
        text = asr_service.transcribe_wav_bytes(audio_bytes)
    except ASRServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Sorry, I couldn't understand the audio. Please try again.",
        )
    return {"success": True, "transcription": text}


@app.post("/api/voice-command")
async def voice_command(audio: UploadFile = File(...)):
    """
    The single end-to-end voice-shopping endpoint:
    audio -> Zaraaq transcription -> command parser -> cart -> response.
    """
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio data received.")

    try:
        transcription = asr_service.transcribe_wav_bytes(audio_bytes)
    except ASRServiceError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {e}")

    if not transcription:
        raise HTTPException(
            status_code=422,
            detail="Sorry, I couldn't understand the audio. Please try again.",
        )

    parsed = command_parser.parse(transcription)
    items_added = []
    errors = []

    for item in parsed["items"]:
        try:
            cart_service.add_item(item["product_id"], item["quantity"])
            items_added.append({"product": item["product_name"], "quantity": item["quantity"]})
        except (KeyError, ValueError) as e:
            errors.append(str(e))

    for term in parsed["unmatched_terms"]:
        errors.append(f"I couldn't find '{term}' in the current catalog.")

    return {
        "success": len(items_added) > 0,
        "transcription": transcription,
        "items_added": items_added,
        "errors": errors,
        "cart": cart_service.get_cart(),
    }


# ----------------------------------------------------------------------
# Cart
# ----------------------------------------------------------------------
@app.get("/api/cart")
def get_cart():
    return cart_service.get_cart()


@app.post("/api/cart/add")
def add_to_cart(req: CartAddRequest):
    try:
        return cart_service.add_item(req.product_id, req.quantity)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/cart/update")
def update_cart(req: CartUpdateRequest):
    try:
        return cart_service.update_quantity(req.product_id, req.quantity)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.delete("/api/cart/{product_id}")
def remove_from_cart(product_id: str):
    return cart_service.remove_item(product_id)


@app.delete("/api/cart")
def clear_cart():
    return cart_service.clear()


# ----------------------------------------------------------------------
# Health
# ----------------------------------------------------------------------
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "asr_ready": asr_service.is_ready,
        "asr_error": asr_service.load_error,
        "asr_model": asr_service.model_id,
        "asr_language": asr_service.language,
        "product_count": len(product_service.get_all()),
    }


# ----------------------------------------------------------------------
# Serve the frontend (single-origin demo)
# ----------------------------------------------------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

if os.path.isdir(FRONTEND_DIR):
    @app.get("/")
    def serve_index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    @app.get("/style.css")
    def serve_css():
        return FileResponse(os.path.join(FRONTEND_DIR, "style.css"))

    @app.get("/script.js")
    def serve_js():
        return FileResponse(os.path.join(FRONTEND_DIR, "script.js"))

from pathlib import Path
import hashlib
import json
import os
import secrets
import urllib.error
import urllib.request

from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from docx import Document as DocxDocument

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("BIBLIOTECARIO_DATA_DIR", BASE_DIR / "data"))
DOCS_DIR = DATA_DIR / "documents"
CHROMA_DIR = DATA_DIR / "chroma"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
MAX_UPLOAD_BYTES = int(os.getenv("BIBLIOTECARIO_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
API_KEY = os.getenv("BIBLIOTECARIO_API_KEY", "").strip()

DOCS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Bibliotecario API", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def require_api_key(x_api_key: str | None) -> None:
    """Require a shared API key when BIBLIOTECARIO_API_KEY is configured."""
    if API_KEY and not x_api_key:
        raise HTTPException(401, "Falta X-API-Key")
    if API_KEY and not secrets.compare_digest(x_api_key, API_KEY):
        raise HTTPException(403, "API key inválida")


def embeddings():
    return OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)


def vectorstore():
    return Chroma(
        collection_name="bibliotecario",
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings(),
    )


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt"}:
        return path.read_text(encoding="utf-8")
    if suffix == ".docx":
        doc = DocxDocument(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    raise ValueError("Formato no soportado")


def make_chunks(text: str, filename: str):
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
    return splitter.create_documents([text], metadata=[{"source": filename, "filename": filename}])


def make_ids(chunks, filename: str):
    return [
        hashlib.sha256(f"{filename}:{i}:{chunk.page_content}".encode("utf-8")).hexdigest()
        for i, chunk in enumerate(chunks)
    ]


def ollama_status() -> dict:
    try:
        with urllib.request.urlopen(f"{OLLAMA_BASE_URL}/api/tags", timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8"))
        models = [item.get("name") for item in payload.get("models", [])]
        return {"ok": True, "available": True, "models": models, "embedding_model_found": EMBED_MODEL in models}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "available": False, "models": [], "embedding_model_found": False, "error": str(exc)}


@app.get("/api/health")
def health():
    ollama = ollama_status()
    return {
        "ok": ollama["available"] and ollama["embedding_model_found"],
        "service": "bibliotecario",
        "version": app.version,
        "embedding_model": EMBED_MODEL,
        "data_dir": str(DATA_DIR),
        "authentication_required": bool(API_KEY),
        "ollama": ollama,
    }


@app.get("/api/documents")
def documents(x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    files = sorted(
        [p for p in DOCS_DIR.iterdir() if p.is_file() and p.suffix.lower() in {".md", ".txt", ".docx"}],
        key=lambda p: p.name.lower(),
    )
    return {
        "count": len(files),
        "documents": [{"filename": p.name, "bytes": p.stat().st_size} for p in files],
    }


@app.post("/api/upload")
def upload(file: UploadFile = File(...), x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".md", ".txt", ".docx"}:
        raise HTTPException(400, "Solo se admiten .md, .txt y .docx")

    safe_name = Path(file.filename).name
    if not safe_name:
        raise HTTPException(400, "Nombre de archivo inválido")

    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"El archivo supera el límite de {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")

    destination = DOCS_DIR / safe_name
    previous_content = destination.read_bytes() if destination.exists() else None

    try:
        destination.write_bytes(content)
        text = extract_text(destination)
        if not text.strip():
            raise ValueError("El documento no contiene texto")

        new_chunks = make_chunks(text, safe_name)
        new_ids = make_ids(new_chunks, safe_name)
        store = vectorstore()
        store.delete(where={"source": safe_name})
        store.add_documents(new_chunks, ids=new_ids)

        return {
            "ok": True,
            "filename": safe_name,
            "chunks": len(new_chunks),
            "replaced_existing": previous_content is not None,
        }
    except Exception as exc:
        # Restauramos el archivo físico y, si había versión anterior, intentamos
        # reconstruir también sus fragmentos en Chroma.
        destination.unlink(missing_ok=True)
        if previous_content is not None:
            destination.write_bytes(previous_content)
            try:
                old_text = extract_text(destination)
                old_chunks = make_chunks(old_text, safe_name)
                store = vectorstore()
                store.delete(where={"source": safe_name})
                store.add_documents(old_chunks, ids=make_ids(old_chunks, safe_name))
            except Exception:
                pass
        raise HTTPException(500, f"No se pudo indexar el documento: {exc}") from exc


@app.get("/api/search")
def search(q: str, k: int = 5, x_api_key: str | None = Header(default=None)):
    require_api_key(x_api_key)
    query = q.strip()
    if not query:
        raise HTTPException(400, "La consulta no puede estar vacía")
    k = max(1, min(k, 20))
    try:
        results = vectorstore().similarity_search_with_score(query, k=k)
        return {
            "query": query,
            "count": len(results),
            "results": [
                {"source": doc.metadata.get("source"), "content": doc.page_content, "score": float(score)}
                for doc, score in results
            ],
        }
    except Exception as exc:
        raise HTTPException(500, f"No se pudo realizar la búsqueda: {exc}") from exc

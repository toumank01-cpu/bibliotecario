from pathlib import Path
import os
import shutil

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter
from docx import Document as DocxDocument

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("BIBLIOTECARIO_DATA_DIR", BASE_DIR / "data"))
DOCS_DIR = DATA_DIR / "documents"
CHROMA_DIR = DATA_DIR / "chroma"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

DOCS_DIR.mkdir(parents=True, exist_ok=True)
CHROMA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Bibliotecario API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


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


@app.get("/api/health")
def health():
    return {
        "ok": True,
        "service": "bibliotecario",
        "embedding_model": EMBED_MODEL,
        "data_dir": str(DATA_DIR),
    }


@app.post("/api/upload")
def upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".md", ".txt", ".docx"}:
        raise HTTPException(400, "Solo se admiten .md, .txt y .docx")

    safe_name = Path(file.filename).name
    destination = DOCS_DIR / safe_name
    with destination.open("wb") as target:
        shutil.copyfileobj(file.file, target)

    try:
        text = extract_text(destination)
        if not text.strip():
            raise ValueError("El documento no contiene texto")
        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=120)
        chunks = splitter.create_documents(
            [text], metadata=[{"source": safe_name, "filename": safe_name}]
        )
        vectorstore().add_documents(chunks)
        return {"ok": True, "filename": safe_name, "chunks": len(chunks)}
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(500, f"No se pudo indexar el documento: {exc}") from exc


@app.get("/api/search")
def search(q: str, k: int = 5):
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
                {
                    "source": doc.metadata.get("source"),
                    "content": doc.page_content,
                    "score": float(score),
                }
                for doc, score in results
            ],
        }
    except Exception as exc:
        raise HTTPException(500, f"No se pudo realizar la búsqueda: {exc}") from exc

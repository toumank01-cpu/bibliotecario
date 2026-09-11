# Bibliotecario

Aplicación web para gestionar una biblioteca privada de conocimiento y realizar búsquedas semánticas para un asistente IA.

## Arquitectura

- **Frontend:** HTML/CSS/JavaScript estático, preparado para GitHub Pages u otro hosting estático.
- **Backend:** FastAPI en `backend/app.py`.
- **Documentos privados:** `backend/data/documents/` en el PC donde corre el backend; esta carpeta está excluida de Git.
- **Vector store:** Chroma persistente en `backend/data/chroma/`, también excluido de Git.
- **Embeddings:** Ollama + `nomic-embed-text` ejecutándose localmente.
- **RAG:** `/api/search` devuelve fragmentos semánticamente relevantes para que el modelo que redacta pueda usarlos como contexto.

## Funciones actuales

- Subida de `.md`, `.txt` y `.docx`.
- Límite configurable de 10 MB por archivo.
- Extracción de texto de Markdown/TXT/DOCX.
- División en fragmentos de 800 caracteres con 120 de solapamiento.
- Indexación persistente mediante Chroma.
- Reindexación del mismo nombre de archivo sin acumular fragmentos antiguos.
- Búsqueda semántica con puntuación.
- Listado de documentos mediante `GET /api/documents`.
- Health check mediante `GET /api/health`, incluyendo disponibilidad de Ollama y del modelo de embeddings.
- Frontend con URL de API configurable y guardada localmente en el navegador.

## Ejecución local

1. Instala Ollama y descarga `nomic-embed-text`.
2. Entra en `backend/`.
3. Ejecuta `run.bat` en Windows.
4. El backend queda disponible en `http://127.0.0.1:8000`.
5. Comprueba `GET /api/health`.
6. Abre el frontend y configura la URL de la API.

## Publicación segura

GitHub Pages **no ejecuta** FastAPI, Chroma ni Ollama. Para usar la aplicación desde fuera del PC habrá que mantener el backend en el equipo local y exponerlo mediante una capa HTTPS/túnel apropiadamente protegida.

Antes de publicar el backend se debe añadir autenticación/autorización y restringir CORS al dominio real del frontend. No se debe exponer una biblioteca privada mediante una API pública sin protección.

## Privacidad

No subir al repositorio público capítulos de la novela, lore, documentos personales, la base Chroma ni claves API. El `.gitignore` del backend excluye `data/`, `.venv/`, `__pycache__/` y `.env`.

# Bibliotecario

Interfaz web para gestionar una biblioteca de conocimiento destinada a un asistente IA.

## Estado actual

- Interfaz web responsive.
- Selección y arrastre de archivos `.md`, `.docx` y `.txt`.
- Zona de búsqueda preparada para RAG.
- Endpoint previsto: `GET /api/search?q=...`.
- La interfaz no incluye todavía documentos de la novela ni secretos.

## Próximo paso

Conectar esta interfaz con un backend privado que almacene los documentos, genere embeddings y exponga una API HTTPS para las búsquedas. Esto evita publicar la biblioteca privada dentro del repositorio público.

## Importante

No subir todavía al repositorio público capítulos, lore, documentos personales ni claves API. El repositorio contiene únicamente el código de la aplicación.
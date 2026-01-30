"""
api.py - FastAPI backend para o Pipeline MD/JSON v3.

API RESTful eficiente para conversão de documentos com:
- Upload assíncrono
- Streaming de progresso via SSE
- Endpoints para download de resultados
"""
import asyncio
import json
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import logging

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar app FastAPI
app = FastAPI(
    title="Pipeline MD/JSON v3 API",
    description="API para conversão de documentos PDF/DOCX em Markdown e JSON estruturado",
    version="3.0.0"
)

# CORS para desenvolvimento local
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Armazenamento de jobs em memória
jobs: Dict[str, Dict[str, Any]] = {}

# Diretório para arquivos temporários
UPLOAD_DIR = Path("temp/uploads")
OUTPUT_DIR = Path("temp/outputs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


# === MODELOS ===

class ConversionRequest(BaseModel):
    """Configurações de conversão."""
    enable_schema_inference: bool = True
    extract_entities: bool = True
    prefer_vision_for_tables: bool = False
    chunk_size: int = 500
    chunk_overlap: int = 50
    include_frontmatter: bool = True
    include_toc: bool = False
    generate_markdown: bool = True
    generate_json: bool = True


class JobStatus(BaseModel):
    """Status de um job de conversão."""
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: int  # 0-100
    stage: str
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


# === ROTAS ===

@app.get("/")
async def root():
    """Redireciona para a interface web."""
    return FileResponse("frontend/index.html")


@app.get("/health")
async def health_check():
    """Health check da API."""
    return {"status": "healthy", "version": "3.0.0"}


@app.post("/api/convert")
async def convert_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    config: str = Form("{}")
):
    """
    Inicia conversão de documento.

    Retorna job_id para acompanhamento do progresso.
    """
    # Validar arquivo
    if not file.filename:
        raise HTTPException(status_code=400, detail="Nome do arquivo não fornecido")

    extension = Path(file.filename).suffix.lower()
    if extension not in [".pdf", ".docx", ".doc"]:
        raise HTTPException(
            status_code=400,
            detail=f"Formato não suportado: {extension}. Use PDF ou DOCX."
        )

    # Parse config
    try:
        config_dict = json.loads(config)
    except json.JSONDecodeError:
        config_dict = {}

    # Criar job
    job_id = str(uuid.uuid4())[:8]
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    # Salvar arquivo
    file_path = job_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    # Registrar job
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "stage": "Iniciando...",
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
        "error": None,
        "result": None,
        "file_path": str(file_path),
        "file_name": file.filename,
        "config": config_dict,
        "output_dir": str(job_dir)
    }

    # Iniciar processamento em background
    background_tasks.add_task(process_document, job_id)

    return {"job_id": job_id, "message": "Conversão iniciada"}


@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    """Retorna status de um job."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = jobs[job_id]
    return JobStatus(
        job_id=job["job_id"],
        status=job["status"],
        progress=job["progress"],
        stage=job["stage"],
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
        error=job.get("error"),
        result=job.get("result")
    )


@app.get("/api/progress/{job_id}")
async def stream_progress(job_id: str):
    """
    Stream de progresso via Server-Sent Events (SSE).
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    async def event_generator():
        last_progress = -1
        while True:
            if job_id not in jobs:
                break

            job = jobs[job_id]

            # Enviar update se houve mudança
            if job["progress"] != last_progress or job["status"] in ["completed", "failed"]:
                last_progress = job["progress"]
                data = {
                    "status": job["status"],
                    "progress": job["progress"],
                    "stage": job["stage"]
                }

                if job["status"] == "completed" and job.get("result"):
                    data["result"] = job["result"]
                elif job["status"] == "failed":
                    data["error"] = job.get("error")

                yield f"data: {json.dumps(data)}\n\n"

                if job["status"] in ["completed", "failed"]:
                    break

            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.get("/api/download/{job_id}/{file_type}")
async def download_result(job_id: str, file_type: str):
    """
    Download de arquivo resultante.

    file_type: 'markdown' ou 'json'
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Conversão não concluída")

    result = job.get("result", {})

    if file_type == "markdown":
        file_path = result.get("markdown_path")
        media_type = "text/markdown"
        filename = f"{Path(job['file_name']).stem}.md"
    elif file_type == "json":
        file_path = result.get("json_path")
        media_type = "application/json"
        filename = f"{Path(job['file_name']).stem}.json"
    else:
        raise HTTPException(status_code=400, detail="Tipo de arquivo inválido")

    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="Arquivo não encontrado")

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename
    )


@app.get("/api/result/{job_id}")
async def get_result(job_id: str):
    """Retorna resultado completo da conversão."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = jobs[job_id]

    if job["status"] != "completed":
        raise HTTPException(status_code=400, detail="Conversão não concluída")

    result = job.get("result", {})

    # Ler conteúdos dos arquivos
    response = {
        "job_id": job_id,
        "file_name": job["file_name"],
        "document_type": result.get("document_type", "unknown"),
        "confidence": result.get("confidence", 0),
        "processing_time": result.get("processing_time", 0),
    }

    # Markdown
    md_path = result.get("markdown_path")
    if md_path and Path(md_path).exists():
        response["markdown"] = Path(md_path).read_text(encoding="utf-8")

    # JSON
    json_path = result.get("json_path")
    if json_path and Path(json_path).exists():
        response["json_data"] = json.loads(Path(json_path).read_text(encoding="utf-8"))

    return response


@app.delete("/api/job/{job_id}")
async def delete_job(job_id: str):
    """Remove um job e seus arquivos."""
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job não encontrado")

    job = jobs[job_id]

    # Remover diretório de output
    output_dir = Path(job.get("output_dir", ""))
    if output_dir.exists():
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)

    # Remover job da memória
    del jobs[job_id]

    return {"message": "Job removido"}


# === PROCESSAMENTO ===

async def process_document(job_id: str):
    """Processa documento em background."""
    job = jobs.get(job_id)
    if not job:
        return

    try:
        job["status"] = "processing"
        job["stage"] = "Importando módulos..."
        job["progress"] = 5

        # Import tardio para não bloquear startup
        from converter import convert_document as do_convert, ConversionConfig

        # Criar config
        config_dict = job.get("config", {})
        config = ConversionConfig(
            output_dir=job["output_dir"],
            enable_schema_inference=config_dict.get("enable_schema_inference", True),
            extract_entities=config_dict.get("extract_entities", True),
            prefer_vision_for_tables=config_dict.get("prefer_vision_for_tables", False),
            chunk_size=config_dict.get("chunk_size", 500),
            chunk_overlap=config_dict.get("chunk_overlap", 50),
            include_frontmatter=config_dict.get("include_frontmatter", True),
            include_toc=config_dict.get("include_toc", False),
            generate_markdown=config_dict.get("generate_markdown", True),
            generate_json=config_dict.get("generate_json", True),
        )

        # Stages com progresso
        stages = {
            "detection": (5, 10, "Detectando tipo de documento..."),
            "text_extraction": (10, 25, "Extraindo texto..."),
            "structure_analysis": (25, 40, "Analisando estrutura..."),
            "routing": (40, 45, "Roteando processamento..."),
            "asset_extraction": (45, 55, "Extraindo imagens..."),
            "vision_processing": (55, 70, "Processando com visão..."),
            "synthesis": (70, 75, "Sintetizando documento..."),
            "schema_inference": (75, 85, "Inferindo schema..."),
            "entity_extraction": (85, 90, "Extraindo entidades..."),
            "chunk_generation": (90, 93, "Gerando chunks..."),
            "generation": (93, 100, "Gerando arquivos...")
        }

        def progress_callback(stage: str, current: int, total: int):
            if stage in stages:
                start, end, message = stages[stage]
                if total > 0:
                    progress = start + (end - start) * (current / total)
                else:
                    progress = start
                job["progress"] = int(progress)
                job["stage"] = message

        # Converter
        file_path = Path(job["file_path"])
        result = do_convert(file_path, config=config, progress_callback=progress_callback)

        job["progress"] = 100
        job["stage"] = "Concluído!"
        job["completed_at"] = datetime.now().isoformat()

        if result.success:
            job["status"] = "completed"
            job["result"] = {
                "markdown_path": result.markdown_path,
                "json_path": result.json_path,
                "assets_dir": result.assets_dir,
                "document_type": result.parsed_document.metadata.document_type if result.parsed_document else "unknown",
                "confidence": result.parsed_document.structured_data.confidence if result.parsed_document and result.parsed_document.structured_data else 0,
                "processing_time": result.parsed_document.processing.processing_time_seconds if result.parsed_document else 0,
                "warnings": result.warnings
            }
        else:
            job["status"] = "failed"
            job["error"] = "; ".join(result.errors) if result.errors else "Erro desconhecido"

    except Exception as e:
        logger.exception(f"Erro no processamento do job {job_id}")
        job["status"] = "failed"
        job["error"] = str(e)
        job["completed_at"] = datetime.now().isoformat()


# === SERVIR FRONTEND ===

# Montar arquivos estáticos
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")


@app.get("/app")
async def serve_app():
    """Serve a interface principal."""
    return FileResponse("frontend/index.html")


# === MAIN ===

def run_server(host: str = "127.0.0.1", port: int = 8000):
    """Inicia o servidor."""
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("paul")

from app.core.config import settings
from app.core.database import Base, engine

# Import models so Alembic/SQLAlchemy picks them up
import app.models  # noqa
from app.api import analyze, export, families, ingest, legacy_theben, products, prompts, transparency


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    from app.core.database import SessionLocal
    from app.seed.seed import run as seed_families
    db = SessionLocal()
    try:
        seed_families(db)
    finally:
        db.close()
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "PAUL data-layer"}


@app.get("/api/v1/lakehouse/products")
def lakehouse_products(article_number: str = None):
    """Query Iceberg product_master table via Trino."""
    from app.lakehouse.iceberg_writer import query_product_master
    rows = query_product_master(article_number)
    return {"source": "iceberg/trino", "count": len(rows), "products": rows}


@app.get("/api/v1/lakehouse/health")
def lakehouse_health():
    """Check if Trino/Iceberg is reachable."""
    try:
        from app.lakehouse.iceberg_writer import query_product_master
        query_product_master()
        return {"status": "ok", "trino": "connected", "catalog": "iceberg", "schema": "products"}
    except Exception as exc:
        return {"status": "degraded", "trino": "unreachable", "error": str(exc)}


app.include_router(families.router, prefix=settings.API_PREFIX)
app.include_router(products.router, prefix=settings.API_PREFIX)
app.include_router(ingest.router, prefix=settings.API_PREFIX)
app.include_router(legacy_theben.router, prefix=settings.API_PREFIX)
app.include_router(analyze.router, prefix=settings.API_PREFIX)
app.include_router(export.router, prefix=settings.API_PREFIX)
app.include_router(prompts.router, prefix=settings.API_PREFIX)
app.include_router(transparency.router, prefix=settings.API_PREFIX)

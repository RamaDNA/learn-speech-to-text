"""Pytest fixtures — database test terpisah (postgres test db) + TestClient."""
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.db import Base, get_db
from app.models import Item, ItemStock, Location, StockTransaction

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://warehouse:warehouse@localhost:5432/warehouse_test",
)


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(TEST_DATABASE_URL, poolclass=StaticPool)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(test_engine):
    factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def client(test_engine):
    def override_get_db():
        factory = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app = __import__("app.main", fromlist=["app"]).app
    app.dependency_overrides[get_db] = override_get_db
    # tanpa context manager: lifespan (seed + pull ollama) TIDAK dijalankan
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def api_key():
    return settings.api_key


@pytest.fixture(autouse=True)
def _clean_tables(test_engine):
    """Bersihkan semua data setelah tiap test (urutan FK: transaksi -> stock -> lokasi -> item)."""
    yield
    with test_engine.begin() as conn:
        conn.execute(delete(StockTransaction))
        conn.execute(delete(ItemStock))
        conn.execute(delete(Location))
        conn.execute(delete(Item))

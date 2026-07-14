"""Sanity checks for the SQLAlchemy model layer — import, table names, key field names."""

from app.db.models import (
    Base,
    Conversation,
    Document,
    DocumentNode,
    DocumentTree,
    EvalQuestionResult,
    EvalRun,
    Feedback,
    Message,
    RefreshToken,
    User,
)

ALL_MODELS = [
    User,
    RefreshToken,
    Document,
    DocumentTree,
    DocumentNode,
    Conversation,
    Message,
    Feedback,
    EvalRun,
    EvalQuestionResult,
]


def test_models_import_cleanly() -> None:
    assert len(ALL_MODELS) == 10


def test_every_model_has_uuid_pk() -> None:
    for model in ALL_MODELS:
        assert "id" in model.__table__.columns
        assert model.__table__.columns["id"].primary_key


def test_models_with_created_at_field() -> None:
    # DocumentTree, DocumentNode, EvalRun, EvalQuestionResult intentionally have no
    # created_at per the exact schema spec — they carry ingested_at/run_date instead,
    # or no timestamp at all.
    for model in (User, RefreshToken, Document, Conversation, Message, Feedback):
        assert "created_at" in model.__table__.columns


def test_mutable_models_have_updated_at() -> None:
    for model in (User, Document, Conversation):
        assert "updated_at" in model.__table__.columns


def test_document_node_uses_qdrant_not_pinecone() -> None:
    columns = DocumentNode.__table__.columns
    assert "qdrant_point_id" in columns
    assert "pinecone_id" not in columns


def test_document_uses_storage_key_not_s3_key() -> None:
    columns = Document.__table__.columns
    assert "storage_key" in columns
    assert "s3_key" not in columns


def test_document_node_has_composite_index() -> None:
    index_names = {ix.name for ix in DocumentNode.__table__.indexes}
    assert "ix_document_nodes_document_id_node_path" in index_names


def test_all_tables_registered_on_base_metadata() -> None:
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "users",
        "refresh_tokens",
        "documents",
        "document_trees",
        "document_nodes",
        "conversations",
        "messages",
        "feedback",
        "eval_runs",
        "eval_question_results",
    }
    assert expected <= table_names

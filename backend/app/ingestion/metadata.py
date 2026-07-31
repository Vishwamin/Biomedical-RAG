"""
ID generation and content hashing.
"""

import hashlib
import uuid


def compute_content_hash(file_bytes: bytes) -> str:
    return hashlib.sha256(file_bytes).hexdigest()


def generate_document_id() -> str:
    return f"doc_{uuid.uuid4().hex[:12]}"


def generate_chunk_id(document_id: str, chunk_index: int) -> str:
    return f"{document_id}_chunk_{chunk_index:04d}"

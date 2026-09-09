"""In-memory gallery of enrolled identities.

Vectors are L2-normalised, so inner product is cosine similarity. Search is a
NumPy matmul (thread-safe under FastAPI). A FAISS IndexFlatIP is kept in sync
when faiss can be imported without colliding with PyTorch's OpenMP runtime.

Entries are keyed by (org_id, person_id) so two organizations can both have
person id 1 without overwriting each other.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

import numpy as np
from sqlmodel import Session, select

from app.core.org_ctx import get_current_org_id
from app.db.models import FaceEmbedding, Organization, Person
from app.db.tenancy import set_search_path


def _try_faiss_index(dim: int):
    try:
        import faiss

        faiss.omp_set_num_threads(1)
        return faiss.IndexFlatIP(dim)
    except Exception:
        return None


def _org_key(org_id: int | None) -> int:
    if org_id is not None:
        return int(org_id)
    current = get_current_org_id()
    return int(current) if current is not None else 0


@dataclass
class Match:
    person_id: int
    name: str
    similarity: float
    n_embeddings: int


class FaceGallery:
    def __init__(self, dim: int = 512, encoder: str = "facenet"):
        self.dim = dim
        self.encoder = encoder
        self.index = _try_faiss_index(dim)
        self._matrix = np.zeros((0, dim), dtype=np.float32)
        self.person_ids: list[int] = []
        self.org_ids: list[int] = []
        self.names: dict[tuple[int, int], str] = {}
        self.counts: dict[tuple[int, int], int] = {}

    def __len__(self) -> int:
        return len(self.person_ids)

    def clear(self) -> None:
        if self.index is not None:
            self.index.reset()
        self._matrix = np.zeros((0, self.dim), dtype=np.float32)
        self.person_ids.clear()
        self.org_ids.clear()
        self.names.clear()
        self.counts.clear()

    def _slot(self, person_id: int, org_id: int | None) -> int | None:
        oid = _org_key(org_id)
        for i, (pid, row_org) in enumerate(zip(self.person_ids, self.org_ids, strict=True)):
            if pid == person_id and row_org == oid:
                return i
        return None

    def _ingest_person(self, person: Person, session: Session, org_id: int) -> np.ndarray | None:
        if person.is_active is False or person.id is None:
            return None
        embs = session.exec(
            select(FaceEmbedding).where(
                FaceEmbedding.person_id == person.id,
                FaceEmbedding.encoder == self.encoder,
            )
        ).all()
        if not embs:
            return None
        stacked = np.stack([_bytes_to_vec(e.vector, e.dim) for e in embs], axis=0)
        centroid = stacked.mean(axis=0)
        norm = np.linalg.norm(centroid)
        if norm < 1e-8:
            return None
        centroid = (centroid / norm).astype(np.float32)
        key = (int(org_id), int(person.id))
        self.person_ids.append(int(person.id))
        self.org_ids.append(int(org_id))
        self.names[key] = person.name
        self.counts[key] = len(embs)
        return centroid

    def rebuild(self, session: Session) -> int:
        """Reload centroids for `self.encoder` from every organization."""
        self.clear()
        vectors: list[np.ndarray] = []
        orgs = session.exec(select(Organization)).all()
        if not orgs:
            for person in session.exec(select(Person)).all():
                vec = self._ingest_person(person, session, int(person.org_id or 0))
                if vec is not None:
                    vectors.append(vec)
        else:
            for org in orgs:
                if org.id is None:
                    continue
                oid = int(org.id)
                set_search_path(session, oid)
                people = session.exec(select(Person).where(Person.org_id == oid)).all()
                for person in people:
                    vec = self._ingest_person(person, session, oid)
                    if vec is not None:
                        vectors.append(vec)
            set_search_path(session, None)
        if vectors:
            mat = np.ascontiguousarray(np.stack(vectors, axis=0), dtype=np.float32)
            self._matrix = mat
            if self.index is not None:
                self.index.add(mat)
        return len(self.person_ids)

    def add_person(self, person_id: int, name: str, embeddings: np.ndarray, *, org_id: int | None = None) -> None:
        """Insert or replace a person's centroid for one organization."""
        if embeddings.ndim == 1:
            embeddings = embeddings[None, ...]
        centroid = embeddings.mean(axis=0)
        centroid = centroid / max(float(np.linalg.norm(centroid)), 1e-8)
        centroid = np.ascontiguousarray(centroid, dtype=np.float32)
        oid = _org_key(org_id)
        self.remove_person(person_id, org_id=oid)
        self._matrix = np.concatenate([self._matrix, centroid[None, ...]], axis=0)
        if self.index is not None:
            self.index.add(centroid[None, ...])
        self.person_ids.append(person_id)
        self.org_ids.append(oid)
        self.names[(oid, person_id)] = name
        self.counts[(oid, person_id)] = int(embeddings.shape[0])

    def set_name(self, person_id: int, name: str, *, org_id: int | None = None) -> None:
        key = (_org_key(org_id), int(person_id))
        if key in self.names:
            self.names[key] = name

    def remove_person(self, person_id: int, *, org_id: int | None = None) -> None:
        loc = self._slot(person_id, org_id)
        if loc is None:
            return
        oid = self.org_ids[loc]
        keep = [i for i in range(len(self.person_ids)) if i != loc]
        self._matrix = self._matrix[keep] if keep else np.zeros((0, self.dim), dtype=np.float32)
        if self.index is not None:
            self.index.reset()
            if keep:
                self.index.add(np.ascontiguousarray(self._matrix))
        self.person_ids = [self.person_ids[i] for i in keep]
        self.org_ids = [self.org_ids[i] for i in keep]
        self.names.pop((oid, person_id), None)
        self.counts.pop((oid, person_id), None)

    def search(
        self,
        embedding: np.ndarray,
        top_k: int = 5,
        allowed_ids: Collection[int] | None = None,
        *,
        org_id: int | None = None,
    ) -> list[Match]:
        if len(self.person_ids) == 0:
            return []
        oid = org_id if org_id is not None else get_current_org_id()
        q = np.ascontiguousarray(embedding, dtype=np.float32).reshape(-1)
        scores = self._matrix @ q
        order = np.argsort(scores)[::-1]
        matches: list[Match] = []
        for idx in order:
            pid = self.person_ids[int(idx)]
            row_org = self.org_ids[int(idx)]
            if oid is not None and row_org != int(oid):
                continue
            if allowed_ids is not None and pid not in allowed_ids:
                continue
            key = (row_org, pid)
            matches.append(
                Match(
                    person_id=pid,
                    name=self.names.get(key, f"#{pid}"),
                    similarity=float(scores[int(idx)]),
                    n_embeddings=self.counts.get(key, 0),
                )
            )
            if len(matches) >= top_k:
                break
        return matches

    def embedding_of(self, person_id: int, *, org_id: int | None = None) -> np.ndarray | None:
        loc = self._slot(person_id, org_id)
        if loc is None:
            return None
        return self._matrix[loc].copy()


def _bytes_to_vec(blob: bytes, dim: int) -> np.ndarray:
    vec = np.frombuffer(blob, dtype=np.float32)
    if vec.size != dim:
        raise ValueError(f"embedding blob has {vec.size} values, expected {dim}")
    return np.asarray(vec, dtype=np.float32)


def vec_to_bytes(vec: np.ndarray) -> bytes:
    return np.asarray(vec, dtype=np.float32).tobytes()

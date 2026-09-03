"""Local, content-addressed attachment store.

Files are persisted under ``<base_dir>/objects/<2-char-prefix>/<sha256>`` and
metadata is kept in ``<base_dir>/meta/<sha256>.json`` so the store can be listed
and inspected without re-reading every object.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from ai.attachment.models import (
  AttachmentRef,
  content_id,
  guess_mime_type,
  normalize_filename,
)

BROAD_MEDIA_TYPES: frozenset[str] = frozenset([
  "image/png",
  "image/jpeg",
  "image/webp",
  "image/gif",
  "text/plain",
  "text/markdown",
  "text/x-python",
  "application/json",
  "application/pdf",
])


class AttachmentError(Exception):
  """Raised when attachment validation or storage fails."""

  def __init__(self, message: str, code: str, *, cause: Exception | None = None) -> None:
    super().__init__(message)
    self.message = message
    self.code = code
    self.cause = cause


@dataclass
class AttachmentLimits:
  """Admission limits for one upload batch."""

  max_bytes: int = 20 * 1024 * 1024
  max_count: int = 20
  max_total_bytes: int = 200 * 1024 * 1024
  max_image_pixels: int = 64_000_000
  max_image_dimension: int = 8192
  allowed_media_types: frozenset[str] = field(default_factory=lambda: BROAD_MEDIA_TYPES)

  def check_batch(self, total_count: int, total_bytes: int) -> None:
    if total_count > self.max_count:
      raise AttachmentError("Attachment batch exceeds the configured count limit.", "TOO_MANY_ATTACHMENTS")
    if total_bytes > self.max_total_bytes:
      raise AttachmentError("Attachment batch exceeds the configured aggregate byte limit.", "BATCH_TOO_LARGE")

  def check(self, mime_type: str, size: int, *, total_count: int, total_bytes: int) -> None:
    self.check_batch(total_count, total_bytes)
    if mime_type not in self.allowed_media_types:
      raise AttachmentError(f"Media type {mime_type} is not accepted.", "UNSUPPORTED_MEDIA_TYPE")
    if size > self.max_bytes:
      raise AttachmentError("Attachment exceeds the configured byte limit.", "ATTACHMENT_TOO_LARGE")


class AttachmentStore:
  """Content-addressed file attachment backend.

  The store is intentionally dependency-light: it does not require image
  processing libraries or openpilot imports. Callers may layer normalization
  on top by replacing the uploaded bytes before calling ``upload``.
  """

  def __init__(
    self,
    base_dir: str | os.PathLike[str],
    *,
    limits: AttachmentLimits | None = None,
  ) -> None:
    self.base_dir = Path(base_dir).resolve()
    self.limits = limits or AttachmentLimits()
    self.objects_dir = self.base_dir / "objects"
    self.meta_dir = self.base_dir / "meta"
    self.objects_dir.mkdir(parents=True, exist_ok=True)
    self.meta_dir.mkdir(parents=True, exist_ok=True)

  def _object_path(self, attachment_id: str) -> Path:
    if not attachment_id.startswith("sha256:") or len(attachment_id) != 71:
      raise AttachmentError("Invalid attachment id.", "INVALID_ATTACHMENT_ID")
    digest = attachment_id[7:]
    return self.objects_dir / digest[:2] / digest

  def _meta_path(self, attachment_id: str) -> Path:
    if not attachment_id.startswith("sha256:") or len(attachment_id) != 71:
      raise AttachmentError("Invalid attachment id.", "INVALID_ATTACHMENT_ID")
    digest = attachment_id[7:]
    return self.meta_dir / f"{digest}.json"

  def _load_meta(self, attachment_id: str) -> AttachmentRef:
    path = self._meta_path(attachment_id)
    try:
      data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
      raise AttachmentError("Attachment not found.", "ATTACHMENT_NOT_FOUND") from exc
    except json.JSONDecodeError as exc:
      raise AttachmentError("Attachment metadata is corrupt.", "ATTACHMENT_CORRUPT") from exc
    return AttachmentRef.from_dict(data)

  def upload(
    self,
    data: bytes,
    *,
    name: str | None = None,
    mime_type: str | None = None,
    _batch_totals: tuple[int, int] | None = None,
  ) -> AttachmentRef:
    """Validate and durably commit one attachment.

    ``_batch_totals`` is an internal hook for ``upload_many`` to enforce batch
    limits without recomputing running totals.
    """
    if not isinstance(data, (bytes, bytearray)):
      raise AttachmentError("Attachment data must be bytes.", "INVALID_ATTACHMENT_DATA")
    size = len(data)
    if size == 0:
      raise AttachmentError("Attachment is empty.", "EMPTY_ATTACHMENT")

    filename = normalize_filename(name)
    resolved_mime = mime_type or guess_mime_type(filename)
    total_count, total_bytes = _batch_totals or (1, size)
    self.limits.check(
      resolved_mime,
      size,
      total_count=total_count,
      total_bytes=total_bytes,
    )

    attachment_id = content_id(data)
    object_path = self._object_path(attachment_id)
    meta_path = self._meta_path(attachment_id)

    if not object_path.exists():
      object_path.parent.mkdir(parents=True, exist_ok=True)
      tmp_path = object_path.with_suffix(".tmp")
      try:
        tmp_path.write_bytes(data)
        tmp_path.replace(object_path)
      except OSError as exc:
        raise AttachmentError("Unable to persist attachment.", "ATTACHMENT_WRITE_FAILED") from exc
      finally:
        tmp_path.unlink(missing_ok=True)

    ref = AttachmentRef(
      attachment_id=attachment_id,
      mime_type=resolved_mime,
      size=size,
      name=filename,
    )

    if not meta_path.exists():
      meta_path.parent.mkdir(parents=True, exist_ok=True)
      tmp_meta = meta_path.with_suffix(".tmp")
      try:
        tmp_meta.write_text(json.dumps(ref.to_dict(), ensure_ascii=False), encoding="utf-8")
        tmp_meta.replace(meta_path)
      except OSError as exc:
        raise AttachmentError("Unable to persist attachment metadata.", "ATTACHMENT_WRITE_FAILED") from exc
      finally:
        tmp_meta.unlink(missing_ok=True)

    return ref

  def upload_many(self, items: list[tuple[bytes, str | None, str | None]]) -> list[AttachmentRef]:
    """Validate and commit a batch of attachments atomically (metadata-only)."""
    total_count = len(items)
    total_bytes = sum(len(data) for data, _, _ in items if isinstance(data, (bytes, bytearray)))
    self.limits.check_batch(total_count, total_bytes)

    refs: list[AttachmentRef] = []
    for data, name, mime_type in items:
      ref = self.upload(data, name=name, mime_type=mime_type, _batch_totals=(total_count, total_bytes))
      refs.append(ref)
    return refs

  def list(self) -> list[AttachmentRef]:
    """Return metadata for every stored attachment."""
    refs: list[AttachmentRef] = []
    if not self.meta_dir.exists():
      return refs
    for path in self.meta_dir.iterdir():
      if path.suffix != ".json":
        continue
      try:
        refs.append(AttachmentRef.from_dict(json.loads(path.read_text(encoding="utf-8"))))
      except Exception:
        continue
    return refs

  def get(self, attachment_id: str) -> tuple[AttachmentRef, bytes]:
    """Read one attachment and verify its bytes match the reference id."""
    ref = self._load_meta(attachment_id)
    path = self._object_path(attachment_id)
    try:
      data = path.read_bytes()
    except FileNotFoundError as exc:
      raise AttachmentError("Attachment object is missing.", "ATTACHMENT_NOT_FOUND") from exc
    if len(data) != ref.size:
      raise AttachmentError("Attachment size does not match reference.", "ATTACHMENT_CORRUPT")
    if content_id(data) != attachment_id:
      raise AttachmentError("Attachment digest does not match reference.", "ATTACHMENT_CORRUPT")
    return ref, data

  def get_meta(self, attachment_id: str) -> AttachmentRef:
    """Return only the metadata for an attachment."""
    return self._load_meta(attachment_id)

  def delete(self, attachment_id: str) -> bool:
    """Remove an attachment's metadata and object if no other reference exists.

    Returns ``True`` when the metadata file existed and was removed.
    """
    meta_path = self._meta_path(attachment_id)
    object_path = self._object_path(attachment_id)
    removed = False
    try:
      meta_path.unlink()
      removed = True
    except FileNotFoundError:
      pass
    try:
      object_path.unlink()
    except FileNotFoundError:
      pass
    return removed

  def object_path(self, attachment_id: str) -> Path:
    """Absolute host path for a stored attachment, or raise if invalid."""
    return self._object_path(attachment_id)

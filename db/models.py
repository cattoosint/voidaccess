"""
SQLAlchemy ORM models for VoidAccess's persistent storage layer.

Tables
------
investigations       — one record per pipeline run
sources              — canonical .onion domain registry (global, deduped by address)
investigation_sources — many-to-many: which sources appeared in which investigation
pages                — individual scraped pages (URL-level, one per unique URL)
entities             — structured intelligence artifacts extracted from pages
entity_relationships — directed edges between two entities

Design notes
------------
- Primary keys are UUID4, generated in Python so they're globally unique and safe
  to produce offline before insertion.
- All enum columns use native_enum=False (stored as VARCHAR) for portability between
  PostgreSQL (production) and SQLite (tests) and to avoid DDL-level ENUM management.
- DateTime columns are timezone-aware (UTC throughout).
- Soft cascade rules: deleting a Page cascades to its Entities and their Relationships.
  Deleting an Investigation does NOT delete its Sources (they are global).
"""

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.schema import UniqueConstraint


# ---------------------------------------------------------------------------
# Enums (application-level validation; stored as VARCHAR in the DB)
# ---------------------------------------------------------------------------

class SourceStatus(str, enum.Enum):
    ACTIVE = "active"
    DOWN = "down"
    UNKNOWN = "unknown"


class SourceType(str, enum.Enum):
    SEARCH_RESULT = "search_result"
    CRAWLED = "crawled"
    SEED = "seed"
    TELEGRAM = "telegram"


class EntityType(str, enum.Enum):
    """Entity types stored as VARCHAR in the DB."""
    CRYPTO_WALLET = "crypto_wallet"
    EMAIL = "email"
    PGP_KEY = "pgp_key"
    ONION_URL = "onion_url"
    CVE = "cve"
    IP_ADDRESS = "ip_address"
    PHONE = "phone"
    HANDLE = "handle"
    MALWARE = "malware"
    RANSOMWARE_GROUP = "ransomware_group"
    DOMAIN = "domain"
    OTHER = "other"
    FILE_HASH_MD5 = "file_hash_md5"
    FILE_HASH_SHA1 = "file_hash_sha1"
    FILE_HASH_SHA256 = "file_hash_sha256"
    MITRE_TECHNIQUE = "mitre_technique"


class RelationshipType(str, enum.Enum):
    """Edge types for the entity graph (Phase 3 will query these)."""
    CO_APPEARED_ON = "CO_APPEARED_ON"
    POSTED_BY = "POSTED_BY"
    LINKED_TO = "LINKED_TO"
    PAID_TO = "PAID_TO"
    MEMBER_OF = "MEMBER_OF"
    USED = "USED"
    CLAIMED = "CLAIMED"
    LIKELY_SAME_ACTOR = "LIKELY_SAME_ACTOR"
    CONFIRMED_SAME_ACTOR = "CONFIRMED_SAME_ACTOR"
    FUNDED_BY = "FUNDED_BY"
    POSSIBLE_SAME_AUTHOR = "POSSIBLE_SAME_AUTHOR"


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Junction table: Investigation <-> Source  (many-to-many)
# ---------------------------------------------------------------------------

investigation_sources = sa.Table(
    "investigation_sources",
    Base.metadata,
    sa.Column(
        "investigation_id",
        sa.UUID(as_uuid=True),
        sa.ForeignKey("investigations.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "source_id",
        sa.UUID(as_uuid=True),
        sa.ForeignKey("sources.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    sa.Column(
        "added_at",
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    ),
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class Investigation(Base):
    """
    One row per pipeline run.  Stores the query, parameters, and final summary.
    """
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), unique=True, nullable=False, default=uuid.uuid4,
        index=True,
    )
    query: Mapped[str] = mapped_column(sa.Text, nullable=False)
    refined_query: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    model_used: Mapped[Optional[str]] = mapped_column(sa.String(100), nullable=True)
    preset: Mapped[Optional[str]] = mapped_column(sa.String(50), nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="pending", server_default="pending"
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    is_seed: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)
    graph_status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default="pending", server_default="pending"
    )
    current_step: Mapped[int] = mapped_column(
        sa.Integer, server_default="0", default=0
    )
    current_step_label: Mapped[str] = mapped_column(
        sa.String(200), server_default="", default=""
    )
    entity_count: Mapped[int] = mapped_column(
        sa.Integer, server_default="0", default=0
    )
    page_count: Mapped[int] = mapped_column(
        sa.Integer, server_default="0", default=0
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        sa.Integer,
        sa.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    sources: Mapped[List["Source"]] = relationship(
        "Source", secondary=investigation_sources, back_populates="investigations"
    )
    entities: Mapped[List["Entity"]] = relationship(
        "Entity", back_populates="investigation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Investigation id={self.id} query={self.query[:50]!r}>"


class Source(Base):
    """
    Canonical record for a .onion domain.  One row per unique base address.
    Sources are global — they exist independently of any single investigation.
    """
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    onion_address: Mapped[str] = mapped_column(
        sa.String(255), unique=True, nullable=False, index=True
    )
    first_seen: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    # VARCHAR so we can add new statuses without migrations
    status: Mapped[str] = mapped_column(
        sa.String(20), nullable=False, default=SourceStatus.UNKNOWN.value
    )
    source_type: Mapped[str] = mapped_column(
        sa.String(30), nullable=False, default=SourceType.SEARCH_RESULT.value
    )

    # Relationships
    investigations: Mapped[List["Investigation"]] = relationship(
        "Investigation", secondary=investigation_sources, back_populates="sources"
    )
    pages: Mapped[List["Page"]] = relationship("Page", back_populates="source")

    def __repr__(self) -> str:
        return f"<Source {self.onion_address!r} status={self.status}>"


class Page(Base):
    """
    One row per unique URL.  Stores the cleaned text and a content hash for
    deduplication (Phase 1C crawler will use raw_content_hash to skip re-scraping
    identical content served at different URLs).
    """
    __tablename__ = "pages"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Nullable: pages discovered by the crawler before their parent domain
    # is resolved can be stored without a source_id.
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    url: Mapped[str] = mapped_column(sa.Text, unique=True, nullable=False)
    # SHA-256 hex digest of the raw downloaded content
    raw_content_hash: Mapped[Optional[str]] = mapped_column(
        sa.String(64), nullable=True, index=True
    )
    cleaned_text: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    scrape_timestamp: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    # When the post was authored (from HTML); null if not extractable — use scrape_timestamp as fallback
    posted_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True, index=True
    )
    # Populated by Phase 6 (i18n/detect.py); nullable until then
    language: Mapped[Optional[str]] = mapped_column(sa.String(10), nullable=True)
    byte_size: Mapped[Optional[int]] = mapped_column(sa.Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    source: Mapped[Optional["Source"]] = relationship("Source", back_populates="pages")
    entities: Mapped[List["Entity"]] = relationship(
        "Entity", back_populates="page", cascade="all, delete-orphan"
    )
    relationships_as_source: Mapped[List["EntityRelationship"]] = relationship(
        "EntityRelationship",
        back_populates="source_page",
        foreign_keys="EntityRelationship.source_page_id",
    )

    def __repr__(self) -> str:
        return f"<Page url={self.url[:80]!r}>"


class Entity(Base):
    """
    A single structured intelligence artifact extracted from a Page.

    The same real-world value (e.g. a Bitcoin wallet address) may appear across
    many pages and therefore produce many Entity rows.  Phase 2D (extractor/normalizer.py)
    will deduplicate them into canonical records; for now every extraction yields
    its own row linked to the page where it was found.
    """
    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    page_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("pages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Optional back-reference to the investigation that produced this entity.
    # Phase 2 extractor will populate this; Phase 1A records may leave it NULL.
    investigation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("investigations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Use EntityType enum values, but stored as plain VARCHAR for extensibility
    entity_type: Mapped[str] = mapped_column(sa.String(50), nullable=False, index=True)
    value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    canonical_value: Mapped[Optional[str]] = mapped_column(sa.String, nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False, default=1.0)
    # Surrounding post text for analyst context (longer snippets improve stylometry)
    context_snippet: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    context = sa.orm.synonym("context_snippet")
    extraction_method: Mapped[Optional[str]] = mapped_column(
        sa.String(10), nullable=True
    )  # "regex", "NER", "LLM"
    historical_context: Mapped[Optional[str]] = mapped_column(sa.Text, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_seen: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    page: Mapped["Page"] = relationship("Page", back_populates="entities")
    investigation: Mapped[Optional["Investigation"]] = relationship(
        "Investigation", back_populates="entities"
    )
    relationships_as_a: Mapped[List["EntityRelationship"]] = relationship(
        "EntityRelationship",
        foreign_keys="EntityRelationship.entity_a_id",
        back_populates="entity_a",
        cascade="all, delete-orphan",
    )
    relationships_as_b: Mapped[List["EntityRelationship"]] = relationship(
        "EntityRelationship",
        foreign_keys="EntityRelationship.entity_b_id",
        back_populates="entity_b",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Entity type={self.entity_type!r} value={str(self.value)[:50]!r}>"

    __table_args__ = (
        sa.Index("ix_entity_canonical", "entity_type", "canonical_value"),
    )


class EntityRelationship(Base):
    """
    A directed edge between two Entity records.

    Captures co-occurrence, attribution, and other semantic links.
    Phase 3 (graph/) will read these to build the NetworkX / Neo4j graph.
    """
    __tablename__ = "entity_relationships"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_a_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_b_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Use RelationshipType enum values; stored as VARCHAR
    relationship_type: Mapped[str] = mapped_column(
        sa.String(50), nullable=False, index=True
    )
    source_page_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("pages.id", ondelete="SET NULL"),
        nullable=True,
    )
    confidence: Mapped[float] = mapped_column(sa.Float, nullable=False, default=1.0)
    first_seen: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    investigation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("investigations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Relationships
    entity_a: Mapped["Entity"] = relationship(
        "Entity", foreign_keys=[entity_a_id], back_populates="relationships_as_a"
    )
    entity_b: Mapped["Entity"] = relationship(
        "Entity", foreign_keys=[entity_b_id], back_populates="relationships_as_b"
    )
    source_page: Mapped[Optional["Page"]] = relationship(
        "Page",
        foreign_keys=[source_page_id],
        back_populates="relationships_as_source",
    )

    def __repr__(self) -> str:
        return (
            f"<EntityRelationship {self.entity_a_id} "
            f"-[{self.relationship_type}]-> {self.entity_b_id}>"
        )

    __table_args__ = (
        sa.Index(
            "ix_entity_relationships_lookup",
            "entity_a_id",
            "entity_b_id",
            "relationship_type",
        ),
    )


class MonitorAlertSeverity(str, enum.Enum):
    """Stored as VARCHAR in ``monitor_alerts.severity``."""

    info = "info"
    warning = "warning"
    critical = "critical"


class MonitorAlert(Base):
    """
    Persisted record of every alert fired by the monitoring system.
    Created whenever a monitor detects a change significant enough to alert.
    """

    __tablename__ = "monitor_alerts"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    monitor_name: Mapped[str] = mapped_column(sa.String, nullable=False, index=True)
    triggered_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    change_type: Mapped[str] = mapped_column(sa.String(50), nullable=False)
    summary: Mapped[str] = mapped_column(sa.Text, nullable=False, default="")
    diff_data: Mapped[Optional[dict[str, Any]]] = mapped_column(sa.JSON, nullable=True)
    severity: Mapped[str] = mapped_column(
        sa.String(20),
        nullable=False,
        default=MonitorAlertSeverity.info.value,
    )
    entity_count_delta: Mapped[int] = mapped_column(
        sa.Integer, nullable=False, default=0
    )
    delivered: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    delivery_channels: Mapped[Optional[List[Any]]] = mapped_column(sa.JSON, nullable=True)
    acknowledged: Mapped[bool] = mapped_column(
        sa.Boolean, nullable=False, default=False
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        sa.Index("ix_monitor_alerts_monitor_triggered", "monitor_name", "triggered_at"),
    )


class InvestigationEntityLink(Base):
    """
    Links an entity to additional investigations beyond its origin.
    Enables cross-investigation deduplication without moving entity ownership.
    """
    __tablename__ = "investigation_entity_links"
    
    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    entity_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True), sa.ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False
    )
    linked_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    
    __table_args__ = (
        sa.UniqueConstraint("entity_id", "investigation_id"),
    )


class ActorStyleProfile(Base):
    """
    Stores aggregated writing style fingerprints for unique actors.
    Updated incrementally as new text samples are discovered.
    """
    __tablename__ = "actor_style_profiles"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    canonical_value: Mapped[str] = mapped_column(sa.String, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(sa.String, nullable=False)
    style_vector: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False)
    sample_count: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")
    total_chars: Mapped[int] = mapped_column(sa.Integer, default=0, server_default="0")
    last_updated: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("canonical_value", "entity_type"),
    )

class User(Base):
    """
    VoidAccess system user.  Handles authentication and access control.
    """
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(sa.String(255), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(sa.String, nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, nullable=False)

    # Forces password reset on next login
    # Set to True for the default admin account
    must_reset_password: Mapped[bool] = mapped_column(sa.Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    last_login_at: Mapped[Optional[datetime]] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<User {self.email!r}>"


class UserApiKey(Base):
    """
    Per-user encrypted API key storage.
    Keys are encrypted at rest using Fernet (AES-128) with a key derived from JWT_SECRET.
    """
    __tablename__ = "user_api_keys"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        sa.Integer,
        sa.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key_name: Mapped[str] = mapped_column(sa.String(64), nullable=False)
    encrypted_value: Mapped[str] = mapped_column(sa.Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        sa.UniqueConstraint("user_id", "key_name"),
    )


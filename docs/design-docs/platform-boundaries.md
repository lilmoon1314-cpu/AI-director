# Platform boundaries

This document owns durable platform-level design reasoning that code alone does not make obvious.

## Architecture style

The application is a modular monolith: one FastAPI process, one React application, a primary SQLite
database, and a separate asset SQLite database plus image files. The MVP has no independent scaling or
multi-user deployment need, so service decomposition would add coordination cost without a current
benefit. A new service process requires a concrete load, isolation, or deployment reason.

Domain modules expose cross-module operations through their service layer. Exact import permissions
are owned and enforced by the import-linter contracts in `backend/pyproject.toml`; this document does
not duplicate that matrix. Request routers are composition points, not data-access layers. The projects
router is the deliberate composition point for deletion that spans multiple domains.

## Storage and transactions

The primary database uses SQLAlchemy and Alembic with SQLite foreign keys and WAL enabled. Stable
world-model identity and referential integrity are database-backed as well as service-validated.

The asset database has a different lifecycle: it is derived/presentation storage and is bootstrapped
idempotently. Its schema evolves additively until a dedicated migration chain is justified. Operations
that span the primary and asset databases cannot be one atomic transaction; project and entity cleanup
therefore combines explicit cleanup with orphan cleanup as a recovery mechanism.

Transaction ownership belongs to domain services. A helper explicitly documented as participating in
its caller's transaction does not commit independently.

## Configuration and generated contracts

Runtime endpoints, credentials, limits, and paths are supplied through `backend/app/config.py` or the
frontend environment. Source scans and type checks own enforceable configuration rules.

The backend OpenAPI document is generated from the application, and frontend API types are generated
from that document. Code/schema is authoritative; generated files are projections with real frontend
consumers, not independent design sources.

## Error boundary

Domain failures use structured application exceptions and a single HTTP error-response boundary. The
observable response is specified in the relevant product spec and enforced by schemas/tests. Runtime
tracebacks stay in local diagnostics rather than API responses.

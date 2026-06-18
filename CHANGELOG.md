# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Memory data model with provenance and value tracking for household and per-member records.
- Evidence accrual for memory inferences, with confidence bumping as new conversations corroborate a belief.
- Portfolio summary upsert so holdings stay consistent across updates.

### Changed

- Transcript lifecycle now uses durable terminal JSONL events instead of `.closed` marker files.

### Fixed

- Entity writes are now idempotent, preventing duplicate records on retried operations.

### Security

- Member IDs are validated against a strict regex to prevent path-traversal access to memory files.

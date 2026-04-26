# Changelog

All notable changes to DAST Analyzer will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
This project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Sprint 1: Project scaffolding — directory structure, Docker Compose, Nginx + TLS
- Sprint 1: PostgreSQL schema — models: User, UserSession, Scan, Vulnerability, Wordlist
- Sprint 1: FastAPI skeleton — routers stubs, UUIDv7 request logging middleware
- Sprint 1: Alembic migrations setup
- Sprint 1: GitLab CI/CD pipeline (lint → sast → test → build → trivy → deploy)
- Sprint 1: Semantic versioning, CHANGELOG, .env.example

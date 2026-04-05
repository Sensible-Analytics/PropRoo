# Architectural Guardrails for PropRoo

**Purpose**: Ensure all code changes maintain architectural integrity.

---

## Required Diagrams

### C4 Diagrams
- **Context**: `docs/architecture/diagrams/system-context.mmd`
- **Container**: `docs/architecture/diagrams/container.mmd`

### Class Diagrams
- **Classes**: `docs/architecture/diagrams/classes.mmd`

### Data Flow
- **DFD**: `docs/architecture/diagrams/data-flow.mmd`

---

## ADR Requirements

All architecture decisions must be documented in `docs/adr/`.

See `docs/adr/TEMPLATE.md` for format.

---

## Tech Stack

- **Frontend**: React 19 + Vite + Tailwind 4 + Zustand
- **Backend**: Python (FastAPI) with DuckDB/Parquet
- **Database**: Neon (PostgreSQL)
- **Deployment**: Vercel + Cloudflare

---

## Diagram Tools

```bash
# Auto-generate diagrams
npm install -g oh-my-mermaid
oh-my-mermaid setup --platform claude-code
```

---

*Last updated: 2026-04-05*
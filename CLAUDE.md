# Architecture Guidelines

## Clean Architecture Layers

```
src/
├── presentation/    # UI components, pages, controllers
├── application/     # Use cases, services
├── domain/          # Business entities, rules
└── infrastructure/  # DB, APIs, external services
```

## Dependency Rules

- `presentation` → `application`, `domain`
- `application` → `domain`
- `domain` → NO external dependencies
- `infrastructure` → `domain`

## Hexagonal Architecture (Ports & Adapters)

```
src/core/
├── domain/        # Pure business logic
└── ports/         # Interfaces (*.port.ts)

src/adapters/
├── primary/       # REST, GraphQL drivers
└── secondary/     # DB, external services driven
```

## Naming Conventions

- Ports: `*.port.ts`
- Adapters: `*.adapter.ts`
- Controllers: `*.controller.ts`
- Services: `*.service.ts`

## Forbidden Patterns

- NO direct infrastructure imports in presentation
- NO business logic in UI components
- NO circular dependencies
- All external deps go through interfaces

## Before Generating Code

1. Identify which layer the code belongs to
2. Check dependency rules
3. Use ports for external integrations
4. Run: `npm run lint` before commit
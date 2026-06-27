# CONVENTIONS.md

Code style and structural standards for this codebase.
Apply to all Python code unless a spec explicitly overrides.

## Type Hints and Docstrings

All public functions and classes must have both.

## Import Order

Standard library → third-party → internal, blank line between groups.
No wildcard imports. No unused imports.

## Naming

| Element | Convention |
|---|---|
| Function / variable | `snake_case` |
| Class | `PascalCase` |
| Constant | `UPPER_SNAKE_CASE` |
| Module / file | `snake_case`, responsibility-named |

## Classes vs Functions

Use classes for shared state or config across methods.
Use functions for stateless, single-purpose operations.

## Secrets

All secrets in `api.env`. Never in code. `api.env` is in `.gitignore`.

## (Expand this file with project-specific patterns as they emerge.)

# Comece por aqui

Esta versão corresponde à v0.3.0 — Fundação modular concluída. A próxima
milestone é v0.4.0 — Blog CMS.

## Objetivo desta etapa

Antes de iniciar uma tarefa da v0.4, o Codex deve:

1. ler `AGENTS.md`;
2. ler `docs/PRODUCT_SCOPE.md`, `docs/ARCHITECTURE.md` e `docs/ROADMAP.md`;
3. confirmar o estado do repositório com `git status`;
4. executar ou consultar o resultado atual de `make verify`;
5. implementar somente uma tarefa explicitamente aprovada, sem antecipar
   funcionalidades futuras.

## Primeiro comando

```bash
git status
```

O gate reproduzível da base é:

```bash
make verify
```

## Próxima milestone

A v0.4.0 adicionará o Blog CMS conforme `docs/ROADMAP.md`. O trabalho só deve
começar mediante tarefa explícita e plano aprovado; Article, Category, Tag e o
workflow editorial ainda não fazem parte da base concluída na v0.3.0.

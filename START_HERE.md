# Comece por aqui

Esta versão preserva o código da base v0.2 e adiciona a documentação fundacional do projeto.

## Objetivo desta etapa

Antes de desenvolver novas funcionalidades, o Codex deve:

1. ler `AGENTS.md`;
2. ler `docs/PRODUCT_SCOPE.md`, `docs/ARCHITECTURE.md` e `docs/ROADMAP.md`;
3. auditar a base atual sem alterar o código;
4. registrar a auditoria em `docs/audits/TECHNICAL_AUDIT_V0.2.md`;
5. aguardar aprovação antes de implementar.

## Primeiro comando

```bash
git status
```

Caso a pasta ainda não seja um repositório Git:

```bash
git init
git add .
git commit -m "chore: import rennam.dev foundation"
```

Depois crie a branch da auditoria:

```bash
git switch -c chore/technical-audit
```

## Primeira tarefa para o Codex

Peça ao Codex:

> Leia `AGENTS.md` e toda a documentação em `docs/`. Faça uma auditoria técnica somente leitura da base v0.2. Não altere arquivos da aplicação. Registre evidências, riscos, pontos reutilizáveis e um plano de estabilização em `docs/audits/TECHNICAL_AUDIT_V0.2.md`. Antes de escrever o relatório, apresente um plano curto da auditoria.

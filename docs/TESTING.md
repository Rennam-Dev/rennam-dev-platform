# Testes

## Ambiente oficial de validação

A v0.2.1 usa Python 3.12 como versão oficial. O fluxo completo requer somente
Docker com Docker Compose e é executado por:

```bash
make verify
```

O comando constrói `Dockerfile.test` com as dependências já declaradas em
`requirements-dev.txt`, restringidas às versões validadas em
`requirements-test.lock`, e inicia `compose.test.yml` sob o projeto isolado
`rennam-dev-test`. O PostgreSQL 16 de teste:

- usa o banco `rennam_test`, com sufixo obrigatório `_test`;
- usa credenciais fictícias exclusivas do ambiente descartável;
- não publica porta no host;
- usa `tmpfs`, sem volume persistente;
- não lê nem reutiliza `DATABASE_URL` ou `.env` da aplicação;
- permanece em uma rede interna separada do Compose de desenvolvimento.

É possível subir e destruir somente esse banco com:

```bash
make test-db-up
make test-db-down
```

`make test-db-down` atua apenas no projeto `rennam-dev-test`. Não use comandos
globais de limpeza do Docker.

## Ordem e proteções

O fluxo de `scripts/verify.sh` executa, nesta ordem:

1. a guarda pura `assert_safe_test_database` e Ruff;
2. somente `tests/test_database_guard.py` e `tests/test_config.py`;
3. a suíte completa com PostgreSQL descartável;
4. `alembic current` e `alembic heads`;
5. `upgrade head`, `alembic check`, `downgrade base` e novo `upgrade head`;
6. `alembic current` para confirmar a revisão final.

Os dois módulos de testes puros usam o marcador `no_database`, portanto não
executam `create_all()` ou `drop_all()`. Antes da criação do engine, a suíte
substitui explicitamente `DATABASE_URL` por `TEST_DATABASE_URL`. A mesma guarda
é chamada imediatamente antes de todo DDL das fixtures e antes de cada comando
Alembic no fluxo. Ela exige `APP_ENV=test`, rejeita a URL normal, arquivos
SQLite e qualquer PostgreSQL cujo banco não termine em `_test`.

O container de validação recebe somente `TEST_DATABASE_URL`; `DATABASE_URL` é
exportada pelo script apenas depois de a URL passar pela guarda. Falhas não
exibem credenciais nem a URL completa.

## Camadas

- Unitários para regras de domínio.
- Integração para repositórios e banco.
- Rotas públicas e administrativas.
- Migrations.
- Segurança e autorização.
- End-to-end para fluxos críticos.
- Verificações de SEO.

## Fluxos críticos planejados

- Login válido e inválido, CSRF e expiração de sessão.
- Criar rascunho, preview, publicar e arquivar.
- Conteúdo privado não acessível e fora do sitemap.
- Mudança de slug com 301.
- Página em manutenção com status adequado.
- Tradução ausente sem URL vazia.
- Convite, acesso permitido, acesso negado e quota excedida.

# rennam.dev — Projeto 0

Portfólio técnico e mini-CMS autoral construído com FastAPI, Jinja2,
PostgreSQL, SQLAlchemy e Alembic.

O site público apresenta projetos como estudos de caso. O painel privado em
`/admin` permite cadastrar, editar, publicar, destacar e excluir projetos sem
alterar dicionários Python ou refazer o deploy do código.

## O que já existe nesta base

- Home, Sobre, Projetos, Blog e Contato;
- páginas públicas em `/projetos/{slug}`;
- filtro por tecnologia;
- painel protegido por sessão;
- cookie `HttpOnly`, `SameSite=Lax` e `Secure` em produção;
- proteção CSRF em todas as mutações administrativas;
- senha com hash Argon2;
- estados `draft` e `published`;
- PostgreSQL + SQLAlchemy 2.0;
- migrations com Alembic;
- Markdown sanitizado para os estudos de caso;
- sitemap, robots.txt, página 404 e `/health`;
- Dockerfile e Docker Compose;
- testes básicos;
- seed do primeiro projeto: **Rennam Semantic Docs**.

O blog permanece baseado em arquivos Markdown nesta fase. Upload de imagens,
editor visual, múltiplos usuários e agendamento não fazem parte do MVP.

## Arquitetura

```text
Visitante ──> rotas públicas ──> projetos publicados
                                     ↑
Rennam ──> /admin ──> CRUD ──> PostgreSQL

Projetos de IA continuam em repositórios próprios.
O rennam.dev publica apenas seus estudos de caso e links.
```

```text
app/
├── core/          # configurações, banco e segurança
├── models/        # modelos SQLAlchemy
├── repositories/  # consultas ao banco
├── routes/        # rotas públicas e administrativas
├── schemas/       # validação dos formulários
├── services/      # regras de negócio
└── scripts/       # hash de senha e seed
```

## Início rápido com Docker

Requisitos: Docker e Docker Compose.

1. Crie as variáveis locais:

   ```bash
   cp .env.example .env
   ```

2. Gere o segredo de sessão:

   ```bash
   openssl rand -hex 32
   ```

   Cole o resultado em `SESSION_SECRET`.

3. Gere o hash da senha administrativa:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install "pwdlib[argon2]"
   python -m app.scripts.password_hash
   ```

   Cole o resultado completo em `ADMIN_PASSWORD_HASH`, entre aspas simples.
   Isso impede que os caracteres `$` do Argon2 sejam interpretados:

   ```env
   ADMIN_PASSWORD_HASH='$argon2id$...'
   ```

4. Defina também uma senha para o PostgreSQL no `.env`:

   ```env
   POSTGRES_PASSWORD=uma-senha-local-forte
   ```

5. Suba a aplicação:

   ```bash
   docker compose up --build
   ```

6. Em outro terminal, insira o projeto inicial:

   ```bash
   docker compose exec web python -m app.scripts.seed
   ```

Acesse:

- site: http://127.0.0.1:8000
- painel: http://127.0.0.1:8000/admin
- documentação local da API: http://127.0.0.1:8000/docs

## Desenvolvimento sem Docker

Use Python 3.12 ou 3.13. A base evita Python 3.14 por enquanto para reduzir
atrito com dependências que ainda possam estar amadurecendo.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
alembic upgrade head
python -m app.scripts.seed
uvicorn app.main:app --reload
```

O valor padrão de `DATABASE_URL` no código usa SQLite apenas como conveniência
para testes e uma primeira execução. A configuração prevista para o projeto é
PostgreSQL.

## Comandos úteis

```bash
make migrate
make seed
make run
make test
make lint
```

Nova migration:

```bash
alembic revision --autogenerate -m "descricao da alteracao"
alembic upgrade head
```

## Regras de segurança

- Nunca comite `.env`.
- `APP_ENV` aceita somente `development`, `test`, `staging` ou `production`,
  sem variações de caixa ou espaços.
- Em produção, a aplicação exige no startup: `SESSION_SECRET` com pelo menos
  32 caracteres e diferente do default, `ADMIN_PASSWORD_HASH` em formato
  Argon2, `ADMIN_USERNAME` não vazio, PostgreSQL em `DATABASE_URL` e
  `SITE_URL` HTTPS sem query string ou fragment.
- O painel usa sessão, não JWT, porque é uma aplicação renderizada no servidor.
- O Markdown é sanitizado antes de ser exibido.
- Imagens serão armazenadas em object storage; o banco guardará somente URLs e
  metadados.
- Antes do deploy público, adicione limitação de tentativas no login e revise
  headers de segurança no proxy.

## Próximas versões

### V1 — base entregue

- CRUD completo de projetos;
- publicação e destaque;
- estudos de caso;
- autenticação por sessão;
- PostgreSQL e migrations.

### V1.1

- preview de rascunho;
- upload de capa para storage compatível com S3;
- editor Markdown com toolbar;
- campos Open Graph por projeto;
- auditoria simples de login;
- rate limit no painel.

### V2

- CRUD do blog;
- tags e categorias;
- agendamento de publicação;
- painel de mídia.

## Projeto 1 — Rennam Semantic Docs

O primeiro projeto técnico acompanha a disciplina de embeddings e bancos
vetoriais, mas será autoral:

```text
documento
  → extração e limpeza
  → chunks
  → embeddings
  → PostgreSQL + pgvector
  → busca por similaridade
  → trechos relevantes
```

O RAG completo entra depois:

```text
pergunta + trechos recuperados → LLM → resposta com fontes
```

O repositório da aplicação será separado do `rennam.dev`. O site hospedará o
estudo de caso e apontará para o código e a demonstração.

---

## Documentação fundacional

Esta distribuição adiciona a fundação de produto e governança sem alterar as funcionalidades da aplicação v0.2.

Comece por [START_HERE.md](START_HERE.md) e leia:

- [Escopo do produto](docs/PRODUCT_SCOPE.md)
- [Arquitetura](docs/ARCHITECTURE.md)
- [Roadmap](docs/ROADMAP.md)
- [Mini CMS](docs/CMS.md)
- [SEO](docs/SEO.md)
- [Segurança](docs/SECURITY.md)
- [Labs](docs/LABS.md)
- [Codex Skills](docs/CODEX_SKILLS.md)
- [Instruções para agentes](AGENTS.md)

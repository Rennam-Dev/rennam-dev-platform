# rennam.dev — Projeto 0

> **Versão atual:** v0.2.1
> **Status:** fundação estabilizada e pronta para evolução funcional, mas
> **não classificada como pronta para produção**. A validação reproduzível está
> disponível por `make verify`.

Portfólio técnico e mini-CMS autoral construído com FastAPI, Jinja2,
PostgreSQL, SQLAlchemy e Alembic.

O site público apresenta projetos como estudos de caso. O painel privado em
`/admin` permite cadastrar, editar, publicar e destacar projetos sem alterar
dicionários Python ou refazer o deploy do código. A exclusão definitiva está
temporariamente desabilitada até existir arquivamento e restauração seguros.

## O que já existe nesta base

- Home, Sobre, Projetos, Blog e Contato;
- páginas públicas em `/projetos/{slug}`;
- filtro por tecnologia;
- painel protegido por sessão;
- cookie `HttpOnly`, `SameSite=Lax` e `Secure` em staging/production;
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
Rennam ──> /admin ──> gestão de projetos ──> PostgreSQL

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

Este Compose é exclusivamente para development local. O serviço web escuta
somente em `127.0.0.1` e não deve ser exposto diretamente em rede não confiável
nem reutilizado como topologia de staging/production.

1. Crie as variáveis locais:

   ```bash
   cp .env.example .env
   ```

   Esse arquivo contém somente placeholders de development. Ele não é um
   perfil implantável e deve falhar se `APP_ENV` for apenas trocado para
   `staging` ou `production` sem substituir os valores sensíveis.

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

Python 3.12 é a versão oficial do projeto, registrada em `.python-version`, no
Dockerfile da aplicação e na imagem de validação. Outras versões não fazem
parte da matriz validada da v0.2.1.

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
make verify
make migrate
make seed
make run
make test
make lint
```

`make verify` é a entrada reproduzível recomendada. Ela não lê o `.env` da
aplicação: constrói uma imagem Python 3.12 com as dependências declaradas e as
versões validadas em `requirements-test.lock`, sobe um PostgreSQL 16 efêmero
chamado `rennam_test`, executa Ruff, os testes puros, a suíte completa e o ciclo
Alembic `upgrade head`, `downgrade base`, `upgrade head`. Ao terminar, inclusive
em caso de erro, remove somente os containers e recursos do projeto Compose
`rennam-dev-test`.

Para inspecionar apenas a disponibilidade do PostgreSQL descartável:

```bash
make test-db-up
make test-db-down
```

O serviço de teste não publica porta no host, usa credenciais fictícias próprias
e armazena os dados em `tmpfs`; ele não compartilha o volume `postgres_data` do
ambiente de desenvolvimento.

Nova migration:

```bash
alembic revision --autogenerate -m "descricao da alteracao"
alembic upgrade head
```

## Regras de segurança

- Nunca comite `.env`.
- `APP_ENV` aceita somente `development`, `test`, `staging` ou `production`,
  sem variações de caixa ou espaços.
- Em staging e production, a aplicação exige no startup: `SESSION_SECRET` com
  pelo menos 32 caracteres e diferente do default, `ADMIN_PASSWORD_HASH` em
  formato Argon2, `ADMIN_USERNAME` não vazio, PostgreSQL em `DATABASE_URL` e
  `SITE_URL` HTTPS sem credenciais, query string ou fragment. O hostname de
  `SITE_URL` deve estar em `ALLOWED_HOSTS`.
- O painel usa sessão, não JWT, porque é uma aplicação renderizada no servidor.
- O Markdown é sanitizado antes de ser exibido.
- Imagens serão armazenadas em object storage; o banco guardará somente URLs e
  metadados.
- Antes de qualquer deploy staging/production, configure `ALLOWED_HOSTS`,
  restrinja `FORWARDED_ALLOW_IPS` ao proxy controlado e publique o ambiente
  somente por HTTPS.

## Estado e roadmap

### Entregue na v0.2.1

- gestão administrativa de projetos, sem alteração de slug ou hard delete;
- publicação, destaque e estudos de caso públicos;
- autenticação por sessão, CSRF, Argon2 e rate limiting do login;
- auditoria sanitizada dos eventos de autenticação;
- PostgreSQL, SQLAlchemy e ciclo Alembic validado em banco descartável;
- configuração fail-closed para staging/production e baseline de segurança HTTP;
- validação reproduzível com Ruff, pytest e Alembic por `make verify`.

### Planejado, ainda não implementado

- v0.3: evolução modular orientada por casos reais;
- v0.4: Blog CMS com estado editorial default-private, categorias e tags;
- versões posteriores: workflow editorial, SEO avançado, internacionalização,
  identidade e gateway controlado de Labs.

O detalhamento e a ordem aprovados permanecem em
[docs/ROADMAP.md](docs/ROADMAP.md).

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

Esta distribuição corresponde à fundação v0.2.1 estabilizada. Ela está pronta
para evolução incremental, mas os requisitos operacionais P2 ainda impedem
classificá-la como pronta para produção.

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

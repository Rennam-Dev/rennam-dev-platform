# Auditoria técnica da base v0.2

**Data:** 2026-08-07
**Escopo:** estado `3a9f0c7` da branch `master`
**Modo:** inspeção somente leitura da aplicação; este relatório é o único arquivo criado
**Conclusão de release:** **não liberar a base atual em produção antes dos itens P0 e P1 de segurança operacional**

## 1. Resumo executivo

A v0.2 é uma fundação pequena, legível e proporcional ao MVP original de portfólio com CMS de projetos. O fluxo público usa FastAPI e Jinja2 com renderização no servidor; projetos publicados são separados de rascunhos nas consultas; o painel usa sessão assinada, Argon2 e CSRF; o Markdown é sanitizado; models e a migration inicial estão estruturalmente coerentes; e a aplicação Docker roda como usuário não privilegiado. A separação dos Labs também foi preservada: não há lógica de IA nem credenciais de LLM no navegador ou no CMS.

A base, porém, ainda não está pronta para produção. O achado mais grave é a fixture de testes executar `drop_all()` no engine construído diretamente de `DATABASE_URL`, sem exigir um banco isolado de testes. Um `pytest` iniciado com configuração equivocada pode apagar as tabelas reais de projetos. Também faltam proteção contra força bruta no login, validação robusta das configurações de produção, política para alteração de slug e exclusão de conteúdo publicado, testes de migrations e endurecimento operacional do container.

Boa parte da distância para a arquitetura documental é intencional e está no roadmap: traduções, workflow editorial completo, usuários, convites, portal e gateway de Labs ainda não deveriam ser implementados na v0.2. Esses itens são registrados como lacunas planejadas, e não como regressões.

### Síntese quantitativa

- 27 arquivos Python passaram por parsing estático de AST.
- 10 rotas públicas e 9 rotas administrativas foram identificadas.
- 2 models principais e 1 associação N:N são cobertos por uma migration inicial com `upgrade()` e `downgrade()`.
- 6 testes estão definidos: 3 públicos e 3 administrativos.
- 1 achado crítico, 3 altos, 7 médios e 4 baixos foram registrados.
- Testes, lint e Alembic não foram executados porque as dependências Python não estão instaladas e a tarefa proíbe instalação.

## 2. Método, evidências e limitações

Foram lidos `AGENTS.md`, `START_HERE.md`, todos os arquivos sob `docs/`, os arquivos de raiz, código Python, migrations, testes, templates, conteúdo Markdown, CSS e manifests Docker. Também foram inspecionados o estado Git, o inventário de arquivos e as ferramentas disponíveis.

Validações não destrutivas realizadas:

- `git status --short --branch`, `git log` e inventário com `rg --files`/`git ls-files`;
- parsing via `ast.parse` de 27 arquivos Python;
- extração estática do mapa de rotas;
- conferência manual de model, schema e migration;
- `docker compose config --quiet`, que não pôde concluir porque `.env` está corretamente ausente do repositório;
- conferência final de diff e whitespace após a criação deste relatório.

Limitações:

- o host usa Python 3.14.5, enquanto o projeto declara Python 3.12/3.13;
- FastAPI, SQLAlchemy, Alembic, pytest, Ruff e as demais dependências não estão instaladas;
- nenhum banco PostgreSQL foi acessado;
- nenhuma imagem Docker foi construída, pois isso instalaria dependências;
- nenhum teste foi executado, inclusive porque a fixture atual não é segura até receber isolamento explícito;
- a auditoria é estática; comportamento dependente de versões concretas das bibliotecas precisa ser confirmado depois em ambiente isolado.

Não foi lido nenhum segredo. Não existe `.env` local no estado auditado, e `.env` está ignorado pelo Git e pelo contexto Docker.

## 3. Estrutura e fluxo atuais

### 3.1 Estrutura

```text
app/
├── core/          configuração, engine e segurança
├── models/        Project, Technology e associação N:N
├── repositories/  consultas de projetos
├── routes/        HTTP público e administrativo
├── schemas/       validação do formulário de projeto
├── services/      criação, atualização, exclusão e tecnologias
├── scripts/       geração de hash e seed
├── main.py        factory, middleware, estáticos e routers
└── web.py         templates, Markdown e blog em arquivos

content/blog/      posts Markdown publicados pelo repositório
templates/         páginas públicas e administrativas SSR
static/            CSS e mídia local
migrations/        ambiente Alembic e migration inicial
tests/             testes básicos de rota com TestClient
docs/              fundação, ADRs, auditorias e planos
```

O tamanho e a divisão são adequados para o MVP, mas as fronteiras não estão totalmente consistentes: rotas concentram autenticação repetida, checagem de unicidade e montagem de formulário; serviços fazem consultas e commits que a arquitetura atribui a repositórios; e não existe uma camada explícita de dependências administrativas.

### 3.2 Inicialização

1. `app.core.config` carrega defaults e `.env` em import time.
2. `app.core.database` cria engine e `SessionLocal` também em import time.
3. `create_app()` rejeita somente o segredo padrão quando `APP_ENV` é exatamente `production` (`app/main.py:9-11`).
4. A aplicação registra `SessionMiddleware`, monta `/static` e inclui os routers público e administrativo (`app/main.py:20-31`).
5. No Compose, o processo web executa `alembic upgrade head` e depois inicia Uvicorn (`docker-compose.yml:26-28`).

### 3.3 Fluxo público

```text
GET público
  → rota FastAPI
  → Session SQLAlchemy quando necessária
  → repositório filtra visibility="published"
  → template Jinja2 SSR
  → filtro Markdown sanitiza conteúdo longo
```

Home, listagem e detalhe usam somente projetos publicados. O blog lê todos os arquivos `content/blog/*.md` e os trata como públicos. Sitemap combina páginas estáticas, projetos publicados e todos os posts Markdown.

### 3.4 Fluxo administrativo

```text
GET /admin/login
  → cria/recupera token CSRF na sessão assinada

POST /admin/login
  → valida CSRF
  → compara usuário e hash Argon2
  → limpa sessão e marca admin

CRUD de projeto
  → checa admin em cada rota
  → valida CSRF nas mutações
  → valida ProjectForm
  → rota checa slug
  → serviço sincroniza tecnologias e faz commit
```

O fluxo é funcionalmente simples. A repetição de controles por rota, no entanto, aumenta a probabilidade de omissão quando novas rotas forem adicionadas.

## 4. Inventário de rotas

### 4.1 Públicas

| Método | Caminho | Banco | Observação |
|---|---|---:|---|
| GET | `/` | sim | projetos em destaque e 2 posts |
| GET | `/sobre` | não | página estática SSR |
| GET | `/projetos` | sim | publicados; filtro parametrizado por tecnologia |
| GET | `/projetos/{slug}` | sim | `404` para ausente ou rascunho |
| GET | `/blog` | não | todos os Markdown da pasta |
| GET | `/blog/{slug}` | não | `404` específico quando ausente |
| GET | `/contato` | não | página estática SSR |
| GET | `/health` | sim | executa `SELECT 1` |
| GET | `/robots.txt` | não | permite rastreamento geral |
| GET | `/sitemap.xml` | sim | páginas estáticas, projetos publicados e posts |

Em desenvolvimento também existem `/docs` e `/openapi.json`. Em produção a UI `/docs` é removida, mas `/openapi.json` permanece porque `openapi_url` não é desabilitado.

### 4.2 Administrativas (`/admin`)

| Método | Caminho | Autenticação | CSRF |
|---|---|---:|---:|
| GET | `/login` | não | gera token |
| POST | `/login` | não | sim |
| POST | `/logout` | sessão | sim |
| GET | `` | sessão | n/a |
| GET | `/projetos/novo` | sessão | n/a |
| POST | `/projetos/novo` | sessão | sim |
| GET | `/projetos/{id}/editar` | sessão | n/a |
| POST | `/projetos/{id}/editar` | sessão | sim |
| POST | `/projetos/{id}/excluir` | sessão | sim |

O admin possui `noindex,nofollow` no template base e não entra no sitemap. As mutações usam POST e CSRF. Não foram encontradas rotas administrativas sem a checagem esperada.

## 5. Models, banco e migrations

### 5.1 Estado atual

- `Project`: conteúdo do estudo de caso, estado técnico, visibilidade, destaque, links, SEO e timestamps.
- `Technology`: nome e slug únicos.
- `project_technologies`: associação N:N com chave primária composta e `ON DELETE CASCADE`.
- Migration `20260728_01`: cria as três tabelas, índices e chaves; o downgrade remove tudo em ordem coerente.

### 5.2 Coerência model–migration

A inspeção não encontrou divergência estrutural imediata em nomes, tipos, nulabilidade, unicidade, índices ou FKs. `slug`, `status`, `visibility` e `featured` possuem os índices declarados pelos models. A PK composta e os cascades da associação também coincidem.

Há, contudo, fragilidades de integridade:

- estados válidos existem apenas no Pydantic; o banco não tem `CHECK` para `status` ou `visibility`;
- defaults e atualização de timestamps são apenas do ORM, sem `server_default`/trigger; inserts fora do ORM precisam preencher todos os campos não nulos;
- os três `HttpUrl` aceitos pelo schema podem exceder os 500 caracteres do banco, gerando erro de persistência não tratado como validação;
- `slugify()` pode gerar slug vazio ou colisões semânticas (`C`, `C++`, `C#`), e a constraint única transforma isso em erro genérico;
- tecnologias sem projetos permanecem após exclusões;
- consultas públicas comuns não têm índice composto para visibilidade/destaque/ordenação; isso só se torna relevante com volume real;
- não há teste de upgrade, downgrade ou detecção de drift entre metadata e migration.

## 6. Autenticação e segurança

### 6.1 Controles presentes

- hash Argon2 via `PasswordHash.recommended()`;
- comparação constante para username e verificação do hash (`app/core/security.py:15-20`);
- cookie de sessão `HttpOnly` por default do middleware, `SameSite=Lax`, expiração de 8 horas e `Secure` em produção (`app/main.py:20-27`);
- limpeza da sessão no login e logout;
- token CSRF aleatório por sessão e comparação constante;
- CSRF no login, logout, criação, edição e exclusão;
- autoescape do Jinja2 para campos comuns;
- Markdown convertido e sanitizado com allowlist de tags, atributos e protocolos antes de virar `Markup` (`app/web.py:14-46`);
- rascunhos de projeto filtrados nas consultas públicas;
- `.env`, bancos locais e caches ignorados; `.env` também excluído do build Docker;
- processo do container executado como usuário `app` não root.

### 6.2 Lacunas

- login sem rate limit, atraso progressivo, lockout, auditoria ou alerta;
- configuração de produção pode falhar aberta por grafia de ambiente (`prod`, `Production `) e aceita segredo fraco desde que diferente do default;
- `ADMIN_PASSWORD_HASH`, PostgreSQL e `SITE_URL` não são obrigatórios/validados na inicialização de produção;
- hash Argon2 inválido pode virar erro 500 no login em vez de falha de configuração antecipada;
- não há `TrustedHostMiddleware`, política explícita de hosts/proxy nem headers como CSP, HSTS, `X-Content-Type-Options`, `Referrer-Policy` e proteção de framing; parte pode pertencer ao reverse proxy, mas não há configuração de proxy versionada;
- páginas administrativas autenticadas não declaram `Cache-Control: no-store`;
- cookies assinados são stateless e não permitem revogar no servidor uma sessão roubada antes de expirar;
- OpenAPI permanece público em produção;
- exclusão administrativa é definitiva e não produz trilha de auditoria;
- não há logs de login, mutações ou request ID.

Não foi encontrada chamada a provedor de LLM, segredo no cliente, upload inseguro ou renderização direta de Markdown não sanitizado.

## 7. Testes e qualidade

### 7.1 Cobertura existente

Os testes verificam:

- health check;
- rascunho fora do detalhe e listagem pública;
- projeto publicado visível no detalhe e home;
- redirecionamento do admin sem login;
- login e criação de projeto com tecnologias;
- recusa de criação sem CSRF.

É uma smoke suite útil, mas não cobre login inválido, atributos do cookie, logout, edição, exclusão, autorização em cada mutação, CSRF em cada endpoint, filtro de tecnologia, sitemap, Markdown malicioso, validação de formulário, conflito de slug, erros de banco, headers, configuração de produção ou migrations.

### 7.2 Segurança da suíte

`tests/conftest.py:12-16` chama `Base.metadata.drop_all()` antes e depois de cada teste usando o `engine` global. Esse engine é construído de `settings.database_url` em import time. Não existe fixture que substitua obrigatoriamente a URL antes do import, nem trava por nome/host/ambiente. Esse é o principal bloqueador da base.

Além do risco destrutivo, criar schema com `Base.metadata.create_all()` faz os testes ignorarem a migration Alembic e pode permitir drift silencioso.

### 7.3 Resultado das validações

| Validação | Resultado |
|---|---|
| Parsing AST de 27 arquivos | passou |
| Inventário estático de rotas | passou: 10 públicas, 9 admin |
| `pytest` | não executado; dependência ausente e fixture insegura |
| `ruff check` | não executado; Ruff ausente |
| Alembic upgrade/downgrade | não executado; Alembic ausente e nenhum DB foi alterado |
| Build Docker | não executado; instalaria dependências |
| `docker compose config --quiet` | bloqueado pela ausência esperada de `.env` |

## 8. Docker, configuração e operação

### Pontos positivos

- Python 3.12 compatível com a documentação;
- usuário não root;
- `.dockerignore` exclui Git, `.env`, virtualenv, testes, bytecode e bancos;
- PostgreSQL tem volume e health check;
- web aguarda o health check do banco;
- migrations são aplicadas antes da aplicação;
- docs interativas são removidas em produção.

### Riscos operacionais

- `python:3.12-slim`, `postgres:16-alpine` e dependências por intervalos não são fixados por digest/lock, reduzindo reprodutibilidade;
- migration acoplada ao startup de cada réplica pode causar disputa em escala e mistura deploy com mudança de schema;
- não há health check do serviço web, política de restart ou teste de readiness externo;
- `POSTGRES_PASSWORD` tem fallback fraco em Compose;
- interpolar a senha diretamente na URL pode falhar com caracteres reservados sem URL encoding;
- `--proxy-headers` é ativado sem uma política versionada de proxies confiáveis;
- não há configuração versionada de reverse proxy/HTTPS, logging, métricas, alertas, backup ou rollback, todos exigidos pela documentação de deploy;
- o app usa SQLite por default e aceita isso em produção; PostgreSQL é arquitetura aprovada, portanto produção deveria rejeitar backend diferente;
- settings e engine globais em import time dificultam sobrescrita segura por teste e validação por ambiente.

## 9. SEO e conteúdo

### Presente

- HTML público SSR e semântico;
- títulos e descriptions básicos;
- Open Graph básico;
- sitemap somente com projetos `published` e posts existentes;
- `robots.txt` e status 404 real nos detalhes de projeto/blog;
- admin marcado `noindex,nofollow` e excluído do sitemap.

### Lacunas

- sem canonical, `hreflang`, URLs localizadas, RSS, JSON-LD, breadcrumbs, Open Graph image ou redirects;
- mudança de slug publicado quebra a URL e exclusão devolve 404 sem política 301/404/410;
- qualquer `.md` colocado em `content/blog` é publicado e incluído no sitemap, sem draft/noindex;
- rotas inexistentes fora de projeto/blog recebem 404 JSON padrão, não a página SSR customizada;
- `SITE_URL` é string sem validação/normalização e o XML é concatenado manualmente;
- `robots.txt` permite `/admin`, `/docs` e `/openapi.json`; isso não é falha de segurança, mas é higiene de crawl incompleta.

Canonical, i18n e SEO avançado estão corretamente planejados para v0.7/v0.8. A exceção de maior impacto imediato é preservar slugs já publicados, regra já explícita em `docs/CMS.md` e `docs/SEO.md`.

## 10. Aderência à arquitetura documentada

| Decisão/requisito | Estado | Evidência/comentário |
|---|---|---|
| Monólito modular | **parcialmente conforme** | módulos claros; fronteiras rota/serviço/repositório ainda vazam |
| FastAPI + Jinja2 SSR | **conforme** | público e admin renderizados no servidor |
| HTMX pontual | **não utilizado** | não é necessário ao comportamento atual; não constitui defeito |
| PostgreSQL principal | **parcialmente conforme** | Compose usa PostgreSQL; default local é SQLite e produção não o rejeita |
| SQLAlchemy 2 + Alembic | **conforme estático** | model e migration coerentes; falta validação executada |
| Sessão segura + Argon2 + CSRF | **parcialmente conforme** | controles básicos corretos; falta hardening e isolamento operacional |
| Rotas/serviços/repositórios | **parcialmente conforme** | regra e persistência distribuídas entre camadas |
| Conteúdo público SSR | **conforme** | projetos e Markdown renderizados no servidor |
| Rascunhos fora do público/sitemap | **conforme para projetos** | blog não possui estado editorial |
| Slug publicado preservado | **não conforme** | edição sobrescreve slug sem redirect |
| PT-BR/en independentes | **planejado, não implementado** | coerente com roadmap v0.8 |
| Identidade, papéis e convites | **planejado, não implementado** | single-admin é escopo original; roadmap v0.9 |
| Labs separados | **conforme** | não há carga de Lab incorporada no CMS |
| Browser sem acesso direto a LLM | **conforme** | nenhuma integração LLM presente |
| Quotas/auditoria de Labs | **planejado, não implementado** | roadmap v1.0 |
| Observabilidade e rollback | **não conforme para produção** | documentação existe, implementação/configuração não |

## 11. Achados priorizados

### A-01 — Crítico — testes podem apagar banco não isolado

**Evidência:** `tests/conftest.py:12-16` usa `drop_all()` no engine global; `app/core/database.py` constrói esse engine da configuração ativa.
**Impacto:** perda de tabelas e conteúdo se `pytest` for executado com `DATABASE_URL` local, staging ou produção.
**Recomendação:** antes de executar a suíte, criar configuração de testes anterior aos imports, usar banco descartável dedicado e adicionar uma trava que aborte salvo ambiente/URL explicitamente de teste. Nunca aceitar fallback para banco real.

### A-02 — Alto — login exposto a força bruta sem observabilidade

**Evidência:** `app/routes/admin.py:119-140` valida credenciais diretamente, sem rate limit ou log. O próprio README reconhece a pendência.
**Impacto:** tentativas ilimitadas contra a única conta administrativa, sem detecção.
**Recomendação:** rate limit por IP e identidade, backoff, logging sem senha, request ID e alerta; manter mensagem genérica em produção.

### A-03 — Alto — validação de produção insuficiente

**Evidência:** apenas `APP_ENV.lower() == "production"` e igualdade com um único segredo default são checados (`app/core/config.py:26-32`, `app/main.py:9-11`).
**Impacto:** `APP_ENV=prod`, segredo curto, hash vazio/inválido, SQLite ou `SITE_URL` insegura podem iniciar uma implantação aparentemente produtiva.
**Recomendação:** enum de ambientes e validação fail-fast de segredo forte, hash Argon2, PostgreSQL, URL HTTPS e variáveis obrigatórias.

### A-04 — Alto — URLs publicadas e exclusões não têm política

**Evidência:** atualização sobrescreve `slug` (`app/services/projects.py:50-55`) e exclusão é hard delete (`app/services/projects.py:60-62`); não existe model `Redirect`.
**Impacto:** links externos, indexação e histórico quebram; exclusão acidental é imediatamente pública e irreversível pelo app.
**Recomendação:** bloquear mudança até existir redirect 301 transacional; definir 301/404/410 e retenção/soft delete conforme o estado publicado.

### A-05 — Médio — OpenAPI continua público em produção

**Evidência:** `docs_url` é removido, mas `openapi_url` permanece no default (`app/main.py:13-19`).
**Impacto:** enumeração desnecessária da superfície administrativa. Não substitui autenticação, mas contraria a intenção de docs apenas locais.
**Recomendação:** desabilitar também `openapi_url` em produção ou proteger explicitamente a documentação.

### A-06 — Médio — hardening HTTP e confiança de proxy não estão definidos

**Evidência:** somente `SessionMiddleware` está configurado; Docker inicia com `--proxy-headers`; não há proxy versionado.
**Impacto:** comportamento de host/esquema e headers depende de infraestrutura externa não auditável neste repositório.
**Recomendação:** documentar fronteira de TLS/proxy, allowlist de proxies/hosts e divisão explícita dos headers de segurança entre proxy e app.

### A-07 — Médio — blog não tem estado editorial

**Evidência:** `load_posts()` publica todo `content/blog/*.md` e sitemap repete a lista (`app/web.py:61-77`, `app/routes/public.py:136-151`).
**Impacto:** um rascunho commitado nessa pasta fica público e indexável.
**Recomendação:** até o CMS de blog, exigir frontmatter de publicação com default privado ou separar diretórios de draft/publicado.

### A-08 — Médio — suíte ignora migrations e cobre poucos fluxos críticos

**Evidência:** schema de teste vem de `metadata.create_all()`; não há teste Alembic. Apenas 6 testes existem.
**Impacto:** drift, downgrade quebrado e regressões administrativas/SEO podem passar despercebidos.
**Recomendação:** provisionar schema de teste por Alembic e adicionar matriz de segurança, CRUD, sitemap, Markdown e configuração.

### A-09 — Médio — deploy não é plenamente reproduzível nem escalável

**Evidência:** tags e dependências por intervalo; migration dentro do comando web; ausência de health check web.
**Impacto:** builds variáveis, rollout acoplado e possíveis disputas entre réplicas.
**Recomendação:** lock/hashes ou processo equivalente, imagens imutáveis, job único de migration e readiness/health check do web.

### A-10 — Médio — invariantes dependem apenas da aplicação

**Evidência:** sem checks de status/visibilidade, defaults server-side ou limites de URL alinhados; slug de tecnologia pode colidir.
**Impacto:** dados inválidos via scripts/concorrência e falhas 500 em persistência.
**Recomendação:** formalizar invariantes e, quando alterar schema, criar migration específica com testes de upgrade/downgrade.

### A-11 — Médio — responsabilidades atravessam camadas

**Evidência:** rota checa unicidade; serviço consulta Technology e faz commits; autorização é repetida em cada handler.
**Impacto:** regras difíceis de testar e maior risco de omitir controles em novas rotas.
**Recomendação:** sem refatoração ampla, criar dependência administrativa reutilizável e consolidar a unidade transacional/regra de publicação no serviço, com persistência no repositório.

### A-12 — Baixo — health check mistura readiness e liveness

**Evidência:** `/health` sempre consulta o banco e deixa a exceção subir.
**Impacto:** banco indisponível torna o único health endpoint 500; orquestrador pode reiniciar app saudável que apenas perdeu dependência.
**Recomendação:** separar liveness simples de readiness com banco e resposta 503 controlada.

### A-13 — Baixo — SEO técnico ainda é mínimo

**Evidência:** ausência de canonical, JSON-LD, RSS, breadcrumbs e i18n.
**Impacto:** capacidade orgânica limitada, sem exposição privada identificada.
**Recomendação:** manter no roadmap v0.7/v0.8; antecipar apenas estabilidade de slug e controle de publicação.

### A-14 — Baixo — leitura de blog é síncrona e repetida

**Evidência:** arquivos e frontmatter são lidos/ordenados a cada request de home, blog e sitemap.
**Impacto:** I/O e parsing redundantes; irrelevante no volume atual, mas mensurável no futuro.
**Recomendação:** só otimizar após medição; cache invalidado por deploy é suficiente para conteúdo versionado.

### A-15 — Baixo — tratamento de erros é inconsistente

**Evidência:** há template 404 nas rotas de detalhe, mas não handler global; 403/500 usam respostas padrão.
**Impacto:** UX inconsistente e pouca observabilidade.
**Recomendação:** handlers SSR para erros públicos, preservando status reais, e logs estruturados para 5xx.

## 12. Dívida técnica e pontos reutilizáveis

### Reutilizar

- app factory pequena e routers separados;
- `ProjectForm` como fronteira de validação;
- consultas públicas que filtram publicação no repositório;
- allowlist de Markdown centralizada;
- CSRF centralizado em funções de segurança;
- model e migration inicial simples e legíveis;
- container não root e health check do PostgreSQL;
- ADRs e roadmap que impedem expansão prematura.

### Corrigir antes de expandir

- isolamento destrutivo dos testes;
- configuração fail-fast por ambiente;
- rate limit e auditoria do login;
- estabilidade de slug/exclusão publicada;
- testes por Alembic;
- dependência reutilizável de admin e limites transacionais;
- contrato de proxy, headers e observabilidade.

### Manter fora da estabilização v0.2.1

- CMS genérico, editor visual e uploads;
- múltiplos usuários, RBAC, convites e portal;
- traduções e URLs localizadas;
- execução ou gateway de Labs;
- quotas e custos de LLM;
- refatoração ampla sem evidência adicional.

## 13. Plano recomendado de estabilização v0.2.1

### P0 — impedir dano e validar ambiente

1. Isolar completamente o banco de testes e adicionar trava anti-produção antes de qualquer `drop_all`.
2. Fazer produção falhar no startup com ambiente inválido, segredo/hash ausente ou fraco, banco não PostgreSQL e URL pública inválida.
3. Criar ambiente reproduzível permitido pelo projeto e então executar lint, testes e migration em PostgreSQL descartável.

**Testes mínimos:** prova de que a suíte recusa URL não dedicada; startup negativo para cada variável; Alembic `upgrade head` e `downgrade base` em banco descartável.

### P1 — segurança e integridade de publicação

1. Adicionar rate limit, logs seguros e request ID ao login.
2. Centralizar dependência de autenticação admin e verificar todas as mutações.
3. Impedir alteração destrutiva de slug publicado até redirects existirem; definir política de exclusão.
4. Alinhar invariantes do schema e tratamento de erros de persistência.
5. Fechar OpenAPI em produção e definir proxy/hosts/headers/cache do admin.

**Testes mínimos:** login válido/inválido/limitado, cookies, CSRF em todos os POSTs, acesso negado, slug publicado, exclusão, headers e OpenAPI por ambiente.

### P2 — operação e cobertura

1. Separar migration do processo web e adicionar readiness/liveness.
2. Tornar builds imutáveis/reproduzíveis e eliminar fallback fraco de senha.
3. Cobrir sitemap, drafts, filtro, Markdown/XSS, erros e drift model–migration.
4. Documentar backup, restore, rollback e configuração do reverse proxy.

### P3 — somente depois da estabilização

Executar o roadmap aprovado sem antecipar features: fundação modular comprovadamente necessária, Blog CMS, workflow editorial, projetos, SEO, i18n, identidade/Labs e gateway.

## 14. Decisão final

A base v0.2 é **aproveitável e adequada como fundação de desenvolvimento**, com bons controles iniciais de publicação, CSRF, sessão e sanitização. Não há justificativa para reescrita ou migração prematura para microsserviços.

Ela é **condicionalmente reprovada para produção no estado atual** por risco destrutivo da suíte, proteção insuficiente do login/configuração e ausência de garantia para URLs publicadas. A sequência correta é estabilizar esses pontos, validar em PostgreSQL descartável e só então retomar o roadmap.

Nenhuma migration, dependência, commit ou alteração na aplicação foi realizada durante esta auditoria.

# Auditoria técnica pós-estabilização v0.2.1

> **Status: snapshot histórico, substituído quanto à classificação atual.** A classificação A e
> os achados R1, R2 e R3 deste relatório motivaram remediações posteriores. A
> confirmação independente mais recente classificou os três como resolvidos e a
> base como **B — pronta para evoluir, mas não para produção**. Consulte
> [TECHNICAL_AUDIT_REMEDIATION_CONFIRMATION_V0.2.1.md](TECHNICAL_AUDIT_REMEDIATION_CONFIRMATION_V0.2.1.md).

**Data da revisão:** 8 de agosto de 2026

**Base auditada:** `master` em `291a868` (`security: harden http and production exposure`)

**Escopo:** verificação independente das tarefas P0.1–P1.5 e reavaliação da base atual

**Modo:** inspeção somente leitura; a criação deste relatório é a única alteração realizada

## Resumo técnico

A estabilização melhorou materialmente a base: o ambiente oficial de verificação é isolado e descartável; `make verify` executa Ruff, testes e o ciclo Alembic; a autenticação administrativa foi centralizada; brute force recebeu limitação local; slugs tornaram-se imutáveis; hard delete foi bloqueado; e o caminho HTTP normal ganhou TrustedHost, CSP, headers, HSTS condicionado a HTTPS e fechamento de OpenAPI em produção.

Mesmo assim, a conclusão independente é **A — NÃO PRONTO PARA EVOLUIR**. Há duas lacunas altas dentro dos próprios gates de estabilização:

1. a guarda de banco de testes ainda aceita qualquer host PostgreSQL cujo nome do banco termine em `_test`; combinada a `drop_all/create_all`, uma `TEST_DATABASE_URL` explícita e equivocada pode executar DDL em um servidor remoto;
2. `staging` aceita o segredo de sessão público do código, o usuário administrativo padrão e cookie sem `Secure`; foi reproduzido acesso autenticado ao CMS com cookie forjado, sem conhecer senha.

Também foi confirmado que a auditoria de login existe como `LogRecord`, mas normalmente não é emitida: o logger da aplicação não tem configuração própria e herda nível efetivo `WARNING`. Portanto P1.1 não entrega observabilidade operacional no runtime padrão.

O resultado verde de `make verify` é importante, mas não invalida esses achados: o fluxo oficial protege o banco por topologia Docker, enquanto o helper de guarda continua permissivo fora desse fluxo; e a matriz de testes não cobre a política de `staging` nem o cookie forjado. A base pode chegar à categoria **B — pronta para evoluir, mas não para produção** após as correções obrigatórias listadas ao final. Produção real ainda exige trabalho operacional P2.

### Síntese dos achados atuais

| Severidade | Quantidade | Síntese |
|---|---:|---|
| Crítica | 0 | Nenhum bypass de produção, segredo real exposto ou dano executado foi encontrado. |
| Alta | 2 | Guarda de banco remoto incompleta; autenticação de staging contornável com defaults. |
| Média | 8 | Logging inefetivo, validações parciais, limites por processo, headers ausentes em 500, lacunas de testes/migrations, operação, invariantes e publicação do blog. |
| Baixa | 5 | Cobertura preventiva, cookies/revogação, erros, SEO e inconsistências documentais. |

## Escopo, fontes e critérios

Foram lidos integralmente:

- `AGENTS.md` e `README.md`;
- `docs/SECURITY.md`, `docs/TESTING.md`, `docs/DEPLOYMENT.md` e `docs/CMS.md`;
- `docs/audits/TECHNICAL_AUDIT_V0.2.md`;
- `docs/plans/STABILIZATION_PLAN_V0.2.1.md`;
- documentação complementar de arquitetura, escopo, SEO, roadmap e `PROJECT_BRIEF.md`.

Foram inspecionados `app/core/`, `app/routes/`, `app/services/`, `app/repositories/`, `app/models/`, `app/schemas/`, `tests/`, `migrations/`, templates, conteúdo, Dockerfiles, arquivos Compose, Makefile, locks, configuração de ambiente e histórico Git das mudanças de estabilização.

As classificações da comparação histórica significam:

- **RESOLVIDO:** o risco original foi eliminado no escopo atual e há evidência proporcional;
- **PARCIALMENTE RESOLVIDO:** houve melhoria, mas parte material do risco ou critério de aceite permanece;
- **NÃO RESOLVIDO:** a condição original ainda existe sem mitigação suficiente;
- **SUBSTITUÍDO POR NOVO RISCO:** a causa original mudou, porém apareceu outra rota de risco equivalente ou relevante.

Não foram usados banco de desenvolvimento, staging ou produção. Provas dinâmicas sem banco foram executadas com rede desabilitada. Não houve pentest externo, scanner de CVEs, validação de proxy real, restauração de backup ou teste de carga; conclusões sobre esses itens são limitadas ao repositório e ao runtime local controlado.

## A estabilização não encerrou dois gates de segurança

### A guarda ainda permite DDL contra um PostgreSQL remoto

**Resultado:** alto; bloqueia o encerramento de P0.

`tests/support/database.py` exige `APP_ENV=test`, backend admitido e, em PostgreSQL, nome terminado em `_test`. Entretanto, não exige host ou credencial explicitamente permitidos e compara a URL normal com a URL de testes por texto, não pela identidade canônica do destino. `tests/conftest.py` continua executando `Base.metadata.drop_all()` e `create_all()` antes/depois dos testes de banco.

Uma prova puramente local, sem abrir conexão, demonstrou que a guarda aceita:

- `postgresql+psycopg://tester:discardable@production.example/portfolio_test`;
- uma representação alternativa do mesmo alvo configurado como banco normal, por diferença de driver/porta implícita.

O Compose oficial reduz fortemente o risco: usa host interno fixo, rede interna, `tmpfs`, container web read-only e sem publicação da porta do PostgreSQL. Isso protege `make verify`, mas não corrige `make test` no host nem uma execução manual com `TEST_DATABASE_URL` explícita. O plano exigia allowlist de host e rejeição de hosts/credenciais protegidos; esse critério não foi atendido.

**Implicação:** nenhuma rotina destrutiva foi executada contra banco normal nesta auditoria, mas a defesa fail-closed ainda depende da topologia do caminho oficial, não da guarda independente prometida.

### Staging aceita um cookie administrativo forjado

**Resultado:** alto; bloqueia o encerramento de P0.3.

`app/core/config.py` aplica a matriz forte apenas quando `APP_ENV=production`. Em `staging`, permanecem possíveis:

- `SESSION_SECRET=development-only-change-me`, público no código;
- `ADMIN_USERNAME=rennam`;
- ausência de hash administrativo obrigatório;
- cookie de sessão sem `Secure`.

`SessionMiddleware` usa esse segredo para assinar o cookie, e `is_admin()` autoriza quando o estado assinado contém `admin` igual ao username configurado. Em imagem já construída, com `--network none`, um cookie assinado com o segredo padrão e `{"admin":"rennam"}` recebeu **HTTP 200** em `GET /admin/projetos/novo` sob configuração `staging` válida para o restante da aplicação.

Isso não demonstra bypass de `production`, cuja inicialização exige segredo e demais valores explícitos. Demonstra, porém, que um staging implantado com defaults — ambiente reconhecido pela própria configuração — não possui fronteira administrativa confiável. O plano reservava defaults convenientes apenas a development.

**Implicação:** staging deve ser tratado como ambiente implantável e fail-closed, ou ser tecnicamente impedido de expor o CMS até receber configuração forte explícita.

## Comparação com a auditoria v0.2

| ID | Achado original | Estado pós-estabilização | Evidência e risco restante |
|---|---|---|---|
| A-01 | Testes podem apagar banco não isolado | **SUBSTITUÍDO POR NOVO RISCO** | A herança direta de `DATABASE_URL` foi removida e o Compose oficial é efêmero. A nova guarda, porém, aceita PostgreSQL remoto arbitrário terminado em `_test`; `drop_all/create_all` permanece. |
| A-02 | Login exposto a força bruta sem observabilidade | **PARCIALMENTE RESOLVIDO** | Limiter bounded e thread-safe funciona em processo único, mas logs `INFO` são suprimidos no runtime padrão e múltiplos processos fragmentam contadores. |
| A-03 | Validação de produção insuficiente | **PARCIALMENTE RESOLVIDO** | Produção ganhou enum, segredo mínimo, hash, PostgreSQL, HTTPS e hosts explícitos. Staging permanece contornável com defaults; Argon2 e outros valores têm validação superficial. |
| A-04 | URLs publicadas e exclusões não têm política | **RESOLVIDO** | A política temporária é explícita: slug imutável para todo projeto e hard delete negado server-side; UI e testes refletem a decisão. |
| A-05 | OpenAPI público em produção | **RESOLVIDO** | `/docs`, `/redoc` e `/openapi.json` não são expostos em produção/staging; development/test preservam documentação deliberadamente. |
| A-06 | Hardening HTTP e proxy não definidos | **PARCIALMENTE RESOLVIDO** | TrustedHost, CSP, headers, HSTS em HTTPS, no-store no admin e validação de proxy existem. Respostas 500 não tratadas podem escapar sem esses headers, e a imposição do proxy continua externa ao repositório. |
| A-07 | Blog não tem estado editorial | **NÃO RESOLVIDO** | Todo arquivo Markdown em `content/blog` é tratado como público e entra no sitemap; não há estado de publicação/default-private. |
| A-08 | Suíte ignora migrations e cobre poucos fluxos críticos | **PARCIALMENTE RESOLVIDO** | `make verify` testa upgrade/check/downgrade/upgrade em PostgreSQL descartável e P1 ganhou boa cobertura. A suíte funcional ainda cria schema por metadata e não roda a aplicação sobre schema provisionado por Alembic. |
| A-09 | Deploy não plenamente reproduzível nem escalável | **PARCIALMENTE RESOLVIDO** | Verificação isolada e dependências de teste exatas melhoraram. Imagens/tags e dependências de runtime flutuam; migration segue no startup web; faltam healthcheck web e controles operacionais. |
| A-10 | Invariantes dependem apenas da aplicação | **NÃO RESOLVIDO** | Status/visibility, limites reais de URL e timestamps continuam sem constraints/defaults equivalentes no banco. |
| A-11 | Responsabilidades atravessam camadas | **PARCIALMENTE RESOLVIDO** | Auth foi centralizada e não foram detectados ciclos. Rotas ainda orquestram validação/unicidade, e serviços consultam/committam ORM apesar da separação documental de repositório. |
| A-12 | Health mistura readiness e liveness | **NÃO RESOLVIDO** | `/health` consulta banco sempre, transforma falha em 500 e não há liveness/readiness separados nem healthcheck do container web. |
| A-13 | SEO técnico mínimo | **PARCIALMENTE RESOLVIDO** | Estabilidade de slug melhorou. Permanecem canonical/hreflang, metadata social específica, dados estruturados e política editorial do sitemap. |
| A-14 | Blog lido de forma síncrona e repetida | **NÃO RESOLVIDO** | Arquivos continuam sendo lidos/renderizados sincronicamente por request; aceitável no volume atual, mas sem cache/invalidação. |
| A-15 | Tratamento de erros inconsistente | **NÃO RESOLVIDO** | Há 404 customizado em detalhes de conteúdo, mas erros globais/infra continuam respostas padrão; falha de health vira 500 e 500 não recebe todos os headers. |

## Matriz independente P0/P1

| Tarefa | Classificação | O que foi comprovado | Lacuna que impede resolução plena |
|---|---|---|---|
| P0.1 — isolamento do banco de testes | **RESOLVIDO** | Configuração de teste é antecipada; Compose usa PostgreSQL dedicado, rede interna e `tmpfs`; banco normal não foi acessado. | Nenhuma lacuna própria material; a defesa complementar de P0.2 é que falha. |
| P0.2 — guarda anti-banco real | **PARCIALMENTE RESOLVIDO** | Rejeita ambiente errado, backends não aceitos, nomes protegidos e PostgreSQL sem sufixo `_test`. | Não restringe host/credencial/cluster e não canonicaliza a identidade do destino. |
| P0.3 — configuração fail-fast | **PARCIALMENTE RESOLVIDO** | Produção exige valores explícitos, HTTPS, PostgreSQL e hosts/proxy definidos; erros não incluem os valores secretos. | Staging aceita defaults forjáveis; Argon2 é validado só por regex; segredo é avaliado principalmente por comprimento. |
| P0.4 — verificação reproduzível | **PARCIALMENTE RESOLVIDO** | Um comando executa Ruff, duas fases de testes e ciclo Alembic descartável com sucesso. | Imagens base usam tags móveis, lock não usa hashes e dependências da imagem da aplicação são ranges. |
| P1.1 — rate limiting e auditoria | **PARCIALMENTE RESOLVIDO** | Limiter local é bounded/thread-safe, tem fail-closed no handler e testes de janela/buckets/proxy. | Eventos `INFO` não saem no logging padrão; não há correlation ID; estado é por processo. |
| P1.2 — autenticação reutilizável | **RESOLVIDO** | `require_admin` está em `app/core/security.py`; todas as rotas administrativas atuais, exceto login, a usam; login segue público e logout protegido/funcional. | O teste de inventário não detectaria necessariamente uma futura rota admin sem a dependência. |
| P1.3 — slug imutável | **RESOLVIDO** | Serviço rejeita mudança antes de atualizar campos; formulário exibe slug readonly e testes cobrem request manual, atomicidade e URL original. | Renomeação segura com histórico/redirect continua corretamente fora do escopo. |
| P1.4 — hard delete bloqueado | **RESOLVIDO** | Serviço sempre lança erro controlado; endpoint mantém auth/CSRF e retorna 409; UI informa indisponibilidade; registros publicados/draft permanecem. | Arquivamento/restore continua corretamente fora do escopo. |
| P1.5 — HTTP/OpenAPI/proxy | **PARCIALMENTE RESOLVIDO** | Caminho normal tem hosts confiáveis, CSP compatível, headers, admin no-store, HSTS só em HTTPS, docs fechadas e testes do middleware Uvicorn. | 500 não tratado escapa dos headers da aplicação; reverse proxy/isolamento de acesso direto não é versionado no repo. |

## Achados atuais por severidade

### Altos

#### F-01 — a guarda anti-produção não valida o destino permitido

**Evidência:** `tests/support/database.py` valida nome/esquema, mas não host/usuário/cluster; fixtures fazem DDL. Provas estáticas aceitam host chamado `production.example` e alias do alvo normal.

**Impacto:** perda de dados em banco remoto explicitamente mal configurado.

**Ação:** allowlist explícita e identidade canônica do destino antes de qualquer DDL.

#### F-02 — staging permite forjar sessão administrativa com defaults públicos

**Evidência:** política forte é exclusiva de production; cookie forjado obteve HTTP 200 em rota protegida sob staging.

**Impacto:** bypass completo do login em staging exposto.

**Ação:** aplicar configuração implantável fail-closed a staging e testar cookie forjado negativamente.

### Médios

#### F-03 — eventos de login não têm emissão operacional garantida

`audit_login()` usa `logger.info(..., extra=...)`, mas não existe handler/nível/formatter da aplicação. No runtime inspecionado, root estava em `WARNING`, `rennam.admin_auth.isEnabledFor(INFO)` era falso e o logger não tinha handlers. `caplog` comprova o objeto, não stdout estruturado. Não há senha/username no evento, o que é positivo.

#### F-04 — validação de configuração permanece sintática em pontos sensíveis

A validação Argon2 é regex e aceitou parâmetros `m=0,t=0,p=0` e salt/digest mínimos. Nos exemplos executados, o backend retornou falha de verificação; não foi demonstrado bypass nem 500, mas o fail-fast e a força mínima não estão garantidos. `SESSION_SECRET` aceita baixa entropia repetitiva desde que tenha 32 caracteres, `DATABASE_URL` valida principalmente o esquema e `SITE_URL` aceita path embora o app suponha raiz.

#### F-05 — rate limit e Argon2 não escalam com workers/réplicas

O limiter vive em memória do processo. Dois workers ou réplicas mantêm buckets independentes. O Docker não fixa explicitamente um worker, e Argon2 síncrono roda dentro do handler assíncrono, podendo bloquear o event loop sob carga. O controle é adequado somente ao baseline atual de uma instância/um processo, que precisa ser explicitado operacionalmente.

#### F-06 — exceção não tratada perde headers de segurança

O middleware de headers adicionado pela aplicação fica dentro do `ServerErrorMiddleware` do Starlette. Prova controlada retornou `500 Internal Server Error` sem stack trace público, porém sem `X-Content-Type-Options` e sem CSP. HSTS/no-store têm o mesmo risco. O proxy deve manter defesa em profundidade, e o app precisa de teste para esse caminho.

#### F-07 — suíte funcional não valida a aplicação sobre schema Alembic

O ciclo Alembic isolado passou e `alembic check` não encontrou operações novas. Porém fixtures funcionais usam `Base.metadata.create_all()`, então compatibilidade app↔schema migrado é verificada apenas indiretamente. Faltam testes de falha de banco/readiness, sitemap/robots/filtros, sanitização Markdown/XSS, cookies reais e logging runtime.

#### F-08 — baseline de deploy ainda não é reproduzível ou operável o suficiente

`python:3.12-slim` e `postgres:16-alpine` são tags móveis; o lock de testes não contém hashes; o Dockerfile da aplicação instala ranges; migration roda junto ao startup web; não há healthcheck/restart do web, job de migration, proxy versionado, runbook testado de backup/restore/rollback, métricas ou alertas. O Compose normal é corretamente documentado como desenvolvimento, não como topologia de produção.

#### F-09 — invariantes de domínio ainda podem divergir no banco

Model e migration atuais estão coerentes, mas `status`/`visibility` dependem de Pydantic, URLs validadas podem exceder `String(500)`, timestamps/defaults são apenas ORM e slug de tecnologia pode ficar vazio/colidir. Uma URL longa pode gerar erro de persistência não tratado pelo bloco que captura somente `IntegrityError`.

#### F-10 — qualquer Markdown do diretório do blog é publicado

Não há estado editorial, data de publicação efetiva ou default-private. Adicionar um rascunho a `content/blog` o torna listável, acessível e incluído no sitemap. Isso não bloqueia o CMS de projetos hoje, mas bloqueia expansão segura do fluxo editorial do blog.

### Baixos

#### F-11 — o teste de cobertura de `require_admin` não é preventivo

O snapshot é construído a partir das rotas que já contêm a dependência. Uma nova rota `/admin` sem proteção pode não entrar no conjunto e o teste ainda passar. O inventário deve partir de todas as rotas admin e excluir somente o login público de forma explícita.

#### F-12 — contrato de sessão tem cobertura incompleta e revogação limitada

O cookie de produção é `Secure`, SameSite Lax e HttpOnly pelo padrão do middleware, com duração de oito horas, mas faltam asserts de `Set-Cookie`, expiração e cenários reais entre ambientes. Sessões são assinadas e stateless: logout remove o cookie do cliente, mas uma cópia roubada permanece válida até expirar. É dívida aceitável apenas enquanto risco/escopo permanecerem pequenos.

#### F-13 — health e erros não oferecem diagnóstico operacional consistente

`/health` mistura processo e banco, deixa falha do banco virar 500 e não há healthcheck web. Páginas 404 específicas existem, mas 403/404/500 globais são respostas padrão. `debug` não é habilitado em produção e nenhum stack trace foi observado, o que evita exposição direta.

#### F-14 — SEO técnico e conteúdo continuam mínimos

SSR, robots e sitemap existem, e slugs de projeto são estáveis. Ainda faltam canonical/hreflang, JSON-LD, RSS/breadcrumbs e metadata social específica para projeto/post. `robots.txt` não é controle de acesso e não substitui o fechamento já feito de admin/docs.

#### F-15 — documentação e versão apresentam divergências

`PROJECT_BRIEF.md` ainda descreve escopo admin incompatível com o CMS atual; o plano permanece textualizado como “proposto”; partes de segurança misturam estado atual com controles futuros; e a versão FastAPI continua `0.2.0`. São problemas de confiança documental, não vulnerabilidades diretas.

## Reavaliação de segurança

### Controles confirmados

- Todas as rotas administrativas atuais, exceto `GET/POST /admin/login`, recebem a dependência `require_admin`: dashboard, criação, edição, exclusão e logout.
- Todos os POSTs mutáveis do admin validam CSRF, inclusive login e logout. O token é ligado à sessão e comparado de forma constante.
- Login permanece público; logout permanece protegido e remove o estado de sessão do navegador.
- Redirecionamentos administrativos usam destinos fixos; não foi encontrado open redirect.
- Consultas usam expressões SQLAlchemy parametrizadas; não foi encontrada concatenação SQL vulnerável.
- Jinja mantém autoescape. Markdown passa por Bleach com allowlist restrita; scripts, estilos, mídia/iframe e HTML perigoso não são permitidos.
- Não foi encontrada API de arquivo/path controlada externamente que ofereça traversal no estado atual.
- A CSP atual é compatível com templates/assets: CSS local, sem JavaScript, handlers inline, estilos inline ou subrecursos remotos. Swagger é deliberadamente excluído da CSP estrita apenas em development/test.
- TrustedHost e o middleware de proxy do Uvicorn foram exercitados com origem confiável e não confiável; headers encaminhados crus não são aceitos diretamente pela aplicação.
- HSTS só é aplicado quando o scheme observado é HTTPS; cookie Secure e fechamento de docs/openapi ocorrem em production.
- Nenhum segredo real, chave privada ou credencial de provedor foi identificado nos arquivos rastreados ou nos caminhos históricos consultados. Valores encontrados eram placeholders ou credenciais descartáveis de teste.

### Riscos residuais e limites

- A configuração segura precisa abranger staging, não apenas production.
- A proteção por IP é correta somente se o proxy confiável remover/recriar forwarded headers e impedir acesso direto; essa topologia não é fornecida pelo repositório.
- `FORWARDED_ALLOW_IPS` rejeita curingas e `/0`, mas a segurança final depende do valor usado pelo processo Uvicorn antes de importar a aplicação.
- O rate limiter não é proteção distribuída e não substitui controles no edge.
- A sessão stateless não possui revogação server-side.
- O caminho 500 precisa de headers no edge ou de uma composição que cubra a resposta externa do Starlette.

## Testes e qualidade

### O que oferece confiança real

- testes puros de configuração, guarda e limiter podem rodar sem banco;
- testes de integração usam PostgreSQL efêmero no fluxo oficial;
- P1.2–P1.5 têm cenários autenticados/não autenticados, CSRF, slug manual e atomicidade, hard delete, proxy, HSTS, CSP, hosts e OpenAPI;
- `make verify` aplica a guarda antes do ciclo Alembic e remove containers/rede específicos ao terminar;
- Ruff e `alembic check` estão no gate único.

### Cobertura superficial ou ausente

- o teste de logs força nível `INFO` com `caplog`, sem provar emissão stdout/estrutura;
- o teste de rotas protegidas parte das rotas já protegidas;
- configuração positiva usa hashes sintéticos sem validar parâmetros mínimos no backend;
- não há prova de cookie efetivamente emitido com flags/expiração esperadas;
- não há smoke da aplicação após `alembic upgrade head` sem `create_all`;
- não há teste de headers em exceção 500;
- cobertura pública é pequena: faltam filtros, sitemap/robots, Markdown malicioso, metadata e falha de banco;
- não há teste multiworker/multirréplica, carga de Argon2 ou failover de infraestrutura.

O warning conhecido foi reproduzido:

> `StarletteDeprecationWarning: Using httpx with starlette.testclient is deprecated; install httpx2 instead.`

Ele é **P3, não bloqueante agora**: as versões de teste estão fixadas, 147 testes passaram e não há falha funcional. Deve ser tratado em atualização coordenada de Starlette/httpx, sem instalar pacote novo ad hoc nem suprimir o warning globalmente.

## Banco, models e migrations

Há um único head Alembic (`20260728_01`). Model e migration permanecem coerentes quanto a tabelas, tipos, nullability, índices, unicidade e relações. No banco descartável, foram confirmados:

1. upgrade até `head`;
2. `alembic check` sem operações novas;
3. downgrade até `base`;
4. novo upgrade até `head`;
5. revisão final no head esperado.

Não foi detectada migration ausente nem operação destrutiva inesperada além do downgrade deliberado no PostgreSQL efêmero do gate. Nenhuma migration foi criada ou alterada nesta auditoria.

O risco é de cobertura: testes funcionais constroem schema por metadata e as invariantes originais continuam fora do banco. Corrigi-las exigirá migration futura explícita e não deve ser misturado às duas correções obrigatórias de configuração/guarda.

## Arquitetura e capacidade de evolução

O monólito modular continua proporcional ao produto atual. Não foram detectados ciclos de importação novos; `require_admin` em `app/core/security.py` evita dependência de core em routes/services; Labs continuam fora do CMS; e o navegador não recebe integração direta com LLM.

As fronteiras ainda são incompletas:

- `app/routes/admin.py` concentra parsing de formulário, validação de unicidade, resposta HTTP e orquestração;
- serviços consultam, adicionam e fazem commit de ORM apesar da diretriz de repositórios para persistência;
- settings/engine globais em import time tornam a app factory parcialmente configurável em testes.

Isso é dívida P3 focada, não justificativa para refatoração ampla durante o fechamento P0. O próximo passo arquitetural deve ser incremental e orientado por casos reais da v0.3.

## SEO, estabilidade de URLs e publicação

A política v0.2.1 resolve o risco imediato do projeto: slug não muda depois da criação e exclusão física não é possível pelo CMS. Título, conteúdo, status e visibility continuam editáveis. Um projeto publicado pode voltar a draft e então sua URL retorna 404; isso é coerente com a política atual, mas histórico/redirect/arquivamento serão necessários antes de permitir renomeação ou remoção segura.

No blog, a ausência de workflow editorial mantém risco de publicação acidental e sitemap indevido. Antes de ampliar conteúdo, Markdown deve ser default-private e ter critério explícito para URL, listagem e sitemap. Recursos avançados — localização independente PT-BR/EN, canonical/hreflang, JSON-LD e redirects — permanecem evolução futura, não correção de estabilização imediata.

## Deploy, operação e escala

O repositório oferece um bom ambiente de desenvolvimento e verificação, mas não uma topologia de produção completa. O próprio `docker-compose.yml` publica a porta do web e deve continuar tratado como desenvolvimento. Para deploy controlado faltam, no mínimo:

- imagem imutável e dependências de runtime totalmente reproduzíveis;
- proxy TLS versionado ou contrato operacional validado que seja o único caminho até Uvicorn;
- migration como job único, separada do startup de cada réplica;
- liveness/readiness e healthcheck do container web;
- baseline explícito de um worker/uma réplica enquanto limiter for local;
- backup, restore testado, rollback, métricas e alertas.

Escalar o web hoje pode enfraquecer rate limiting e duplicar migrations. Portanto múltiplos workers/réplicas não devem ser habilitados por variável operacional sem trocar o limiter por estado compartilhado e separar a responsabilidade de migration.

## Dívidas técnicas classificadas

### P2 — importantes antes de produção real

| Dívida | Motivo e critério de saída |
|---|---|
| Logging de segurança operacional | Emitir eventos sanitizados em stdout estruturado, com request/attempt ID, e provar no runtime. |
| Baseline de deployment | Imagens/dependências imutáveis, proxy exclusivo, job de migration, healthchecks e um worker/uma réplica explícitos. |
| Observabilidade e recuperação | Métricas, alertas, logs coletáveis, backup/restore e rollback exercitados. |
| Invariantes no banco | CHECKs/defaults/limites coerentes com schemas, com migration revisável. |
| Blog default-private | Estado editorial e exclusão segura de rascunhos de listagens/sitemap. |
| Sessão/revogação conforme risco | Decidir rotação/revogação server-side antes de ampliar superfície ou operadores. |
| Erros e headers no edge | Cobrir 500, separar readiness/liveness e manter headers em toda resposta observável. |

### P3 — melhorias posteriores

| Dívida | Momento apropriado |
|---|---|
| Warning Starlette/TestClient | Atualização coordenada do toolchain; não exige ação isolada agora. |
| Teste preventivo de rotas admin | Próxima alteração de superfície administrativa. |
| Refino routes/services/repositories | Ao iniciar casos de uso v0.3, sem “clean architecture” especulativa. |
| Erros HTML globais e acessibilidade | Antes de tráfego público relevante ou trabalho visual maior. |
| SEO técnico adicional | Antes de campanha/indexação multilíngue; priorizar canonical/metadata social. |
| Consistência documental/versão | Junto ao fechamento formal da estabilização. |
| Cache do blog | Somente se medição mostrar custo relevante. |

### FUTURO — quando escala ou escopo exigirem

| Dívida/evolução | Gatilho |
|---|---|
| Rate limiter compartilhado | Segundo worker, réplica ou instância. |
| Sessões server-side/RBAC/auditoria persistida | Mais administradores, privilégios distintos ou exigência de revogação. |
| Histórico de slug, aliases e redirects | Primeira necessidade legítima de renomear URL publicada. |
| Soft delete, archive e restore | Primeiro fluxo de despublicação/retirada operacional. |
| Cache/indexação do conteúdo Markdown | Crescimento medido de volume/latência. |
| Labs/filas/serviços separados | Cargas pesadas reais, conforme arquitetura já aprovada. |

## Readiness

### Decisão: A — NÃO PRONTO PARA EVOLUIR

A base não deve sair formalmente da estabilização enquanto F-01 e F-02 permanecerem. Ambos contradizem critérios explícitos do plano: defesa independente contra banco real e defaults convenientes restritos a ambiente local. Um gate verde no caminho Docker não compensa uma guarda permissiva, e produção segura não compensa staging autenticável com segredo público.

Depois dessas correções e da entrega operacional de logging de P1.1, a base pode ser reavaliada para **B — pronta para evoluir, mas não para produção**. A categoria **C — deploy controlado** depende do baseline P2 de proxy, migration, health, imagens, recovery e observabilidade. Não há evidência para categoria D.

## Próximas ações, em ordem

### Correções obrigatórias

1. **Fechar P0.2:** validar allowlist explícita de hosts/credenciais de teste e comparar destinos PostgreSQL por identidade canônica; cobrir host production/staging, alias de driver, porta default e equivalência com `DATABASE_URL`.
2. **Fechar P0.3 em staging:** exigir segredo não default, hash administrativo válido, PostgreSQL, HTTPS e hosts explícitos; emitir cookie Secure e adicionar teste negativo com cookie forjado.
3. **Fechar a parte de auditoria de P1.1:** configurar logging sanitizado e estruturado para stdout, incluir request/attempt ID e testar a saída real nos resultados success/failure/rate-limited.

### Dívida técnica

4. **Criar o baseline P2 de deploy controlado:** um worker/uma réplica explícitos, migration job único, liveness/readiness e healthcheck web, imagens/dependências imutáveis, proxy exclusivo, backup/restore/rollback e métricas.

### Evolução funcional

5. **Só após os gates, iniciar v0.3 de forma focada:** antes de expandir o blog, torná-lo default-private; depois evoluir casos de uso e fronteiras de camada sem refatoração ampla preventiva.

## Verificações executadas

Todos os comandos foram executados contra arquivos locais, containers descartáveis ou runtime sem rede. Nenhum banco normal foi acessado.

| Verificação | Resultado |
|---|---|
| `git status --short --branch` antes de qualquer execução | Limpo: apenas `## master`. |
| Leitura com `sed`/`rg`, inventário com `rg --files`, inspeção de histórico com `git log` | Concluídos; commits P0.1–P1.5 identificados. |
| `docker compose --env-file /dev/null --project-name rennam-dev-test -f compose.test.yml config --quiet` | Passou. |
| Provas da guarda por import/chamada local, sem conexão | Reproduziram aceitação de host remoto e alias do alvo normal. |
| Provas com `docker run --network none ... python -c ...` | Reproduziram cookie forjado em staging (200), logger INFO inativo, Argon2 fraco aceito pela configuração e 500 sem headers. |
| `make verify` | Passou integralmente. |
| Ruff dentro de `make verify` | Todos os checks passaram. |
| Testes puros dentro de `make verify` | 54 passaram; 1 warning conhecido. |
| Testes completos dentro de `make verify` | 93 passaram; 1 warning conhecido. |
| Alembic no PostgreSQL descartável | upgrade/check/downgrade/upgrade/head passaram; “No new upgrade operations detected”. |
| Scan estático de segredos e consulta de caminhos sensíveis no histórico | Nenhum segredo real evidente encontrado; limitação: não substitui secret scanner especializado. |
| `git diff --check` após o relatório | Passou, sem erro de whitespace. |

## Estado Git final

Não houve commit, alteração de código, migration, dependência, refactor ou correção. O working tree iniciou limpo e terminou com um único arquivo novo:

```text
?? docs/audits/TECHNICAL_AUDIT_POST_STABILIZATION_V0.2.1.md
```

Assim, este relatório é o único arquivo criado ou alterado pela auditoria.

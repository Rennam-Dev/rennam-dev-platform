# Confirmação técnica pós-remediação v0.2.1

**Data:** 2026-08-08

**Escopo:** confirmação independente de R1, R2 e R3

**Commits avaliados:** `d4a03df` (R1), `79a75bd` (R2) e `b1d6c72` (R3)

## Resumo executivo

As três remediações corrigem os achados que motivaram esta confirmação:

| Remediação | Classificação | Conclusão |
|---|---|---|
| R1 — guarda do banco de testes | **RESOLVIDO** | O bypass trivial por PostgreSQL remoto com nome `_test` foi fechado; o fluxo destrutivo oficial permanece restrito ao Compose descartável. |
| R2 — staging fail-closed | **RESOLVIDO** | Staging não inicia com o segredo público/default e um cookie assinado com o segredo antigo não autentica. |
| R3 — logging de autenticação | **RESOLVIDO** | Os três eventos são emitidos em `INFO`, uma vez, para stdout no runtime padrão. |

Não foi identificado novo risco **CRITICAL/HIGH/P0/P1** introduzido por R1, R2
ou R3. As regressões rápidas e o gate completo permaneceram verdes.

**Readiness atual: B — PRONTO PARA EVOLUIR, MAS NÃO PARA PRODUÇÃO.**

- **Existe bloqueador HIGH/P0/P1 para iniciar a evolução funcional da v0.3? NÃO.**
- **Existe bloqueador para publicar o repositório no GitHub após revisão de
  secrets? NÃO.** A publicação do código não equivale a autorização de deploy.

## Método e limites

Foram relidos os documentos obrigatórios, inspecionados os arquivos indicados e
comparados os três commits de remediação com os achados anteriores. As provas
dinâmicas usaram apenas resolução simulada, SQLite em memória, container sem
rede ou o PostgreSQL efêmero de `compose.test.yml`.

Não houve conexão com banco de development, staging ou production. Não foram
executados pentest externo, scanner de CVEs, teste de carga, proxy real,
restauração de backup ou deploy. A busca de secrets foi estática e não substitui
um scanner especializado antes de tornar o repositório público.

## R1 — banco de testes

### Resultado: RESOLVIDO

`tests/support/database.py` aceita SQLite somente como
`sqlite[+pysqlite]:///:memory:`. Para PostgreSQL, a guarda exige simultaneamente:

- `APP_ENV=test`;
- host literal `test-db`, porta `5432`, banco `rennam_test` e sufixo `_test`;
- usuário e credencial descartáveis exatamente iguais ao contrato do Compose;
- ausência de query, fragment, `DATABASE_URL` normal e overrides libpq capazes
  de alterar destino;
- resolução bem-sucedida para exatamente um IPv4 em `10/8`, `172.16/12` ou
  `192.168/16`.

Hostname alternativo, IP literal, localhost/loopback, IP público, link-local,
IPv6, resolução vazia/falha e múltiplos endereços são negados. A allowlist não é
configurável e não oferece wildcard, toggle ou opt-out.

O contrato corresponde a `compose.test.yml`: serviço `test-db`, banco e
credenciais próprios, nenhuma porta publicada, dados em `tmpfs` e rede
`internal: true`.

A guarda permanece posicionada:

- antes de importar/criar o engine em `tests/conftest.py`;
- imediatamente antes de cada `drop_all()` e `create_all()`, inclusive teardown;
- antes de exportar `DATABASE_URL` e antes de cada `alembic current`, `heads`,
  `upgrade`, `check` e `downgrade` em `scripts/verify.sh`.

Uma prova pura com DNS simulado aceitou apenas SQLite em memória e o perfil
oficial resolvido para IPv4 privado. Rejeitou host remoto, IP público,
localhost, URL normal, resolução pública, múltiplos endereços e `PGHOSTADDR`,
sem abrir conexão.

### Limite residual

A resolução validada e a conexão posterior são operações distintas. Controle
hostil de DNS/roteamento poderia tentar um rebinding ou fazer `test-db` apontar
para um endpoint RFC1918 que reproduza toda a identidade pública de teste. Isso
não reabre o erro trivial original e, no fluxo suportado, é contido pela rede
interna do Compose. Fica como defesa em profundidade P3, não como bloqueador.

## R2 — staging fail-closed

### Resultado: RESOLVIDO

`Settings` centraliza a noção de ambiente implantável em
`staging|production`. Nos dois ambientes:

- o segredo default, segredo menor que 32 caracteres e whitespace periférico
  são rejeitados;
- `ADMIN_PASSWORD_HASH` é obrigatório e precisa ter estrutura Argon2 admitida;
- `ADMIN_USERNAME` vazio é rejeitado;
- `DATABASE_URL` precisa usar PostgreSQL;
- `SITE_URL` precisa ser HTTPS absoluta, sem credenciais, query ou fragment;
- o hostname de `SITE_URL` precisa constar em `ALLOWED_HOSTS`;
- o cookie de sessão recebe `Secure`.

`SessionMiddleware` usa diretamente `settings.session_secret`, isto é, o mesmo
valor validado por `Settings`, e `https_only=settings.session_cookie_secure`.

A cadeia de ataque anterior agora termina na validação da assinatura:

```text
segredo público antigo
→ cookie assinado pelo atacante com {"admin": "..."}
→ SessionMiddleware configurado com segredo staging distinto
→ assinatura inválida e sessão não autorizada
→ require_admin redireciona para /admin/login
```

O teste negativo reproduz o cookie antigo e recebe `303 /admin/login`. O teste
positivo confirma login legítimo, flag `Secure` e dessina o cookie emitido com o
segredo validado. Development e test preservam conveniências locais;
production mantém as mesmas ou maiores proteções. Staging permanece diferente
de production apenas onde já é deliberado, como OpenAPI e HSTS, não na
configuração sensível ou no cookie.

### Limites residuais

As validações de força continuam sintáticas: segredo repetitivo com 32
caracteres pode passar, Argon2 é validado por regex sem mínimos de parâmetros e
`DATABASE_URL` valida principalmente o esquema. São dívidas P2 já conhecidas;
nenhuma permite reutilizar silenciosamente o segredo público antigo.

## R3 — logging de autenticação

### Resultado: RESOLVIDO

`app/core/logging.py` configura `rennam.admin_auth` com:

- nível próprio e efetivo `INFO`;
- um `StreamHandler` nomeado `rennam.admin_auth.stdout` em stdout;
- `propagate=False`;
- formatter chave-valor limitado a timestamp, nível, logger, evento, IP
  normalizado, path e resultado;
- busca pelo handler nomeado, tornando chamadas repetidas idempotentes.

`create_app()` aplica essa configuração sem substituir o logging do Uvicorn.
O logger não depende do root nem do handler `uvicorn`, e a ausência de
propagação impede uma segunda linha.

No container recém-construído pelo gate, com rede desabilitada, foram
confirmados:

```text
effective_level=INFO
info_enabled=true
handler_count=1
handler=rennam.admin_auth.stdout
stream=<stdout>
propagate=false
```

O mesmo runtime emitiu uma única linha para cada evento:

- `admin_login_success`;
- `admin_login_failure`;
- `admin_login_rate_limited`.

Os fluxos reais e o formatter não recebem username, senha, hash Argon2,
`SESSION_SECRET`, cookie, sessão/session ID, CSRF, Authorization,
`DATABASE_URL` ou corpo do formulário. O teste funcional verifica esses valores
negativamente e conta exatamente uma emissão por tentativa, sem depender de
`caplog`.

## Regressões verificadas

| Controle | Evidência de confirmação | Resultado |
|---|---|---|
| Auth administrativa e `require_admin` | Login continua público; rotas atuais de dashboard, logout, criação, edição e exclusão declaram a dependência comum; sessão inválida redireciona. | Preservado |
| CSRF | Login, logout, criação, edição e tentativa de exclusão continuam validando token; casos inválidos retornam 403 antes da mutação. | Preservado |
| Rate limiting | Janela, buckets por IP, proxy confiável/não confiável, 429 e bypass de Argon2 quando limitado continuam cobertos. | Preservado |
| Slug imutável | Serviço rejeita divergência antes de alterar outros campos; draft e published permanecem no slug original. | Preservado |
| Hard delete | Serviço sempre nega; endpoint mantém auth/CSRF, responde 409 e o projeto/associações permanecem. | Preservado |
| TrustedHost e proxy | Hosts explícitos, wildcard e `/0` negados; forwarded headers só afetam o escopo via proxy confiável do Uvicorn. | Preservado |
| OpenAPI | `/docs`, `/redoc` e `/openapi.json` permanecem ausentes em production. | Preservado |
| Headers, CSP e HSTS | Headers normais, CSP sem `unsafe-inline/eval`, admin `no-store` e HSTS somente em production HTTPS continuam cobertos. | Preservado |
| Cookies | `HttpOnly`/SameSite do middleware permanecem; staging/production usam `Secure` e o segredo validado. | Preservado |
| Models e migrations | Um único head `20260728_01`; `alembic check` sem novas operações; downgrade/upgrade no banco efêmero passou. | Preservado |
| Ambiente reproduzível | Compose de teste válido; Ruff, testes puros/completos e ciclo Alembic executados pelo gate único. | Preservado |

## Novos riscos encontrados

Nenhum novo achado CRITICAL, HIGH, P0 ou P1 foi identificado nas remediações.

Dois limites de defesa em profundidade merecem registro, sem bloquear evolução:

- R1 não oferece garantia criptográfica contra DNS/host comprometido fora da
  topologia oficial;
- o formatter R3 pressupõe que qualquer produtor futuro do logger forneça todos
  os campos estruturados esperados; omiti-los causa erro de formatação, não
  vazamento de segredo.

## Dívidas técnicas restantes

### P2 — importantes antes de produção real

- **Baseline de deploy:** imagens e dependências de runtime imutáveis, proxy TLS
  exclusivo, migration como job único, healthcheck web e baseline explícito de
  um worker/uma réplica.
- **Operação:** coleta/retenção/alerta dos logs stdout, métricas, backup/restore
  testado e rollback.
- **Configuração sensível:** validação operacional de Argon2, política melhor de
  força do segredo e identidade completa de `DATABASE_URL` implantável.
- **Erros e disponibilidade:** headers também em 500, liveness/readiness
  separados e falha de banco convertida em 503 controlado.
- **Dados e migrations:** constraints/defaults/limites alinhados aos schemas e
  smoke da aplicação sobre schema provisionado por Alembic.
- **Publicação do blog:** conteúdo default-private antes de expandir o fluxo de
  blog na v0.3.
- **Sessão:** avaliar revogação server-side antes de ampliar operadores ou risco.

### P3 — melhorias posteriores

- Tornar o inventário de rotas admin preventivo para detectar futuras rotas sem
  `require_admin`.
- Tornar o formatter de autenticação tolerante ou tipar o contrato de produtores
  antes de adicionar novos usos do logger.
- Tratar o warning `StarletteDeprecationWarning` em atualização coordenada do
  toolchain. As versões de teste estão controladas e todas as suítes passam; não
  há justificativa para instalar `httpx2` isoladamente ou suprimir o warning.
- Defesa adicional contra TOCTOU de DNS na guarda, se surgir execução
  PostgreSQL suportada fora do Compose interno.

### FUTURO — depende de escala ou escopo

- limiter compartilhado antes de múltiplos workers/réplicas;
- sessões server-side, RBAC e auditoria persistida com múltiplos operadores;
- histórico de slug/redirects e archive/soft delete/restore quando URLs
  precisarem ser renomeadas ou retiradas.

## Readiness e decisões explícitas

### B — PRONTO PARA EVOLUIR, MAS NÃO PARA PRODUÇÃO

R1 e R2 fecharam os dois bloqueadores HIGH que sustentavam a classificação A.
R3 entregou a emissão operacional que faltava a P1.1. O gate permanece verde e
as remediações não enfraqueceram os controles P0/P1 existentes.

**Liberação para v0.3: NÃO existe bloqueador HIGH/P0/P1 para iniciar evolução
funcional.** A resposta objetiva é **NÃO**. A evolução deve continuar incremental;
se o primeiro escopo envolver o blog, tornar Markdown default-private é seu
pré-requisito específico.

**Publicação no GitHub após revisão de secrets: NÃO existe bloqueador técnico
identificado.** A resposta objetiva é **NÃO**. `.env` não é rastreado, os valores
versionados encontrados são placeholders ou credenciais deliberadamente
descartáveis de teste, e a busca simples não encontrou chave privada/token real.
Ainda assim, uma varredura de secrets dedicada antes do primeiro push público é
uma precaução operacional adequada.

As lacunas P2 acima impedem classificar a base como C ou D e continuam
obrigatórias antes de produção real.

## Comandos e verificações executados

| Verificação | Resultado |
|---|---|
| `git status --short --branch` antes das verificações | Limpo: `## master` |
| Leitura com `sed`/`rg`, inventário e `git log` | Concluídos; R1/R2/R3 e documentação comparados |
| Matriz Python pura da R1 com DNS simulado | Perfil oficial/SQLite aceitos; desvios negados; nenhuma conexão |
| `docker compose --env-file /dev/null --project-name rennam-dev-test -f compose.test.yml config --quiet` | Passou |
| `make verify` | Passou integralmente |
| Ruff dentro de `make verify` | Passou |
| Testes puros | `100 passed`, 1 warning conhecido |
| Suíte completa | `142 passed`, 1 warning conhecido |
| Alembic descartável | current/heads/upgrade/check/downgrade/upgrade/current passaram; nenhum drift |
| Prova R3 no container do gate com `--network none` | INFO habilitado, um handler stdout, sem propagação; três eventos emitidos |
| Busca estática de chaves/tokens e arquivos sensíveis rastreados | Nenhum segredo real evidente; `.env` ignorado |
| `git diff --check` após o relatório | Passou, sem erro de whitespace |

## Estado Git final

As verificações finais confirmaram somente:

```text
?? docs/audits/TECHNICAL_AUDIT_REMEDIATION_CONFIRMATION_V0.2.1.md
```

Nenhum código, configuração, migration, schema ou dependência foi alterado.
Nenhum commit foi criado.

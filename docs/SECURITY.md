# Segurança

**Estado:** os controles explicitamente marcados como implementados descrevem a
v0.2.1. Os blocos “Planejado” são requisitos futuros e não devem ser
interpretados como funcionalidade existente ou autorização de produção.

## Identidade

### Implementado na v0.2.1

- Senhas com Argon2.
- Sessões em cookies `HttpOnly`, `Secure` em staging/production e `SameSite`
  adequado.
- Rotação de sessão no login.
- CSRF em operações de escrita.

### Planejado, não implementado

- Recuperação de senha e convites com tokens aleatórios, expirados e
  armazenados como hash.

### Configuração de ambientes implantáveis

Staging e production usam a mesma política fail-closed de configuração
sensível. Ambos exigem segredo de sessão explícito, não default e com ao menos
32 caracteres; username administrativo não vazio; hash Argon2 estruturalmente
válido; PostgreSQL; `SITE_URL` HTTPS absoluta; e o hostname do site em
`ALLOWED_HOSTS`. Wildcards de host e confiança global de proxy continuam
proibidos.

Development e test podem manter defaults locais. Os placeholders públicos de
`.env.example` pertencem somente a development e não iniciam staging/production
sem substituição. Mensagens de validação não incluem segredo de sessão, hash,
senha, cookie ou URL completa do banco.

### Proteção do login administrativo

O login administrativo limita falhas pelo endereço remoto observado diretamente
em `request.client.host`. A aplicação não interpreta cabeçalhos forwarded
diretamente; somente o Uvicorn pode traduzir `X-Forwarded-For` e
`X-Forwarded-Proto`, e apenas quando a conexão vem da allowlist explícita do
proxy descrita abaixo. `X-Real-IP` e `Forwarded` não são usados.

A política inicial permite até 5 falhas em uma janela deslizante de 10 minutos.
A quinta falha ainda recebe a resposta genérica de credenciais inválidas e
estabelece o bloqueio; novas tentativas recebem HTTP 429 com `Retry-After` até a
falha mais antiga expirar. Um login válido fora do bloqueio limpa as falhas do IP.
Os valores podem ser configurados por `ADMIN_LOGIN_MAX_FAILURES`,
`ADMIN_LOGIN_WINDOW_SECONDS` e `ADMIN_LOGIN_MAX_CLIENTS`.

O armazenamento é protegido para acesso concorrente, expira entradas antigas e
mantém no máximo 10.000 IPs por processo. Ele é deliberadamente local e atende ao
único processo Uvicorn atual. Múltiplos workers ou réplicas mantêm contadores
independentes; antes de escalar horizontalmente será necessário adotar um backend
compartilhado, sem remover a negação segura em caso de falha do limitador.

Os eventos `admin_login_success`, `admin_login_failure` e
`admin_login_rate_limited` registram apenas evento, timestamp do logging, IP
normalizado, path e resultado. Username, senha, hash, cookie, sessão, CSRF,
headers de autorização, URL do banco e corpo do formulário não são registrados.
O logger dedicado `rennam.admin_auth` opera em nível `INFO` e emite uma única
linha estruturada em chave-valor para o stdout padrão do container, sem exigir
configuração manual adicional e sem substituir o logging do Uvicorn.

## Fronteira HTTP

### OpenAPI

`/docs` e `/openapi.json` permanecem disponíveis em `development`, `test` e
`staging`. Em `production`, `/docs`, `/redoc` e `/openapi.json` não são
registrados pela aplicação. O ReDoc permanece desabilitado nos demais ambientes
para preservar o comportamento atual.

### Hosts e headers de segurança

Toda requisição deve usar um host listado explicitamente em `ALLOWED_HOSTS`.
Wildcards são rejeitados, e em staging/production a lista deve incluir o
hostname de `SITE_URL`.

As respostas recebem `X-Content-Type-Options: nosniff`,
`Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: DENY` e
uma `Permissions-Policy` que desabilita câmera, geolocalização, microfone,
pagamentos e USB. HTML da aplicação também recebe CSP restrita a recursos
same-origin, sem `unsafe-inline` ou `unsafe-eval`. O Swagger em `/docs` é a única
exceção de CSP em ambientes não produtivos porque sua UI atual usa script inline
e recursos externos. Respostas sob `/admin` recebem `Cache-Control: no-store`.

Em respostas HTTPS de `production`, a aplicação envia HSTS por um ano.
`includeSubDomains` e `preload` não são usados nesta fase. Como `SITE_URL` já
precisa ser HTTPS, o reverse proxy deve expor production somente via TLS,
informar corretamente o esquema externo e preservar esse header. A aplicação
não força redirect HTTP→HTTPS, evitando loops quando TLS termina no proxy.

### Proxy confiável

`FORWARDED_ALLOW_IPS` aceita somente IPs e redes CIDR explícitos e rejeita `*`
e redes `/0`, equivalentes a confiança global. O default confia apenas em
`127.0.0.1`. O rate limiter continua lendo
`request.client.host`; ele não consulta diretamente `X-Forwarded-For`,
`X-Real-IP`, `Forwarded` ou `X-Forwarded-Proto`.

Forwarded headers só podem influenciar o endereço/esquema observado quando a
conexão chega de um proxy listado em `FORWARDED_ALLOW_IPS`. Esse proxy deve ser
controlado, inacessível para bypass direto e remover/substituir valores enviados
pelo cliente antes de encaminhar `X-Forwarded-For` e `X-Forwarded-Proto`.
`X-Real-IP` e `Forwarded` não fazem parte do contrato atual. Confiar em `*`, em
redes amplas ou preservar headers do cliente permitiria falsificação de IP e
enfraqueceria o rate limiting.

## Autorização planejada, não implementada

- Papéis administrativos separados de usuários demo.
- Acesso concedido por Lab, prazo e quota.
- Negação por padrão.
- Logs de concessão, revogação e uso.

O painel atual possui um único administrador e nega acesso por padrão por meio
da sessão administrativa. Papéis, usuários demo, Labs e concessões pertencem ao
roadmap futuro.

## Proteção de LLM planejada, não implementada

- Chaves somente no servidor.
- Rate limit, limite de requisições, tokens e orçamento.
- Bloqueio automático ao atingir hard limit.
- Registro de modelo, tokens, custo estimado, latência, status e request ID.

## Conteúdo e uploads

**Implementado na v0.2.1:** sanitização de Markdown/HTML.

**Planejado, não implementado:** upload com validação de MIME, extensão, tamanho
e dimensões; storage externo com apenas metadados no banco.

## Requisitos operacionais antes de produção

- Segredos por variáveis de ambiente ou secret manager.
- Backups do banco e mídia com teste de restauração.
- Dependências e imagens Docker atualizadas de forma controlada.
- Auditoria de segurança antes do deploy e após funcionalidades sensíveis.

Esses itens são baseline operacional P2. Não foram comprovados por deploy,
proxy real, restauração de backup ou monitoramento e impedem classificar a base
como pronta para produção.

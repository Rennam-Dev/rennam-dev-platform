# Segurança

## Identidade

- Senhas com Argon2.
- Sessões em cookies `HttpOnly`, `Secure` em produção e `SameSite` adequado.
- Rotação de sessão no login.
- CSRF em operações de escrita.
- Recuperação de senha e convites com tokens aleatórios, expirados e armazenados como hash.

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

## Fronteira HTTP

### OpenAPI

`/docs` e `/openapi.json` permanecem disponíveis em `development`, `test` e
`staging`. Em `production`, `/docs`, `/redoc` e `/openapi.json` não são
registrados pela aplicação. O ReDoc permanece desabilitado nos demais ambientes
para preservar o comportamento atual.

### Hosts e headers de segurança

Toda requisição deve usar um host listado explicitamente em `ALLOWED_HOSTS`.
Wildcards são rejeitados, e em `production` a lista deve incluir exatamente o
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

## Autorização

- Papéis administrativos separados de usuários demo.
- Acesso concedido por Lab, prazo e quota.
- Negação por padrão.
- Logs de concessão, revogação, login e uso.

## Proteção de LLM

- Chaves somente no servidor.
- Rate limit, limite de requisições, tokens e orçamento.
- Bloqueio automático ao atingir hard limit.
- Registro de modelo, tokens, custo estimado, latência, status e request ID.

## Conteúdo e uploads

- Sanitização de Markdown/HTML.
- Validação de MIME, extensão, tamanho e dimensões.
- Storage externo em produção; banco guarda metadados.

## Operação

- Segredos por variáveis de ambiente ou secret manager.
- Backups do banco e mídia com teste de restauração.
- Dependências e imagens Docker atualizadas de forma controlada.
- Auditoria de segurança antes do deploy e após funcionalidades sensíveis.

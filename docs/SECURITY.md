# Segurança

## Identidade

- Senhas com Argon2.
- Sessões em cookies `HttpOnly`, `Secure` em produção e `SameSite` adequado.
- Rotação de sessão no login.
- CSRF em operações de escrita.
- Recuperação de senha e convites com tokens aleatórios, expirados e armazenados como hash.

### Proteção do login administrativo

O login administrativo limita falhas pelo endereço remoto observado diretamente
em `request.client.host`. Cabeçalhos `X-Forwarded-For`, `X-Real-IP` e `Forwarded`
não são usados enquanto a fronteira segura de proxy não estiver configurada.

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

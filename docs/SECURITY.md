# Segurança

## Identidade

- Senhas com Argon2.
- Sessões em cookies `HttpOnly`, `Secure` em produção e `SameSite` adequado.
- Rotação de sessão no login.
- CSRF em operações de escrita.
- Recuperação de senha e convites com tokens aleatórios, expirados e armazenados como hash.

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

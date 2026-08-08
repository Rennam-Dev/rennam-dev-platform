# Deploy

## Ambientes

Local, test, staging e production.

## Produção

- Docker.
- Reverse proxy e HTTPS.
- PostgreSQL gerenciado ou isolado.
- Storage compatível com S3 para mídia.
- Migrations executadas como etapa controlada.
- Health checks, logs, métricas e alertas.
- Backup e procedimento de rollback.

## Regra

Nenhum deploy deve depender de estado manual não documentado. Variáveis obrigatórias devem ser validadas na inicialização.

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

## HTTP e reverse proxy

O reverse proxy controlado termina TLS e deve ser o único caminho de rede para o
container web. Ele deve:

- remover os headers `X-Forwarded-For` e `X-Forwarded-Proto` recebidos do cliente;
- recriá-los com o IP original e o esquema externo já validados;
- encaminhar um `Host` presente em `ALLOWED_HOSTS`;
- preservar os headers de segurança retornados pela aplicação;
- impedir acesso direto da internet à porta do Uvicorn.

O `docker-compose.yml` documentado no README é somente para desenvolvimento
local e publica a porta 8000 no host. Ele não representa a topologia de
production. No deploy real, a porta do Uvicorn deve ficar em rede privada ou
restrita ao endereço pelo qual o proxy controlado se conecta.

Configure `ALLOWED_HOSTS` com hosts exatos. Em production, o hostname de
`SITE_URL` é obrigatório. Configure `FORWARDED_ALLOW_IPS` somente com os IPs ou
CIDRs de origem do proxy controlado. `*` e redes `/0` são rejeitados; o default
`127.0.0.1` não confia automaticamente em redes Docker.

Use DNS ou IPv4 em `ALLOWED_HOSTS`; literais IPv6 são rejeitados porque a versão
atual do middleware de host não os interpreta de forma confiável. Essa limitação
não se aplica a `FORWARDED_ALLOW_IPS`, cuja validação aceita IPv6 e CIDR IPv6.

O Uvicorn recebe explicitamente `--proxy-headers` e
`--forwarded-allow-ips "$FORWARDED_ALLOW_IPS"`. Apenas conexões vindas dessa
allowlist podem fazer `X-Forwarded-For` e `X-Forwarded-Proto` alterarem o escopo
ASGI. `X-Real-IP` e `Forwarded` são ignorados pelo contrato atual.

A aplicação não executa redirect HTTP→HTTPS. Production exige `SITE_URL` HTTPS,
envia `Strict-Transport-Security: max-age=31536000` nas respostas cujo esquema
ASGI é HTTPS e pressupõe que o proxy só a publique via TLS. Não habilite preload
ou `includeSubDomains` sem inventário e decisão operacional próprios.

## Superfície por ambiente

- `development`, `test` e `staging`: `/docs` e `/openapi.json` disponíveis;
- `production`: `/docs`, `/redoc` e `/openapi.json` ausentes;
- todos os ambientes: hosts validados e headers HTTP básicos;
- somente `production`: cookie de sessão `Secure` e HSTS.

## Regra

Nenhum deploy deve depender de estado manual não documentado. Variáveis obrigatórias devem ser validadas na inicialização.

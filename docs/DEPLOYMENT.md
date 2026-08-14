# Deploy

## Ambientes

Local, test, staging e production.

Staging e production são ambientes implantáveis e falham na inicialização sem
segredo de sessão não default e com ao menos 32 caracteres, hash administrativo
Argon2, username não vazio, PostgreSQL, `SITE_URL` HTTPS e host permitido. Os
placeholders de `.env.example` são exclusivos de development. O cookie de sessão
é `Secure` nos dois ambientes.

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

Configure `ALLOWED_HOSTS` com hosts exatos. Em staging/production, o hostname de
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
- `staging` e `production`: cookie de sessão `Secure`;
- somente `production`: HSTS.

## Regra

Nenhum deploy deve depender de estado manual não documentado. Variáveis obrigatórias devem ser validadas na inicialização.

## Cutover do Blog/Journal para o CMS SQL (v0.4 M4.5)

O import do conteúdo legado é uma ação operacional explícita. Ele não roda em
startup, request, migration Alembic ou fallback do runtime. Execute-o com o
mesmo artefato imutável da release que será promovida, enquanto a versão antiga
continua atendendo as URLs públicas:

1. Confirme backup recuperável e aplique as migrations de schema da release.
2. No artefato da release, com a configuração do PostgreSQL alvo, execute:

   ```bash
   python -m app.scripts.import_legacy_blog
   ```

3. Verifique no banco ou na administração autenticada que existem exatamente os
   Articles publicados esperados:

   - `blog/ola-mundo`, `published_at=2026-07-03 00:00:00 UTC`;
   - `blog/por-que-fastapi`, `published_at=2026-07-05 00:00:00 UTC`;
   - Category `Conteúdo legado` (`conteudo-legado`) e as Tags do frontmatter.

4. Reexecute o comando. O resultado esperado é `0 criado(s), 2 inalterado(s)`.
   Qualquer divergência aborta o comando sem sobrescrever o CMS e exige correção
   manual antes do cutover.
5. Somente após essas verificações, promova/inicie o runtime SQL da release.
6. Verifique `GET /blog`, `/blog/ola-mundo`, `/blog/por-que-fastapi`,
   `GET /journal` e um detalhe publicado de Journal quando houver.

A unidade transacional é um Article: Article, Category e Tags daquele arquivo
são confirmados juntos ou revertidos juntos. Se um arquivo posterior falhar, os
anteriores já confirmados permanecem válidos; corrija a causa e reexecute o
comando idempotente. Datas legadas sem horário são interpretadas como meia-noite
UTC. Não faça deploy do runtime SQL antes do passo 3, pois isso criaria uma
janela evitável de 404 nas URLs legadas.

# Plano de estabilização v0.2.1

**Origem:** `docs/audits/TECHNICAL_AUDIT_V0.2.md`
**Escopo:** somente achados P0 e P1 da auditoria
**Estado:** proposto; nenhuma tarefa deste documento está implementada
**Regra de execução:** cada tarefa deve ser implementada, revisada e validada separadamente, sem avançar enquanto seus critérios de aceite não forem satisfeitos

## 1. Objetivo da versão

Tornar a base v0.2 segura para executar validações e suficientemente endurecida para uma avaliação de produção, sem ampliar o produto. A v0.2.1 deve eliminar o risco de testes contra bancos reais, validar configurações críticas antes do startup, criar um ambiente verificável e conter os riscos imediatos do painel administrativo e de URLs publicadas.

Este plano não autoriza implementação. Cada tarefa exigirá uma solicitação de execução própria, inspeção do estado corrente e aprovação de qualquer dependência nova.

## 2. Decisões e limites do plano

- Nenhum teste poderá ser executado antes da conclusão conjunta de P0.1 e P0.2.
- Bancos local, staging e production nunca serão usados por testes.
- Testes que criam, removem ou migram schema só poderão operar em banco descartável, com identidade validada antes da conexão destrutiva.
- Não serão criadas tabelas de redirect, histórico, auditoria ou arquivamento na v0.2.1.
- Slugs se tornarão imutáveis após a criação. É a contenção mais segura enquanto redirects persistidos não existem.
- Hard delete de projetos será bloqueado. A política definitiva de archive/redirect/404/410 fica fora desta estabilização.
- Auditoria de login será feita em logs estruturados, sem persistência no PostgreSQL e sem dados sensíveis.
- O rate limiting inicial será local ao processo, com memória limitada e relógio injetável. Isso é compatível com o único processo Uvicorn atual; múltiplas réplicas exigirão backend compartilhado em decisão posterior.
- Nenhuma dependência Python nova é necessária para a abordagem proposta. Se a implementação optar por biblioteca externa, deve parar e pedir aprovação.
- Funcionalidades futuras — blog CMS, i18n, usuários, convites, Labs, quotas e SEO avançado — permanecem fora do escopo.

## 3. Gates de execução

| Gate | Condição para avançar |
|---|---|
| G0 | P0.1 e P0.2 revisadas estaticamente; somente então é permitido iniciar pytest |
| G1 | P0.3 validada sem acesso a banco real |
| G2 | P0.4 executa pytest, Ruff e Alembic exclusivamente no ambiente descartável |
| G3 | P1.1–P1.5 passam na suíte segura e não reduzem sessão, Argon2 ou CSRF |
| G4 | Diff final contém apenas estabilização aprovada, documentação e testes correspondentes |

## 4. Tarefas P0 — impedir dano e validar o ambiente

### P0.1 — isolamento seguro do banco de testes

1. **Objetivo**

   Separar a configuração e o ciclo de vida do banco de testes do banco normal da aplicação antes que qualquer model, engine ou app seja importado.

2. **Risco que resolve**

   Reduz o risco crítico de `pytest` herdar `DATABASE_URL` de desenvolvimento, staging ou produção e executar `drop_all()` nesse banco.

3. **Arquivos provavelmente afetados**

   - `tests/conftest.py`
   - possivelmente `tests/support/database.py` como helper pequeno e puro
   - `app/core/config.py`, somente se for indispensável expor `APP_ENV=test` sem acoplamento
   - `docs/TESTING.md`

4. **Abordagem proposta**

   - Definir `APP_ENV=test` e a URL ativa de testes antes dos imports de `app.*` em `tests/conftest.py`.
   - Usar `TEST_DATABASE_URL` como entrada exclusiva da suíte; na ausência dela, usar SQLite estritamente em memória para os testes rápidos de rota.
   - Copiar a URL de teste validada para `DATABASE_URL` antes da criação do engine; nunca usar `setdefault`, pois uma URL externa preexistente não pode prevalecer.
   - Manter o schema efêmero e sem arquivo local persistente.
   - Reservar PostgreSQL descartável para integração e migrations em P0.4.
   - Não executar pytest ao concluir apenas esta tarefa; P0.2 ainda precisa instalar a trava independente.

5. **Impacto em banco/migration**

   Nenhuma migration nova. Nenhum banco existente deve ser acessado. SQLite em memória poderá receber `create_all/drop_all` apenas depois de P0.2; PostgreSQL será tratado somente em P0.4.

6. **Impacto em segurança**

   Positivo e crítico: remove a herança implícita da URL normal. Não altera autenticação, autorização, sessão ou CSRF.

7. **Testes necessários**

   - Teste estático/unitário do bootstrap confirmando que a URL ativa é a de teste antes de importar `app.core.database`.
   - Teste de que a ausência de `TEST_DATABASE_URL` resulta em SQLite `:memory:`.
   - Teste de que um `DATABASE_URL` externo preexistente não é usado pela suíte.
   - Esses testes só serão executados depois de P0.2.

8. **Critérios de aceite**

   - Não há caminho de import da suíte que crie o engine antes da configuração de teste.
   - O default de testes não cria arquivo `.db`.
   - Nenhuma URL de aplicação é reutilizada implicitamente.
   - A revisão do diff confirma que nenhum teste foi executado ainda.

9. **Rollback**

   Reverter apenas o bootstrap/helper de testes. Como nenhum banco foi tocado durante esta tarefa isolada, não há rollback de dados.

10. **Dependências da tarefa**

   Nenhuma. É a primeira tarefa e pré-requisito de todas as demais validações.

### P0.2 — trava anti-produção / anti-staging nos testes

1. **Objetivo**

   Bloquear a suíte antes de abrir conexão ou executar DDL quando a identidade do ambiente/banco não for inequivocamente de teste.

2. **Risco que resolve**

   P0.1 separa a configuração, mas uma `TEST_DATABASE_URL` preenchida incorretamente ainda poderia apontar para um banco real. Esta tarefa cria defesa independente e fail-closed.

3. **Arquivos provavelmente afetados**

   - `tests/conftest.py`
   - `tests/support/database.py`
   - novo `tests/test_test_database_guard.py`
   - `docs/TESTING.md`

4. **Abordagem proposta**

   - Implementar uma função pura `assert_safe_test_database(url, app_env)` chamada antes de criar engine, sessão ou schema.
   - Exigir simultaneamente `APP_ENV=test` e origem em `TEST_DATABASE_URL`.
   - Aceitar automaticamente apenas SQLite em memória.
   - Para PostgreSQL descartável, exigir nome de banco terminado em `_test`, host explicitamente permitido pelo ambiente de testes e ausência de nomes/hosts protegidos como production/staging.
   - Rejeitar SQLite em arquivo, URL vazia, backend desconhecido, banco sem sufixo de teste, credencial/host de ambiente protegido e qualquer URL igual à `DATABASE_URL` normal quando ela estiver disponível.
   - Não usar somente um toggle do tipo `ALLOW_DROP=1`; um toggle isolado é fácil de copiar para o ambiente errado.
   - Executar a trava novamente imediatamente antes de qualquer `drop_all`, downgrade ou limpeza destrutiva.

5. **Impacto em banco/migration**

   Nenhuma migration. A função deve ser testável sem conexão. A primeira execução real só ocorrerá contra SQLite em memória ou PostgreSQL descartável validado.

6. **Impacto em segurança**

   Positivo e crítico: adiciona defesa em profundidade contra destruição de dados e configuração acidental. Mensagens de erro não devem imprimir senha ou URL completa.

7. **Testes necessários**

   - Tabela parametrizada de URLs permitidas e negadas.
   - Casos `APP_ENV=development`, `staging`, `production`, `prod`, vazio e desconhecido devem falhar.
   - PostgreSQL sem `_test`, SQLite em arquivo e URL igual à normal devem falhar antes de chamar qualquer connector.
   - Spy/mock deve provar que nenhuma conexão é aberta nos casos negados.
   - Caso permitido em SQLite em memória pode então executar a smoke suite existente.

8. **Critérios de aceite**

   - Todo DDL destrutivo da suíte é precedido pela trava.
   - Casos proibidos encerram pytest com mensagem sanitizada e código diferente de zero.
   - A suíte existente passa usando somente o banco efêmero permitido.
   - Nenhum banco persistente é criado ou alterado.

9. **Rollback**

   Reverter helper e integração com fixtures. Não remover a separação obtida em P0.1 durante rollback parcial; se ambas forem revertidas, continuar proibido executar pytest.

10. **Dependências da tarefa**

   Depende de P0.1. Libera o gate G0 e permite a primeira execução segura dos testes rápidos.

### P0.3 — validação fail-fast de configuração de produção

1. **Objetivo**

   Fazer a aplicação rejeitar, antes de servir requisições, ambientes desconhecidos e configurações inseguras de production.

2. **Risco que resolve**

   Evita inicialização com `APP_ENV=prod` interpretado como desenvolvimento, segredo fraco, hash administrativo ausente/inválido, SQLite ou URL pública não HTTPS.

3. **Arquivos provavelmente afetados**

   - `app/core/config.py`
   - `app/main.py`
   - `app/core/security.py`, apenas se a validação segura do formato Argon2 pertencer ali
   - `.env.example`
   - `tests/test_config.py`
   - `README.md`

4. **Abordagem proposta**

   - Restringir `APP_ENV` a `development`, `test`, `staging` e `production`; valores desconhecidos falham em vez de cair em development.
   - Centralizar validação em `Settings`, evitando checks dispersos na app factory.
   - Em production, exigir:
     - `SESSION_SECRET` não placeholder, com entropia/comprimento mínimo documentado;
     - `ADMIN_PASSWORD_HASH` presente e com formato Argon2 válido;
     - `DATABASE_URL` PostgreSQL;
     - `SITE_URL` HTTPS, absoluto, sem query/fragment e normalizado sem barra final;
     - username administrativo não vazio.
   - Aplicar as propriedades seguras de cookie com base no enum, não em comparação textual aberta.
   - Manter defaults convenientes somente em development; `test` recebe configuração explícita de P0.1.
   - Não registrar valores secretos em exceções ou logs.

5. **Impacto em banco/migration**

   Nenhum schema ou migration. A aplicação poderá recusar URLs SQLite em production, mas nenhuma conexão será aberta para validar os casos negativos.

6. **Impacto em segurança**

   Alto e positivo: converte configuração insegura em erro de startup. Preserva Argon2, CSRF e cookie `Secure`; não reduz controles existentes.

7. **Testes necessários**

   - Matriz de ambientes válidos/inválidos.
   - Um teste negativo para cada requisito de production.
   - Teste positivo com valores fictícios válidos e sem conexão real.
   - Testes de `docs_url`, cookie `Secure` e defaults de development/test.
   - Teste de que exceções não contêm segredo, hash ou password da URL.

8. **Critérios de aceite**

   - Toda grafia de ambiente desconhecida falha no carregamento.
   - Production não inicia com placeholder, segredo curto, hash vazio/malformado, SQLite ou HTTP.
   - Development continua iniciável com defaults documentados.
   - Testes de configuração passam no ambiente isolado de P0.1/P0.2.

9. **Rollback**

   Reverter validadores e documentação em conjunto. Antes do rollback, preservar o bloqueio mínimo atual do segredo default. Nenhum rollback de dados é necessário.

10. **Dependências da tarefa**

   Depende de P0.1 e P0.2 para testar com segurança. Deve terminar antes de construir o ambiente reproduzível definitivo.

### P0.4 — ambiente reproduzível para executar pytest, Ruff e Alembic

1. **Objetivo**

   Fornecer um único fluxo documentado e repetível, em Python 3.12, para lint, testes e validação completa das migrations em PostgreSQL descartável.

2. **Risco que resolve**

   Elimina a validação dependente da máquina local, reduz drift de versões e impede que comandos Alembic sejam apontados por engano para bancos persistentes.

3. **Arquivos provavelmente afetados**

   - `Dockerfile` ou novo `Dockerfile.test`
   - novo `docker-compose.test.yml`
   - `requirements.txt`
   - `requirements-dev.txt`
   - possivelmente novos arquivos de lock/pins, sem ferramenta adicional
   - `Makefile`
   - `alembic.ini` ou configuração de comando, somente se necessário
   - `tests/` para smoke de migration
   - `.gitignore` e `.dockerignore`
   - `README.md` e `docs/TESTING.md`

4. **Abordagem proposta**

   - Criar uma composição de testes separada, com serviço PostgreSQL de nome e banco terminados em `_test`, credenciais exclusivas e storage efêmero/projeto isolado.
   - Garantir que a composição não monte nem reutilize `postgres_data` do ambiente normal.
   - Executar ferramentas em imagem Python 3.12 dedicada, construída somente com dependências já aprovadas.
   - Registrar versões exatas validadas das dependências e da imagem; se pins/hashes exigirem ferramenta nova, solicitar aprovação antes.
   - Adicionar alvos explícitos, por exemplo:
     - `make lint` → `ruff check .`;
     - `make test` → pytest rápido no banco seguro;
     - `make test-integration` → PostgreSQL descartável;
     - `make test-migrations` → `upgrade head`, `downgrade base`, `upgrade head` somente no banco descartável;
     - `make verify` → sequência completa.
   - Aplicar P0.2 antes de cada comando Alembic destrutivo.
   - Não tornar downgrade de produção parte de deploy; ele existe apenas como validação no banco efêmero.

5. **Impacto em banco/migration**

   Nenhuma migration nova. As migrations existentes serão aplicadas e revertidas apenas no PostgreSQL descartável. Nenhum volume normal poderá ser referenciado.

6. **Impacto em segurança**

   Positivo: reduz risco operacional e cadeia de dependências variável. Segredos usados no ambiente de teste serão descartáveis e não commitados.

7. **Testes necessários**

   - `docker compose -f docker-compose.test.yml config --quiet`.
   - Prova automatizada de que a URL/banco/volume de teste diferem dos normais.
   - `ruff check .`.
   - `pytest` rápido e integração PostgreSQL.
   - Alembic `upgrade head → downgrade base → upgrade head`.
   - Verificação de que `alembic current` termina em `20260728_01`.
   - Segunda execução limpa para demonstrar repetibilidade.

8. **Critérios de aceite**

   - Um comando documentado executa a validação completa em Python 3.12.
   - Duas execuções consecutivas produzem o mesmo resultado funcional.
   - Nenhuma etapa solicita ou lê `.env` de production/staging.
   - O banco descartável é identificável pela trava e não reutiliza volumes normais.
   - pytest, Ruff e o ciclo Alembic passam antes de iniciar P1.

9. **Rollback**

   Remover somente manifests/alvos de teste e pins adicionados nesta tarefa, preservando P0.1–P0.3. O ambiente descartável pode ser encerrado e seu volume específico removido apenas por comando explícito e alvo exato; nunca usar limpeza ampla.

10. **Dependências da tarefa**

   Depende de P0.1, P0.2 e P0.3. Conclui o gate G2 e é pré-requisito de todas as tarefas P1.

## 5. Tarefas P1 — segurança e integridade de publicação

### P1.1 — rate limiting e auditoria do login

1. **Objetivo**

   Limitar tentativas inválidas contra a conta administrativa e registrar eventos de autenticação úteis, sem expor credenciais ou criar infraestrutura nova.

2. **Risco que resolve**

   Reduz força bruta ilimitada e ausência de evidência sobre sucesso, falha e bloqueio no login.

3. **Arquivos provavelmente afetados**

   - novo `app/services/authentication.py` ou `app/services/login_protection.py`
   - `app/routes/admin.py`
   - `app/core/config.py`
   - possivelmente `app/core/logging.py`
   - `tests/test_admin.py`
   - novo `tests/test_login_protection.py`
   - `.env.example` e `README.md`

4. **Abordagem proposta**

   - Implementar regra de rate limit fora da rota, com janela e relógio injetável para testes.
   - Contabilizar falhas por IP obtido de `request.client.host`; não confiar diretamente em `X-Forwarded-For` antes de P1.5.
   - Usar armazenamento em memória com TTL, tamanho máximo e limpeza limitada; parâmetros conservadores e configuráveis, com defaults documentados.
   - Retornar HTTP 429 e `Retry-After` quando o limite for excedido, preservando CSRF e verificação Argon2 nos fluxos permitidos.
   - Registrar eventos estruturados `admin_login_succeeded`, `admin_login_failed` e `admin_login_rate_limited`, com timestamp, IP observado, outcome e identificador de tentativa.
   - Nunca registrar password, hash, cookie, sessão, CSRF, URL com credenciais ou corpo do formulário.
   - Documentar que a proteção é por processo e atende ao deployment atual de um Uvicorn; backend compartilhado será obrigatório antes de múltiplas réplicas.

5. **Impacto em banco/migration**

   Nenhum. Contadores e auditoria não serão persistidos no PostgreSQL nesta versão.

6. **Impacto em segurança**

   Alto e positivo. Deve manter mensagens de credenciais genéricas. É necessário limitar a cardinalidade do mapa para evitar DoS de memória.

7. **Testes necessários**

   - Tentativas abaixo e acima do limite, com relógio falso e sem sleeps.
   - Expiração da janela e limpeza de entradas.
   - HTTP 429 e `Retry-After`.
   - IPs distintos isolados e limite global de memória respeitado.
   - Login válido continua funcionando e rotacionando/limpando a sessão como hoje.
   - Captura de logs confirma eventos e ausência de segredos.
   - CSRF inválido continua 403 e não é enfraquecido para facilitar o limiter.

8. **Critérios de aceite**

   - Força bruta repetida recebe 429 de forma determinística.
   - Testes não dependem de tempo real.
   - Logs permitem distinguir sucesso, falha e limitação sem dados sensíveis.
   - O armazenamento é limitado e documentado como single-process.
   - Toda a suíte segura de P0.4 permanece verde.

9. **Rollback**

   Reverter integração do limiter, serviço e settings relacionados. Manter o fluxo original de Argon2, sessão e CSRF; nunca fazer rollback desabilitando esses controles. Remover apenas logs específicos se forem incompatíveis.

10. **Dependências da tarefa**

   Depende de P0.4. P1.5 posteriormente definirá confiança no proxy e tornará o IP observado operacionalmente correto atrás do proxy.

### P1.2 — dependência reutilizável de autenticação admin

1. **Objetivo**

   Substituir checagens manuais repetidas por uma dependência de acesso administrativo negada por padrão.

2. **Risco que resolve**

   Reduz a chance de uma rota administrativa nova ou existente esquecer `is_admin()` e melhora a separação entre HTTP, acesso e regra de negócio.

3. **Arquivos provavelmente afetados**

   - `app/core/security.py` ou novo `app/dependencies/auth.py`
   - `app/routes/admin.py`
   - `tests/test_admin.py`

4. **Abordagem proposta**

   - Criar uma dependência tipada `require_admin` que valide a sessão e negue acesso por default.
   - Preservar a UX SSR atual: acesso não autenticado deve redirecionar por 303 para `/admin/login` sem revelar o recurso.
   - Aplicar a dependência ao dashboard, novo, criar, editar, atualizar, excluir e logout.
   - Manter login GET/POST como únicas rotas administrativas públicas.
   - Autenticação deve ocorrer antes de ler formulário ou acessar banco do recurso.
   - Manter CSRF como controle separado e obrigatório nas mutações; a dependência não o substitui.

5. **Impacto em banco/migration**

   Nenhum.

6. **Impacto em segurança**

   Positivo: centraliza negação por padrão. O principal risco de implementação é mudar sem querer redirects/status ou dispensar CSRF; os testes devem impedir isso.

7. **Testes necessários**

   - Matriz parametrizada com todas as rotas protegidas, métodos e resultado sem sessão.
   - Matriz equivalente com sessão válida.
   - POSTs autenticados sem CSRF continuam 403.
   - Login permanece acessível sem sessão; usuário já autenticado continua redirecionado do login GET.
   - Prova de que requisição não autenticada não consulta nem altera o projeto.

8. **Critérios de aceite**

   - Toda rota protegida declara a mesma dependência reutilizável.
   - Não restam checks manuais duplicados nas rotas protegidas.
   - Somente login GET/POST são públicos sob `/admin`.
   - Sessão e CSRF preservam o comportamento esperado.

9. **Rollback**

   Restaurar checagens explícitas em todas as rotas antes de remover a dependência. Nunca deixar intervalo em que uma rota fique sem ambos os controles.

10. **Dependências da tarefa**

   Depende de P0.4. Deve ser concluída antes de alterar políticas de edição e exclusão em P1.3/P1.4.

### P1.3 — política segura para mudança de slug publicado

1. **Objetivo**

   Garantir estabilidade de URL sem criar prematuramente infraestrutura de redirects.

2. **Risco que resolve**

   Evita que edição administrativa quebre links, sitemap, indexação e referências externas de projetos já criados/publicados.

3. **Arquivos provavelmente afetados**

   - `app/services/projects.py`
   - `app/routes/admin.py`
   - `templates/admin/project_form.html`
   - `tests/test_admin.py`
   - possivelmente novo `tests/test_project_policies.py`
   - `README.md` ou `docs/CMS.md` para registrar a contenção temporária

4. **Abordagem proposta**

   - Tornar o slug imutável após a criação para todos os projetos durante a v0.2.1.
   - Manter slug obrigatório no formulário de criação.
   - Exibir o slug como somente leitura na edição, mas não confiar no HTML.
   - Fazer o serviço comparar o slug persistido com o recebido e rejeitar qualquer diferença antes de mutar outros campos ou abrir commit.
   - Retornar erro de validação amigável na mesma página; não redirecionar e não aplicar atualização parcial.
   - Não permitir bypass por publicar, despublicar ou enviar POST manual.
   - Deixar redirects 301 persistidos para uma versão futura com model, migration e política editorial aprovados.

5. **Impacto em banco/migration**

   Nenhum. Não criar tabela `Redirect`, coluna histórica ou migration nesta estabilização.

6. **Impacto em segurança**

   Positivo para integridade e SEO. A validação obrigatoriamente server-side evita adulteração do formulário. Não muda autenticação ou CSRF.

7. **Testes necessários**

   - Slug definido na criação funciona.
   - Edição de outros campos preserva o slug.
   - Tentativa de mudar slug de draft e published via POST é recusada.
   - Nenhum outro campo é persistido quando o slug diverge.
   - URL antiga continua 200 para published e sitemap permanece igual.
   - Requisição sem admin/CSRF continua negada antes da política.

8. **Critérios de aceite**

   - Não existe caminho administrativo ou de serviço que altere slug após criação.
   - A tentativa retorna erro claro e transação sem mudanças parciais.
   - URLs publicadas permanecem estáveis.
   - Nenhuma migration foi criada.

9. **Rollback**

   Reverter bloqueio no serviço e readonly do template em conjunto. Como nenhum dado é migrado, rollback é somente de código; porém reabrir alteração de slug restaura o risco e não deve ocorrer em produção sem redirects.

10. **Dependências da tarefa**

   Depende de P0.4 e P1.2. A política de exclusão P1.4 deve considerar a mesma decisão de preservação.

### P1.4 — política segura para exclusão de conteúdo publicado

1. **Objetivo**

   Impedir perda definitiva e quebra silenciosa de URLs enquanto não existe histórico de publicação, arquivamento ou redirects.

2. **Risco que resolve**

   Elimina hard delete acidental e o bypass de primeiro despublicar e depois excluir um conteúdo que já teve URL pública.

3. **Arquivos provavelmente afetados**

   - `app/services/projects.py`
   - `app/routes/admin.py`
   - `templates/admin/project_form.html`
   - `tests/test_admin.py`
   - possivelmente `tests/test_project_policies.py`
   - `README.md` ou `docs/CMS.md`

4. **Abordagem proposta**

   - Bloquear hard delete de todos os projetos na v0.2.1, pois o model atual não registra se um draft já foi publicado no passado.
   - Remover a ação de exclusão da interface para não sugerir operação disponível.
   - Manter defesa server-side no endpoint/serviço para POST manual ou cliente antigo, retornando conflito/erro de política sem alterar banco.
   - Registrar tentativa negada em log sem conteúdo sensível.
   - Permitir somente edição e mudança de visibilidade já existente; documentar que despublicar não autoriza exclusão.
   - Projetar archive/soft delete e 301/404/410 somente em tarefa futura, com schema e migration próprios.

5. **Impacto em banco/migration**

   Nenhum. Não criar coluna `archived`, tabela de revisão ou migration. Nenhuma linha será removida.

6. **Impacto em segurança**

   Positivo para integridade e disponibilidade de conteúdo. Autenticação e CSRF continuam obrigatórias mesmo para a operação negada, evitando transformar o endpoint em oracle público.

7. **Testes necessários**

   - UI não exibe botão/form de exclusão.
   - POST direto autenticado e com CSRF é negado e preserva draft/published.
   - POST sem autenticação redireciona; autenticado sem CSRF retorna 403 antes da política.
   - Tecnologias e associações permanecem intactas.
   - Tentativa negada gera log sanitizado.

8. **Critérios de aceite**

   - Nenhuma rota ou serviço executa `db.delete(project)` no fluxo administrativo.
   - Despublicar não habilita exclusão.
   - Tentativas manuais não alteram projeto nem associações.
   - A limitação temporária está documentada.

9. **Rollback**

   Reintroduzir UI e hard delete somente junto de uma política substituta aprovada e testada. Um rollback simples ao comportamento anterior não é seguro para produção, embora não haja rollback de dados desta tarefa.

10. **Dependências da tarefa**

   Depende de P0.4, P1.2 e da decisão de estabilidade de P1.3. Sua remoção do handler inline também facilita CSP estrita em P1.5.

### P1.5 — hardening HTTP, OpenAPI e configuração de proxy

1. **Objetivo**

   Fechar exposição desnecessária, definir a fronteira de confiança com o reverse proxy e aplicar headers seguros sem quebrar SSR/admin.

2. **Risco que resolve**

   Reduz enumeração via OpenAPI, host header abuse, cache indevido do admin, interpretação incorreta de IP/esquema atrás do proxy e ausência de baseline de headers.

3. **Arquivos provavelmente afetados**

   - `app/main.py`
   - `app/core/config.py`
   - possivelmente novo `app/core/http.py` para middleware pequeno e tipado
   - `Dockerfile`
   - `docker-compose.yml`
   - `.env.example`
   - templates, apenas se a CSP revelar inline incompatível
   - novo `tests/test_http_security.py`
   - `tests/test_admin.py`
   - `README.md` e `docs/SECURITY.md`/`docs/DEPLOYMENT.md`

4. **Abordagem proposta**

   - Definir `openapi_url`, `docs_url` e `redoc_url` como `None` em production; mantê-los apenas nos ambientes explicitamente permitidos.
   - Configurar hosts permitidos em setting validado e aplicar `TrustedHostMiddleware`.
   - Adicionar headers no app: CSP compatível com templates, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `frame-ancestors`/proteção de framing e política de permissões mínima.
   - Aplicar `Cache-Control: no-store` a `/admin` e respostas de autenticação.
   - Definir HSTS no reverse proxy somente depois de confirmar HTTPS; não ativá-lo cegamente em development.
   - Tornar explícita a allowlist de proxies confiáveis do Uvicorn (`--forwarded-allow-ips` ou equivalente) e não aceitar forwarded headers de qualquer origem.
   - Documentar quem termina TLS, quais headers o proxy remove/recria e como o IP usado por P1.1 chega ao app.
   - Validar que a CSP não exige `unsafe-inline`; P1.4 remove o único handler inline identificado no formulário de exclusão.

5. **Impacto em banco/migration**

   Nenhum.

6. **Impacto em segurança**

   Alto e positivo. Configuração incorreta de proxy pode causar redirects em loop ou IP errado; por isso a allowlist e os testes de esquema/host são critérios obrigatórios.

7. **Testes necessários**

   - Production: `/docs`, `/redoc` e `/openapi.json` indisponíveis.
   - Development/test: docs somente conforme configuração explícita.
   - Host permitido aceito e host desconhecido rejeitado.
   - Headers esperados em páginas pública e admin.
   - Admin/login com `Cache-Control: no-store`.
   - CSP não quebra CSS, formulários, navegação ou Markdown permitido.
   - Forwarded headers de origem não confiável são ignorados; proxy permitido produz esquema/IP esperados.
   - Rate limit de P1.1 usa o IP correto no cenário atrás do proxy.

8. **Critérios de aceite**

   - OpenAPI e UIs não estão expostos em production.
   - Host/proxy são fail-closed e documentados.
   - Headers não reduzem funcionalidade pública/admin nem sanitização.
   - Nenhuma resposta administrativa autenticada é cacheável.
   - A suíte completa de P0.4 passa com cenários diretos e atrás do proxy.

9. **Rollback**

   Reverter middleware/header individual que cause incompatibilidade, preservando OpenAPI fechado e cookie seguro. Mudanças no proxy e app devem ser revertidas em conjunto para evitar loop ou confiança incorreta. Nunca ampliar forwarded allowlist para `*` como rollback emergencial.

10. **Dependências da tarefa**

   Depende de P0.3, P0.4, P1.1 e P1.4. É a última mudança funcional da estabilização.

## 6. Ordem exata de execução

1. **P0.1 — isolamento seguro do banco de testes.** Fazer apenas a configuração antecipada e o banco efêmero; ainda não executar pytest.
2. **P0.2 — trava anti-produção / anti-staging.** Revisar estaticamente a trava e só então executar os primeiros testes seguros.
3. **P0.3 — validação fail-fast de produção.** Construir e testar a matriz de configuração sem conexão real.
4. **P0.4 — ambiente reproduzível.** Validar Compose de teste, Ruff, pytest e ciclo Alembic no PostgreSQL descartável.
5. **P1.1 — rate limiting e auditoria do login.** Implementar proteção compatível com o processo único atual.
6. **P1.2 — dependência reutilizável de autenticação admin.** Aplicar negação por padrão a todas as rotas protegidas.
7. **P1.3 — slug imutável após criação.** Bloquear alteração server-side e ajustar formulário.
8. **P1.4 — bloqueio de hard delete.** Remover ação da UI e negar operação no servidor.
9. **P1.5 — hardening HTTP/OpenAPI/proxy.** Fechar a superfície e validar o contrato do proxy.
10. **Gate final.** Rodar `make verify` no ambiente descartável, revisar migrations existentes, segurança, SEO, documentação e diff; nenhuma migration nova é esperada por este plano.

Não paralelizar P0.1/P0.2 nem qualquer tarefa que dependa delas. P1.1 e P1.2 poderiam ser desenvolvidas separadamente depois de G2, mas a integração final deve respeitar a ordem acima para reduzir conflitos em `app/routes/admin.py`.

## 7. Primeira mudança de código

A primeira mudança deve ocorrer em `tests/conftest.py`, antes dos imports de `app.*`: definir explicitamente `APP_ENV=test` e substituir a URL ativa pela origem exclusiva de testes, com default SQLite em memória.

Essa alteração deve ser pequena e revisável. **Nenhum pytest deve ser executado logo após ela.** A primeira execução só é autorizada depois que P0.2 adicionar e validar a trava independente imediatamente anterior a qualquer criação, remoção ou migration de schema.

## 8. Critério de conclusão da v0.2.1

A estabilização estará pronta somente quando:

- P0.1–P1.5 atenderem individualmente seus critérios de aceite;
- pytest, Ruff e Alembic passarem no ambiente descartável reproduzível;
- não houver acesso de teste a banco local, staging ou production;
- configuração insegura de production falhar antes do startup;
- rate limit, logs sanitizados, autenticação admin, CSRF e sessão estiverem cobertos;
- slugs não puderem mudar após criação e nenhum projeto puder sofrer hard delete;
- OpenAPI estiver fechado em production e o contrato de proxy/headers estiver documentado e testado;
- nenhuma migration nova tiver sido criada sem necessidade de schema;
- o diff não contiver funcionalidades futuras nem alterações fora deste plano.

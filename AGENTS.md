# AGENTS.md

## Produto

`rennam.dev` é um laboratório público de AI Data Engineering, portfólio técnico, blog multilíngue, mini CMS e gateway controlado para demonstrações privadas de Labs.

## Fase atual

Fundação v0.2.1 estabilizada, com remediações R1–R3 confirmadas e preparação
para publicação do repositório. A base está pronta para evolução funcional,
mas não está classificada como pronta para produção. A v0.3 ainda não começou.

Não implemente funcionalidades futuras sem tarefa explícita e aprovação do plano.

## Arquitetura aprovada

- Monólito modular para site público, CMS, autenticação e portal.
- FastAPI, Jinja2, HTMX, PostgreSQL, SQLAlchemy 2 e Alembic.
- Renderização no servidor para conteúdo público.
- Autenticação web por sessão segura, Argon2 e CSRF.
- Labs pesados e serviços de IA permanecem separados do CMS.
- O navegador nunca chama provedores de LLM diretamente.

## Método de trabalho

1. Leia a documentação relevante antes de modificar código.
2. Inspecione arquivos e comportamento atual.
3. Apresente um plano curto, com arquivos, riscos e testes.
4. Faça apenas a alteração aprovada e dentro do escopo.
5. Execute validações não destrutivas relevantes.
6. Informe arquivos alterados, comandos executados e riscos restantes.
7. Não faça commit, push, merge ou rebase sem autorização explícita.

## Limites de segurança

- Nunca exponha segredos, chaves de LLM ou credenciais.
- Nunca apague migrations existentes.
- Nunca faça reset ou drop de banco.
- Nunca use comandos destrutivos como `git reset --hard`, `git clean -fd` ou `rm -rf`.
- Nunca reduza autenticação, autorização, CSRF, rate limit ou quotas para facilitar testes.
- Nunca publique rascunhos, previews, admin ou conteúdo privado no sitemap.
- Dependências novas exigem justificativa e aprovação.

## Banco e migrations

- Toda alteração de schema exige migration Alembic.
- Models, constraints, índices e migrations devem permanecer coerentes.
- Não armazene arquivos binários grandes no PostgreSQL.
- Downgrade deve existir quando for seguro e prático.

## Qualidade

- Use type hints.
- Rotas tratam HTTP; serviços tratam regras; repositórios tratam persistência.
- Evite abstrações especulativas e refatorações fora do escopo.
- Mudanças de comportamento exigem testes.
- Não alegue que testes passaram sem executá-los.

## SEO e conteúdo

- Conteúdo público deve ser renderizado no servidor.
- URLs publicadas devem ser estáveis e localizadas.
- Alteração de slug publicado deve preservar redirecionamento.
- Conteúdo privado, rascunho e `noindex` não entra no sitemap.
- PT-BR e inglês podem ter estados de publicação independentes.

## Definição de pronto

Uma tarefa só está concluída quando:

- o comportamento solicitado foi implementado;
- testes relevantes passaram;
- migrations estão coerentes, se aplicável;
- segurança e SEO foram preservados;
- documentação foi atualizada quando necessário;
- o diff não contém alterações alheias à tarefa.

# Brief para revisão arquitetural — rennam.dev

> **Status:** documento fundacional vivo alinhado à v0.3.0. A Fundação modular
> está concluída; a exclusão definitiva permanece bloqueada e os recursos
> listados em “Fora do escopo” continuam planejados, não implementados.

## Decisão central

O `rennam.dev` é o **Projeto 0**: portfólio, laboratório público e plataforma
que apresenta os demais projetos. Não é o primeiro projeto de AI Data
Engineering e não deve incorporar a lógica dos projetos de IA.

## Objetivo atual

Substituir o catálogo fixo em arquivos Python por um mini-CMS autoral com:

- FastAPI;
- Jinja2;
- HTML e CSS próprios;
- PostgreSQL;
- SQLAlchemy 2.0;
- Alembic;
- autenticação por sessão;
- gestão administrativa de projetos, sem hard delete;
- conteúdo longo em Markdown sanitizado.

## Usuários

- Visitante: acessa apenas projetos publicados.
- Administrador: apenas Rennam; cadastra, edita e publica projetos. A exclusão
  definitiva está bloqueada até existir uma política segura de arquivamento e
  restauração.

Não haverá cadastro público, múltiplos usuários, papéis ou permissões nesta
fase.

## Entidade principal

`Project` contém:

- título e slug;
- resumo;
- problema;
- solução;
- arquitetura;
- decisões técnicas;
- resultados;
- aprendizados;
- disciplina/origem;
- status;
- rascunho/publicado;
- destaque na Home;
- tecnologias em relação N:N;
- GitHub, demonstração e capa;
- descrição SEO;
- datas de criação e atualização.

## Segurança escolhida

- sessão assinada em cookie `HttpOnly`;
- `SameSite=Lax`;
- `Secure` em staging e production;
- CSRF nas requisições de escrita;
- hash Argon2 da senha;
- segredo e hash somente no `.env`;
- Markdown convertido e sanitizado.

JWT foi descartado para o painel porque não existe SPA nem cliente externo.

## Limites do MVP

Fora do escopo:

- Taskni como primeiro estudo de caso;
- CRUD de artigos;
- upload de imagens;
- editor visual;
- comentários;
- analytics;
- múltiplos administradores;
- permissões;
- plugins ou temas;
- execução interna dos projetos de IA.

## Primeiro projeto apresentado

**Rennam Semantic Docs**:

1. ingestão de documentos próprios ou públicos;
2. extração e limpeza;
3. chunking;
4. geração de embeddings;
5. armazenamento no PostgreSQL com pgvector;
6. busca semântica;
7. avaliação de relevância e latência;
8. somente depois, geração de respostas com fontes.

Os PDFs comerciais da formação DSA não serão publicados nem usados na
demonstração pública.

## Perguntas úteis para a revisão

1. A separação entre rotas, serviços, repositórios e modelos está proporcional
   ao tamanho do projeto?
2. Há vulnerabilidades concretas no fluxo de sessão, CSRF ou renderização de
   Markdown?
3. A modelagem atual suporta os estudos de caso sem virar um CMS genérico?
4. Quais mudanças são realmente necessárias antes do primeiro deploy e quais
   podem esperar?
5. Há alguma complexidade que pode ser removida sem enfraquecer o valor de
   portfólio?

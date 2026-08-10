# Arquitetura

## Estilo

Monólito modular para o site público, CMS, identidade e portal. Labs de IA permanecem isolados quando exigirem dependências, bancos, escala ou ciclos de deploy próprios.

## Visão lógica

```text
Internet
   ↓
Reverse proxy / HTTPS
   ↓
FastAPI
   ├── Site público SSR
   ├── Mini CMS administrativo
   ├── Portal privado
   └── Lab Gateway
          ↓
      Serviços de domínio
          ↓
      Repositórios
          ↓
      PostgreSQL
```

## Integração com Labs

```text
Usuário autenticado
   ↓
rennam.dev valida sessão, permissão, validade e quota
   ↓
Gateway chama API interna do Lab
   ↓
Lab executa busca, RAG ou LLM
   ↓
Uso, tokens, custo e latência são registrados
```

## Responsabilidades

- **Rotas:** HTTP, formulários, status e dependências de acesso.
- **Serviços:** regras de negócio, orquestração e fronteira transacional.
- **Repositórios:** consultas e persistência ORM, sem encerrar transações.
- **Templates:** apresentação server-side.
- **PostgreSQL:** conteúdo, identidade, permissões, auditoria e metadados.
- **Storage de objetos:** mídia em produção.

## Fronteira transacional

```text
route (HTTP, auth, CSRF e resposta)
  → service (regras, commit, rollback e tradução de conflitos)
    → repository (select, add e flush)
      → SQLAlchemy / PostgreSQL
```

Cada comando de escrita possui um único `commit` no service. O service executa
`rollback` tanto para conflitos de persistência quanto para erros inesperados
após mutação; `IntegrityError` é convertido em exception específica do domínio.
Repositories nunca executam `commit` ou `rollback`, e routes não tratam
exceptions de persistência do SQLAlchemy.

## Restrições

- Sem chaves de LLM no cliente.
- Sem acesso público direto às APIs internas dos Labs.
- Sem lógica de negócio relevante em templates.
- Sem dependência nova sem decisão registrada.

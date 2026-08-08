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
- **Serviços:** regras de publicação, autorização, quotas e negócio.
- **Repositórios:** consultas e persistência.
- **Templates:** apresentação server-side.
- **PostgreSQL:** conteúdo, identidade, permissões, auditoria e metadados.
- **Storage de objetos:** mídia em produção.

## Restrições

- Sem chaves de LLM no cliente.
- Sem acesso público direto às APIs internas dos Labs.
- Sem lógica de negócio relevante em templates.
- Sem dependência nova sem decisão registrada.

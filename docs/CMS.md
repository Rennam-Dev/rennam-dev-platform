# Mini CMS

## Objetivo

Oferecer uma experiência administrativa semelhante ao essencial do WordPress, mas orientada ao domínio do `rennam.dev`.

## Módulos planejados

- Dashboard.
- Artigos e Engineering Journal.
- Projetos.
- Labs e arquiteturas.
- Roadmap e páginas institucionais.
- Categorias, tags e tecnologias.
- Biblioteca de mídia.
- Usuários, convites e configurações.

## Workflow editorial

```text
draft → coming_soon / scheduled → published → maintenance / archived
```

## Campos de artigo

Título, slug, resumo, conteúdo, capa, categoria, tags, idioma, SEO title, meta description, Open Graph, status e datas.

## Campos de projeto

Título, resumo, problema, objetivo, solução, arquitetura, fluxo de dados, tecnologias, decisões, desafios, resultados, métricas, aprendizados, limitações, próximos passos, GitHub e demo.

## Regras

- Preview privado antes da publicação.
- Traduções podem ter estados diferentes.
- Na v0.2.1, o slug de todo projeto é imutável após a criação para preservar URLs.
- Uma versão futura com histórico e redirects permitirá renomeação segura de slug.
- Hard delete de projetos está desabilitado na v0.2.1 para evitar perda
  irreversível e quebra de URLs.
- Arquivamento, soft delete e restauração serão projetados em versão futura.
- Rascunhos e previews nunca aparecem publicamente ou no sitemap.

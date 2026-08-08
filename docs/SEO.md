# SEO

## Objetivo

Garantir rastreabilidade, indexação correta e base técnica para crescimento orgânico, sem substituir a necessidade de conteúdo autoral e útil.

## Fundamentos

- Renderização server-side com HTML semântico.
- URLs localizadas: `/pt-br/` e `/en/`.
- Canonical próprio por página.
- `hreflang` apenas entre traduções existentes e equivalentes.
- Sitemap apenas com conteúdo publicado, acessível e indexável.
- `robots.txt` não substitui autenticação nem `noindex`.
- Redirect 301 ao alterar slug publicado.
- 404, 403, 429, 500 e 503 reais.
- JSON-LD para Article/BlogPosting, BreadcrumbList, Person e WebSite quando aplicável.
- Open Graph e imagens otimizadas.

## Conteúdo privado

A página pública do Lab pode ser indexada. A demo, o portal, admin, previews e APIs internas devem permanecer protegidos e fora do índice.

## Status editoriais

- `draft`: privado.
- `coming_soon`: `noindex` se não houver conteúdo substancial.
- `published`: indexável conforme configuração.
- `maintenance`: 503 somente durante indisponibilidade temporária real.
- `archived`: oculto; política de 301, 404 ou 410 definida caso a caso.

## Monitoramento

Google Search Console, Bing Webmaster Tools, Core Web Vitals, erros de rastreamento, sitemap e links internos.

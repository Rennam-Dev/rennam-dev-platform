# Modelo de Dados

## Estado atual

A v0.3.0 mantém os modelos de projetos e tecnologias, sem migration nova na
Fundação modular. Article, Category e Tag permanecem planejados para a v0.4.0.

## Entidades planejadas

- User, Role, Permission e Invitation.
- Article, ArticleTranslation, Category e Tag.
- Project, ProjectTranslation e Technology.
- Lab, LabTranslation, LabAccess e UsageEvent.
- Page, PageTranslation e MediaAsset.
- Redirect, ContentRevision, AuditLog e SiteSetting.

## Relações principais

```text
Article 1 ── N ArticleTranslation
Project 1 ── N ProjectTranslation
Project N ── N Technology
User N ── N Role
User 1 ── N LabAccess
Lab 1 ── N LabAccess
Lab 1 ── N UsageEvent
```

## Princípios

- Constraints e índices explícitos.
- Tradução separada de metadados invariantes.
- Auditoria e revisão não substituem backups.
- Exclusões com impacto devem ter política definida: restrição, soft delete ou cascade controlado.

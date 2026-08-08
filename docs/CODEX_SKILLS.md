# Codex Skills

## Conceito

Codex Skills são pacotes modulares de instruções para automatizar fluxos no Codex CLI e na API. Skills dizem ao agente **como trabalhar**; um MCP Gateway fornece ferramentas e acesso seguro para executar ações externas.

O Composio MCP Gateway declara oferecer um endpoint MCP único para mais de 1.000 integrações, com autenticação, controles de acesso de equipe, logs de auditoria e recursos voltados a produção. Sua adoção não faz parte do MVP e exige avaliação de segurança, privacidade, custo e dependência.

## Instalação recomendada

```bash
git clone https://github.com/ComposioHQ/awesome-codex-skills.git
cd awesome-codex-skills
python skill-installer/scripts/install-skill-from-github.py \
  --repo ComposioHQ/awesome-codex-skills \
  --path meeting-notes-and-actions
```

O instalador coloca a skill em `$CODEX_HOME/skills/<skill-name>`, normalmente `~/.codex/skills/<skill-name>`. Reinicie o Codex após instalar ou atualizar.

## Instalação manual

Copie a pasta da skill para `$CODEX_HOME/skills/`, reinicie o Codex e descreva a tarefa normalmente ou cite o nome da skill. O frontmatter `description` é usado para decidir quando ativá-la.

## Política do projeto

- Não instalar tudo do catálogo.
- Revisar `SKILL.md`, scripts, permissões, rede e credenciais.
- Skills externas são código de terceiros.
- Nenhuma skill pode fazer commit, push, deploy, instalação de dependência ou ação destrutiva sem aprovação.
- `AGENTS.md` e decisões do projeto prevalecem sobre automações comunitárias.

## Seleção planejada

Primeira fase: `create-plan`, `codebase-recon` (se houver histórico suficiente) e `webapp-testing` depois da estabilização.

Com CI/PRs: `gh-fix-ci`, `gh-address-comments` e `changelog-generator`.

Após deploy: `sentry-triage`.

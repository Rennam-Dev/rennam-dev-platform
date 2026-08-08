# Labs

## Estrutura

Cada Lab possui duas superfícies:

1. Página pública indexável com problema, arquitetura, stack, resultados e solicitação de acesso.
2. Aplicação privada com autenticação, autorização, validade, quota e auditoria.

## Acesso

Convites individuais são preferidos a uma senha demo pública compartilhada.

```text
Convite → criação de senha → portal → Lab autorizado → quota → execução
```

## Controle de custo

Cada Lab pode definir limite por usuário, período, tokens e orçamento financeiro. Usuário autenticado não significa uso ilimitado.

## Separação

O CMS não incorpora toda a lógica do Lab. Ele atua como identidade, catálogo, portal e gateway. Serviços internos usam autenticação entre serviços e rede restrita.

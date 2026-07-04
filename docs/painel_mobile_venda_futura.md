# Painel Mobile - venda futura pelo app

Este documento prepara o caminho para uma futura venda pelo aplicativo, sem ativar venda agora.

## Estado atual

- O painel mobile e somente leitura.
- A tela consulta `/api/status` e `/api/vendas`.
- Nenhuma regra de venda, estoque, financeiro, baixa de estoque ou banco local do desktop foi alterada.
- A area "Nova Venda em breve" existe apenas como aviso discreto na interface.

## Endpoints que seriam necessarios

Para vender pelo app com seguranca, a proxima etapa deve definir endpoints separados e validados:

- `GET /api/produtos?limite=...`: listar produtos ativos, preco e estoque disponivel.
- `GET /api/clientes?limite=...`: buscar cliente existente.
- `POST /api/clientes`: criar cliente quando necessario.
- `POST /api/vendas/preview`: calcular subtotal, desconto, taxa e total sem gravar nada.
- `POST /api/vendas/mobile`: criar venda mobile com validacao de estoque e permissao do usuario.
- `GET /api/vendas/{id}`: consultar venda criada e itens.

## Regras obrigatorias antes de implementar

- Reutilizar as mesmas regras de calculo do desktop.
- Validar estoque no servidor antes de confirmar.
- Baixar estoque somente dentro de transacao.
- Registrar vendedor/login da sessao.
- Impedir venda duplicada por idempotencia.
- Registrar origem `mobile`.
- Manter sincronizacao com o desktop sem sobrescrever dados locais.

## Observacao tecnica

A tela atual nao chama `POST /api/vendas` e nao possui botao ativo para finalizar venda. Qualquer venda futura deve ficar em modulo separado, com testes proprios e revisao das regras de estoque.

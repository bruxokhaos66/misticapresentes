# Documentos do Admin

Esta pasta concentra planos e documentos operacionais relacionados ao Admin, pedidos, Pix, pagamentos, status, backend, estoque, produtos, uploads e integracao.

## Documentos movidos da raiz

- `BACKEND_ADMIN_PLANO.md` — plano tecnico para Admin seguro e banco de dados.
- `PEDIDOS_BACKEND_ADMIN.md` — painel de pedidos conectado ao backend.
- `STATUS_PEDIDOS_BACKEND.md` — status de pedidos salvo no backend.
- `PEDIDOS_PIX_ADMIN.md` — acompanhamento de pedidos e confirmacao manual de Pix.
- `PIX_BACKEND.md` — registro de pagamentos Pix no backend.
- `INTEGRACAO_PROGRAMA_SITE.md` — integracao entre programa da loja, API e site.
- `ISIS_API.md` — Isis comercial conectada aos produtos da API.
- `BAIXA_ESTOQUE_PEDIDOS.md` — baixa controlada de estoque por status de pedido.
- `BAIXA_MANUAL_ESTOQUE.md` — baixa manual de estoque pelo Admin.
- `PRODUTOS_API_ADMIN.md` — cadastro completo de produtos pela API e Admin.
- `UPLOAD_IMAGENS_PRODUTOS.md` — upload real de imagens de produtos.
- `BACKUP_MONITORAMENTO_DEPLOY.md` — backup automático fora do Render, monitoramento com UptimeRobot, rollback manual de deploy e auditoria periódica automatizada.
- `ISIS_CHAT_HOMOLOGACAO.md` — homologação controlada do chat inteligente da Isis 2.0 (recomendação de produtos, modo determinístico, flags, limites, painel admin).

## Regra daqui para frente

- Novos documentos de Admin devem entrar nesta pasta.
- Relatorios de auditoria continuam em `docs/auditorias/`.
- A raiz do repositorio deve ficar reservada para arquivos essenciais.

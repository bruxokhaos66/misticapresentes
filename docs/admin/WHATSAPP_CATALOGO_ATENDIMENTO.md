# Catálogo Comercial na Central de Atendimento (PR #408)

Esta é a terceira etapa da Central de Atendimento WhatsApp, depois de
`docs/WHATSAPP_CLOUD_API.md` (Cloud API e Central original,
administrador-apenas) e `docs/admin/WHATSAPP_ATENDIMENTO_MULTIATENDENTE.md`
(fila, assunção, transferência). Aqui documentamos o Catálogo Comercial:
pesquisa de produtos reais da loja e envio comercial (imagem + nome + preço
+ link) pelo WhatsApp.

**Fora do escopo desta etapa** (ficam para PRs futuras): IA, PWA,
notificações push, WebSocket/SSE, dashboard avançado, comissões, automação
de campanhas, carrinho/pedido dentro da Central (o envio é apenas
comercial/informativo).

## 1. Finalidade

Permitir que o atendente pesquise produtos reais do catálogo da loja (a
mesma tabela `produtos` usada pelo site e pelo painel administrativo — nunca
uma segunda fonte de catálogo), selecione um ou vários itens e envie ao
cliente pelo WhatsApp com imagem oficial, nome, preço atual e link seguro
para a página do produto.

## 2. Flag

`ATENDIMENTO_CATALOG_ENABLED` (padrão `false`) — interruptor mestre. Com a
flag desligada:

- todas as rotas de `/api/admin/whatsapp/catalog/*` e
  `/api/admin/whatsapp/conversations/{id}/send-product(s)` devolvem `503`;
- o painel "Produtos" **não aparece** na Central (o frontend faz uma
  checagem silenciosa no carregamento e só exibe o botão se o backend
  confirmar que o catálogo está disponível — nunca decide isso sozinho);
- nenhuma chamada extra de catálogo é feita pelo frontend.

Também depende de `WHATSAPP_CLOUD_ENABLED=true` (a Central de Atendimento
em si precisa estar habilitada e configurada).

Flags complementares:

- `ATENDIMENTO_CATALOG_MAX_PRODUCTS_PER_SEND` (padrão `5`, máx. `10`) —
  limite de produtos por envio em lote.
- `ATENDIMENTO_CATALOG_LOW_STOCK_THRESHOLD` (padrão `3`) — quantidade em
  estoque igual ou abaixo deste valor aparece como "Estoque baixo" em vez de
  "Disponível" (a quantidade exata nunca é exposta ao atendente).

## 3. Permissões

Mesmos perfis e mesma revalidação no banco da Central Multiatendente —
`backend/atendimento_repository.py::exigir_atendente`/
`autorizado_para_conversa`, nunca confia no perfil cacheado na sessão nem em
botão escondido no frontend:

| Ação | adm | supervisor_atendimento | vendedor |
|------|:---:|:-----------------------:|:--------:|
| Pesquisar catálogo | ✅ | ✅ | ✅ |
| Ver recentes | ✅ | ✅ | ✅ (só os próprios) |
| Enviar produto em conversa própria/atribuída | ✅ | ✅ | ✅ |
| Enviar produto em conversa de outro | ✅* | ✅* | ❌ |

`*` mesma regra de `ATENDIMENTO_REQUIRE_ASSIGNMENT_FOR_ADMIN` já usada pelo
envio de texto.

Usuário inativo, suspenso (`atendimento_suspended_at`) ou com
`atendimento_enabled=0` nunca acessa o catálogo — checado no banco a cada
chamada, nunca só na sessão.

## 4. Busca

`GET /api/admin/whatsapp/catalog/products`

Parâmetros: `q`, `categoria`, `marca`, `ativo` (padrão `true`),
`em_estoque` (padrão `false`), `page`, `page_size` (máx. 60).

- Pesquisa por nome, SKU/código, categoria, marca, descrição e selo
  (`backend/whatsapp_catalog_repository.py::buscar_produtos_catalogo`).
- Case-insensitive (`COLLATE NOCASE`), tolera espaços extras (normalizados
  antes da busca) e escapa `%`/`_`/`\` para nunca virar um wildcard abusivo.
- Paginação obrigatória com limite seguro de `page_size`.
- Ordenação estável: ativos primeiro, com estoque primeiro, depois nome.
- Nunca faz `SELECT *`, nunca consulta imagem/categoria por item (uma única
  query paginada) e nunca aceita SQL concatenado — todo parâmetro do `LIKE`
  é passado via bind.

`GET /api/admin/whatsapp/catalog/recent-products` — produtos recentemente
enviados por este atendente (derivado do histórico de envio, nunca uma
segunda tabela de "produtos recentes"). Preço e estoque são sempre
revalidados na consulta atual; produtos inativos nunca são oferecidos para
reenvio.

## 5. Dados devolvidos

Só o necessário: `id, nome, sku, categoria, marca, preco,
preco_promocional, moeda, estoque_status, imagem_url, url_publica, ativo,
disponivel`. Nunca custo, lucro, fornecedor ou qualquer campo
administrativo. Estoque é normalizado em `available` / `low_stock` /
`unavailable` (`estoque_status`) — a quantidade exata nunca é exposta.

## 6. Formação do link e da imagem

- URL pública: sempre gerada pelo backend
  (`backend/isis_chat_catalog.py::produto_url`, a mesma função já usada pelo
  Chat da Isis — nunca uma segunda implementação desse padrão), a partir do
  domínio da nossa allowlist (`backend/api_security.py::ORIGENS_PERMITIDAS`)
  ou do `link_externo` já cadastrado no produto. Nunca aceita uma URL vinda
  do navegador.
- Imagem: usa `produtos.imagem_url` (já uma URL HTTPS pública, validada no
  cadastro do produto por `backend/product_routes.py::_validar_url_https`).
  Sem imagem, o card mostra um estado "Sem imagem" e o envio nunca é
  bloqueado por isso — o texto comercial é enviado mesmo assim.
- Envio da imagem: `WhatsAppProvider.send_inbox_image` (novo método em
  `backend/whatsapp_provider.py`) manda a imagem por **link direto**
  (`type: image, image: {link, caption}` da Cloud API) — a Meta busca a
  imagem na URL informada, sem baixar/reenviar mídia pelo nosso servidor e
  sem duplicar armazenamento (reaproveita a mesma URL pública já usada pelo
  site).

## 7. Envio único

`POST /api/admin/whatsapp/conversations/{id}/send-product`

Corpo: `product_id`, `assignment_version` (opcional), header
`Idempotency-Key` (escopo próprio `whatsapp_catalog_send_product`, nunca
colide com o de envio de texto).

O backend busca o produto **de novo** pelo ID — nunca confia em
nome/preço/imagem/estoque/URL vindos do frontend. Antes de enviar, valida:
sessão, perfil, acesso à conversa, conversa aberta, atribuição
(multiatendente), janela de atendimento de 24h da Meta, produto ativo,
produto disponível (estoque ou sob encomenda), URL pública válida,
`Idempotency-Key` (clique duplo/retry nunca duplicam o envio),
`assignment_version` (conflito de versão → `409`).

Produto indisponível/inativo é **bloqueado por padrão** (nunca inventa
estoque nem envia produto inativo) — registrado como
`unavailable_product_blocked` no histórico.

## 8. Envio em lote

`POST /api/admin/whatsapp/conversations/{id}/send-products`

Corpo: `product_ids` (até `ATENDIMENTO_CATALOG_MAX_PRODUCTS_PER_SEND`, IDs
únicos), `assignment_version`, `Idempotency-Key` (escopo
`whatsapp_catalog_send_products_batch`).

Todo produto do lote é revalidado no backend **antes** de qualquer envio —
se um for inválido (inativo/indisponível/inexistente), a requisição inteira
falha (`422`/`404`/`409`) sem enviar nenhum produto do lote (nunca deixa
metade enviada por erro de outro item). Depois de iniciados os envios, cada
produto é registrado individualmente (sucesso ou falha), e um retry com a
mesma `Idempotency-Key` devolve a mesma resposta salva, sem duplicar nada.

## 9. Mensagem comercial

`backend/whatsapp_catalog_repository.py::montar_texto_comercial` — função
central, nunca aceita texto arbitrário do frontend, sempre reconstrói a
partir dos dados já validados do backend. Moeda brasileira, disponibilidade
normalizada, link clicável, tamanho limitado a 1024 caracteres (limite de
legenda de mídia da Cloud API), sem HTML.

## 10. Histórico e auditoria

Tabela `whatsapp_catalog_sends` (append-only, migração aditiva em
`database/migrations.py::_criar_estrutura_catalogo_atendimento`):
`conversation_id, product_id, message_id, performed_by_user_id, action,
price_at_send, status, idempotency_key_hash, created_at`. Ações:
`product_sent`, `product_batch_sent`, `product_send_failed`,
`unavailable_product_blocked`. Nunca grava token, `Authorization`, payload
bruto da Meta, telefone completo, imagem binária ou segredo. Complementa
(não substitui) a auditoria genérica (`backend/audit.py::registrar_auditoria`,
ações `enviar_produto`/`enviar_produtos_lote`/`enviar_produto_falhou`).

## 11. Roteiro de teste manual

1. Deploy com `ATENDIMENTO_CATALOG_ENABLED=false` — validar que a Central
   continua idêntica (sem o botão "Produtos").
2. Ativar a flag em homologação.
3. Abrir uma conversa atribuída dentro da janela de 24h.
4. Pesquisar um produto real (nome, depois SKU, depois categoria).
5. Selecionar um produto e enviar — confirmar imagem, texto, preço e link
   recebidos no WhatsApp; abrir o link e confirmar que aponta para a página
   real do produto.
6. Selecionar vários produtos (até o limite) e enviar em lote.
7. Repetir o clique de envio (ou reenviar a mesma requisição) e confirmar
   que não duplica mensagem nem histórico.
8. Tentar enviar um produto inativo/sem estoque e confirmar bloqueio.
9. Validar em mobile (drawer responsivo, seleção por toque, botão de
   enviar sempre visível).
10. Conferir `whatsapp_catalog_sends` e `audit_log` — sem segredo, sem
    payload bruto.

## 12. Rollout

- Etapa A — deploy com a flag desligada, validar que nada mudou.
- Etapa B — ativar só para `adm`, testar um produto/imagem/link reais.
- Etapa C — ativar para um vendedor, testar conversa atribuída e lote de
  até 3 produtos.
- Etapa D — liberar para toda a equipe.

## 13. Rollback

`ATENDIMENTO_CATALOG_ENABLED=false` + reiniciar o serviço: o painel
"Produtos" desaparece e as rotas comerciais voltam a `503`. Conversas,
mensagens e histórico existentes permanecem intactos — nunca apaga a
migração nem a auditoria (`whatsapp_catalog_sends` continua existindo,
apenas para de crescer).

## 14. Limitações desta etapa

- Sem carrinho/pedido — o envio é apenas comercial/informativo.
- Sem favoritos (deixado para uma PR futura, para não aumentar o escopo
  desta etapa).
- Sem IA, PWA, notificações push, WebSocket/SSE, dashboard avançado,
  comissões ou automação de campanhas.

# Produtos completos na API e Admin

Esta fase transforma o cadastro de produto em uma operação real de API/backend.

## Recursos adicionados

- Novo router `backend/product_routes.py`.
- Produto completo com:
  - nome;
  - código;
  - preço;
  - estoque;
  - categoria;
  - descrição;
  - imagem principal;
  - galeria de imagens;
  - link externo/parceiro;
  - selo comercial.

## Endpoints

```http
GET /api/produtos
POST /api/produtos
PUT /api/produtos/{produto_id}
DELETE /api/produtos/{produto_id}
```

## Admin

Novo arquivo:

```text
admin-product-api.js
```

O Admin agora pode:

- salvar produto na API;
- editar produto da API;
- excluir produto da API;
- recarregar produtos;
- sincronizar a vitrine após salvar.

## Site

O `mobile-sync.js` agora entende os campos completos da API:

- `descricao`
- `imagem_url`
- `imagens`
- `link_externo`
- `selo`

Assim, quando a API estiver online, a vitrine usa os produtos reais do banco.

## Como testar

1. Subir o backend.
2. Abrir o site com `?admin=mistica`.
3. Entrar no Admin.
4. Cadastrar produto com descrição, selo e imagem.
5. Clicar em `Salvar na API`.
6. Recarregar produtos.
7. Editar produto da API.
8. Excluir produto da API.
9. Verificar se a vitrine atualiza após sincronizar.

## Observações

- A exclusão é lógica: `ativo=0`.
- Se `MISTICA_SITE_API_KEY` estiver configurada, POST/PUT/DELETE exigem `X-Mistica-Api-Key`.
- A próxima fase recomendada é conectar pedidos 100% ao backend.

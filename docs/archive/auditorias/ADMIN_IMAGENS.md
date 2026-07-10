# Fase 7 - Upload visual de imagem no Admin

Esta fase adiciona no Admin uma área visual para enviar imagem de produto para a API.

## Recursos adicionados

- Novo arquivo `admin-image-upload.js`.
- Carregamento automático pelo catálogo.
- Área dentro do cadastro de produtos:
  - selecionar imagem;
  - pré-visualizar imagem;
  - enviar para API;
  - copiar URL gerada;
  - inserir URL automaticamente no campo de imagens.

## Fluxo

1. Admin acessa `?admin=mistica`.
2. Entra no painel.
3. Abre o cadastro de produto.
4. Escolhe uma imagem JPG, PNG ou WEBP.
5. Clica em `Enviar imagem`.
6. A imagem é enviada para:

```http
POST /api/uploads/produtos
```

7. A API retorna a URL.
8. O site adiciona a URL ao campo de imagens do produto.
9. O Admin salva o produto.

## Segurança

Se `siteApiKey` estiver configurada em `site-config.js`, o upload envia o header:

```http
X-Mistica-Api-Key
```

A chave real não deve ser colocada em repositório público.

## Limites

- JPG, PNG ou WEBP.
- Até 4 MB.

## Como testar

1. Subir a API com a rota de upload ativa.
2. Abrir o site com `?admin=mistica`.
3. Entrar no Admin.
4. No cadastro de produto, selecionar uma imagem.
5. Conferir a prévia.
6. Clicar em `Enviar imagem`.
7. Verificar se a URL aparece no campo de imagens.
8. Salvar o produto.
9. Conferir se a imagem aparece no card e na página do produto.

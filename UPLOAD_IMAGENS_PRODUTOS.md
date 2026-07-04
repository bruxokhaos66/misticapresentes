# Fase 6 - Upload real de imagens de produtos

Esta fase prepara o backend para receber imagens reais de produtos.

## Recursos adicionados

- Novo arquivo `backend/upload_routes.py`.
- Nova rota:

```http
POST /api/uploads/produtos
```

- Pasta pública de uploads:

```text
/uploads/produtos
```

- Arquivos são salvos em:

```text
backend/uploads/produtos
```

- O backend agora serve arquivos estáticos em `/uploads`.
- Dependência adicionada:

```text
python-multipart
```

## Formatos aceitos

- JPG
- PNG
- WEBP

## Limite

- Máximo de 4 MB por imagem.

## Segurança

A rota usa a variável de ambiente:

```text
MISTICA_SITE_API_KEY
```

Quando configurada, deve receber o header:

```http
X-Mistica-Api-Key
```

## Exemplo de teste com curl

```bash
curl -X POST "http://localhost:8000/api/uploads/produtos?produto_id=incenso-natural" \
  -H "X-Mistica-Api-Key: SUA_CHAVE" \
  -F "arquivo=@foto-produto.webp"
```

Resposta esperada:

```json
{
  "ok": true,
  "filename": "incenso-natural-abc123.webp",
  "content_type": "image/webp",
  "size_bytes": 123456,
  "url": "/uploads/produtos/incenso-natural-abc123.webp"
}
```

## Próximo passo recomendado

Adicionar no Admin um campo de upload visual para enviar a foto e preencher automaticamente a URL da imagem do produto.

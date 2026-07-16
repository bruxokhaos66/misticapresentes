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

- O backend serve arquivos estáticos em `/uploads`.
- Dependência adicionada:

```text
python-multipart
```

## Persistência real (leia antes de mexer aqui)

O disco dos serviços web do Render é **efêmero** fora do disco persistente
montado em `/data` (ver `render.yaml`). Gravar uploads em
`backend/uploads/produtos` -- dentro do código da aplicação -- fazia as
imagens desaparecerem no deploy seguinte, mesmo com a URL continuando salva
no banco (causa raiz de imagens "sumindo" depois de algum tempo).

Toda a gravação/remoção agora passa por uma única camada,
`backend/product_image_storage.py` (`ProductImageStorage`), com dois modos:

- **Storage remoto S3-compatível** (Cloudflare R2, Amazon S3, Backblaze B2,
  ...), ativado com `PRODUCT_IMAGES_STORAGE_ENABLED=true` e as variáveis
  `PRODUCT_IMAGES_BUCKET`, `PRODUCT_IMAGES_ENDPOINT`, `PRODUCT_IMAGES_REGION`,
  `PRODUCT_IMAGES_ACCESS_KEY_ID`, `PRODUCT_IMAGES_SECRET_ACCESS_KEY`,
  `PRODUCT_IMAGES_PUBLIC_BASE_URL` e `PRODUCT_IMAGES_PREFIX` (veja
  `.env.example` e `render.yaml`). É o modo recomendado em produção: a URL
  devolvida é estável e não depende de qual instância recebeu o upload.
  Use um bucket/credencial **próprios**, nunca reaproveite os segredos
  `BACKUP_*` do backup do banco (escopo e prefixo diferentes).
- **Disco local** (padrão quando o storage remoto não está configurado --
  desenvolvimento, testes, ou fallback): grava em
  `backend/upload_routes.UPLOAD_DIR`, que por padrão é
  `backend/uploads/produtos`, mas pode (e deve, em produção sem storage
  remoto) ser redirecionado para o disco persistente via
  `PRODUCT_IMAGES_LOCAL_DIR=/data/uploads/produtos`.

Endpoints nunca chamam boto3 nem escrevem no disco diretamente -- sempre
pelo `ProductImageStorage`, para manter nomes, prefixos, validação e
remoção centralizados.

### Auditoria e migração

- `scripts/audit_product_images.py` -- só leitura, verifica se as URLs
  cadastradas respondem, detecta 404/duplicidade/caminho local ausente.
- `scripts/migrate_local_product_images_to_storage.py` -- migra imagens
  ainda presentes no disco local para o storage remoto e atualiza o banco;
  roda em `--dry-run` por padrão, use `--apply` para efetivar.

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
  "url": "/uploads/produtos/incenso-natural-abc123.webp",
  "armazenamento": "local"
}
```

`armazenamento` vem `"s3"` quando o storage remoto está ativo -- nesse caso
`url` já é a URL pública definitiva (`PRODUCT_IMAGES_PUBLIC_BASE_URL` + chave).

## Próximo passo recomendado

Adicionar no Admin um campo de upload visual para enviar a foto e preencher automaticamente a URL da imagem do produto.

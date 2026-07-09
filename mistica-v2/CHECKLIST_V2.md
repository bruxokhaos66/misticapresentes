# Checklist da Mistica Presentes V2

## Objetivo visual

- [x] Criar base limpa em `mistica-v2/`.
- [x] Manter identidade xamanica, moderna e comercial.
- [x] Manter Isis como destaque visual e comercial.
- [x] Reaproveitar imagem ja existente da Isis.
- [x] Preservar versao atual do site sem apagar arquivos antigos.

## Funcionalidades preservadas

- [x] Produtos renderizados pelo `app.js` atual.
- [x] Carrinho mantido com os mesmos IDs usados pela logica atual.
- [x] Pix mantido com canvas, payload e botoes usados pelo `app.js`.
- [x] WhatsApp mantido com `data-whatsapp-link` e botoes funcionais.
- [x] Isis mantida com `isisForm`, `isisInput` e `isisChat`.
- [x] Estruturas internas minimas mantidas para evitar erro no `app.js`.

## Testes necessarios antes de publicar

- [ ] Abrir `mistica-v2/index.html` em preview.
- [ ] Confirmar se os produtos carregam.
- [ ] Adicionar produto ao carrinho.
- [ ] Confirmar se total do carrinho atualiza.
- [ ] Gerar Pix e conferir QR Code.
- [ ] Copiar Pix copia e cola.
- [ ] Enviar pedido pelo WhatsApp.
- [ ] Testar botoes rapidos da Isis.
- [ ] Testar layout no celular.

## Observacoes

A V2 foi criada em pasta isolada para reconstruir o site com calma. A versao principal ainda nao foi substituida. So deve virar a home principal depois dos testes acima.
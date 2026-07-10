# Checklist da Mística Presentes V2

## Objetivo visual

- [x] Criar uma base limpa para a nova versão do site.
- [x] Manter identidade xamânica, moderna e comercial.
- [x] Manter Isis como destaque visual e comercial.
- [x] Reaproveitar a imagem existente da Isis.
- [x] Preservar a versão anterior antes da migração definitiva.

## Funcionalidades preservadas

- [x] Produtos renderizados pelo `app.js` atual.
- [x] Carrinho mantido com os mesmos IDs usados pela lógica atual.
- [x] Pix mantido com canvas, payload e botões usados pelo `app.js`.
- [x] WhatsApp mantido com `data-whatsapp-link` e botões funcionais.
- [x] Isis mantida com `isisForm`, `isisInput` e `isisChat`.
- [x] Estruturas internas mínimas mantidas para evitar erro no `app.js`.

## Testes necessários antes de publicar

- [ ] Abrir o `index.html` da raiz em preview.
- [ ] Confirmar se os produtos carregam.
- [ ] Adicionar produto ao carrinho.
- [ ] Confirmar se o total do carrinho atualiza.
- [ ] Gerar Pix e conferir QR Code.
- [ ] Copiar Pix copia e cola.
- [ ] Enviar pedido pelo WhatsApp.
- [ ] Testar botões rápidos da Isis.
- [ ] Testar o layout no celular.

## Observações

A V2 foi criada inicialmente em uma pasta isolada e agora está preparada para se tornar a página principal na raiz do domínio. A publicação definitiva só deve ocorrer depois da aprovação de todos os testes automatizados e da conferência visual.
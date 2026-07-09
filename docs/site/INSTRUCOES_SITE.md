# Mistica Presentes - Site comercial

Projeto estatico em HTML, CSS e JavaScript para publicar no GitHub Pages.

## O que foi criado

- Pagina inicial comercial com visual moderno e xamanico.
- Area sobre a Mistica Presentes.
- Catalogo de produtos da loja.
- Botao Comprar pelo WhatsApp em cada produto.
- Carrinho de venda simples.
- Envio do pedido para o WhatsApp da loja.
- Cadastro de cliente.
- Validacao basica de dados e quantidade.
- Controle simples de estoque salvo no navegador.
- Historico das ultimas vendas.
- Exportacao de clientes e vendas em CSV.
- Geracao de Pix copia e cola e QR Code Pix pelo navegador.
- Area administrativa inicial.
- Dashboard, fornecedores, estoque minimo, comprovante, backup local e area da Isis.

## Arquivos principais

- `index.html`: estrutura da pagina.
- `styles.css`: layout, cores, responsividade, painel admin e Isis.
- `app.js`: produtos, carrinho, clientes, vendas, estoque, Pix, WhatsApp, fornecedores, backup, cupom, dashboard e Isis.
- `site-config.js`: configuracoes comerciais centralizadas.

## Configuracoes comerciais

As configuracoes reais de WhatsApp, Pix, dominio e chaves devem ficar em arquivos de configuracao apropriados ou variaveis de ambiente do servidor.

Nao registre senha real, chave Pix sensivel, token de API ou credenciais em repositorio publico.

## Como alterar produtos, precos, estoque e fotos reais

No catalogo, cada produto deve ter:

```js
{
  id: "incenso-natural",
  name: "Incenso Natural",
  category: "Aromas",
  description: "Aromas para purificacao...",
  price: 12.90,
  stock: 30,
  icon: "🌿",
  imageUrl: ""
}
```

Campos importantes:

- `price`: preco de venda.
- `stock`: estoque inicial.
- `icon`: icone usado quando nao houver foto.
- `imageUrl`: link da foto real do produto.

## Como usar a venda

1. Escolha a quantidade de um produto.
2. Clique em Adicionar.
3. Confira o carrinho e o total.
4. Envie o pedido pelo WhatsApp.
5. Gere Pix quando aplicavel.
6. Confira no banco se valor e recebedor estao corretos.

## Historico, cupom e comprovante

Na area de historico e possivel:

- exportar vendas CSV;
- imprimir cupom de venda;
- enviar comprovante ou resumo do pedido pelo WhatsApp.

## Area administrativa

A area administrativa inclui:

- faturamento;
- total de vendas;
- alertas de estoque minimo;
- cadastro de fornecedores;
- backup local;
- plano de evolucao para banco de dados.

## Backup

O sistema pode salvar backup automatico no navegador e permitir download de arquivo JSON com dados operacionais.

Para producao, use backend e banco de dados como fonte principal.

## Isis

A area da Isis responde comandos locais e pode ser conectada a API/backend para consultas, recomendacoes e pedidos.

## Limitacoes importantes

Um site estatico sozinho nao oferece seguranca administrativa real nem banco centralizado.

Para uso profissional completo, o proximo passo e manter backend, banco de dados, autenticacao real, logs e integracao oficial com pagamentos.

## Publicacao no GitHub Pages

1. Mescle a branch aprovada na `main`.
2. No GitHub, abra o repositorio.
3. Va em Settings.
4. Abra Pages.
5. Configure Deploy from a branch.
6. Selecione a branch e pasta correta.
7. Salve e aguarde o link publico ser gerado.

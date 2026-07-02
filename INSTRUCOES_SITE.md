# Mística Presentes - Site comercial

Projeto estático em **HTML, CSS e JavaScript** para publicar no GitHub Pages.

## O que foi criado

- Página inicial comercial com visual moderno e xamânico.
- Área sobre a Mística Presentes.
- Catálogo de produtos da loja.
- Botão **Comprar pelo WhatsApp** em cada produto.
- Carrinho de venda simples.
- Envio do resumo da venda para o WhatsApp da loja.
- Cadastro de cliente com nome, CPF, endereço e WhatsApp.
- Validação básica de CPF, WhatsApp e quantidade.
- Controle simples de estoque salvo no navegador.
- Histórico visível das últimas vendas.
- Exportação de clientes e vendas em CSV.
- Geração de Pix copia e cola e QR Code Pix pelo navegador.
- Aviso para conferir nome do recebedor e valor antes de pagar.
- Imagens SVG locais em `assets/`.
- Dados salvos no navegador via `localStorage`.

## Arquivos principais

- `index.html`: estrutura da página.
- `styles.css`: layout, cores, responsividade e visual xamânico.
- `app.js`: produtos, carrinho, clientes, vendas, estoque, Pix, WhatsApp e CSV.
- `assets/logo-mistica.svg`: logo do site.
- `assets/hero-xamanico.svg`: arte principal do topo.

## Configuração obrigatória antes de publicar

Abra o arquivo `app.js` e edite o bloco `storeConfig`:

```js
const storeConfig = {
  name: "Mística Presentes",
  whatsappNumber: "5549999999999",
  pixKey: "misticapresentes@email.com",
  merchantName: "MISTICA PRESENTES",
  merchantCity: "PINHALZINHO",
  instagram: "@misticaprodutos"
};
```

### WhatsApp

Troque `5549999999999` pelo número real da loja.

Formato obrigatório:

```txt
55 + DDD + número
```

Exemplo:

```txt
5549999999999
```

Não use espaços, parênteses ou traços.

### Pix

Troque `misticapresentes@email.com` pela chave Pix real da loja.

Pode ser:

- e-mail;
- telefone;
- CPF/CNPJ;
- chave aleatória.

Também confira:

- `merchantName`: nome que aparecerá no banco, limitado pelo padrão Pix.
- `merchantCity`: cidade do recebedor.

## Como alterar produtos, preços e estoque

No arquivo `app.js`, edite a lista `products`:

```js
{
  id: "incenso-natural",
  name: "Incenso Natural",
  category: "Aromas",
  description: "Aromas para purificação...",
  price: 12.90,
  stock: 30,
  icon: "🌿"
}
```

Campos importantes:

- `price`: preço de venda.
- `stock`: estoque inicial.
- `icon`: ícone que aparece no card.

## Como usar a venda

1. Escolha a quantidade de um produto.
2. Clique em **Adicionar**.
3. Confira o carrinho e o total.
4. Clique em **Enviar resumo WhatsApp** para mandar a venda para a loja.
5. Clique em **Gerar QR Code Pix** para gerar pagamento.
6. Confira no banco se o valor e o recebedor estão corretos.

Quando o Pix é gerado, a venda é salva no histórico e o estoque é baixado neste navegador.

## Exportação CSV

O site tem botões para:

- Exportar clientes CSV.
- Exportar vendas CSV.

Os arquivos são baixados pelo próprio navegador.

## Limitações importantes

Este projeto ainda é um site estático.

Isso significa:

- dados ficam salvos somente no navegador usado;
- outro computador/celular não verá os mesmos clientes, vendas e estoque;
- o Pix não confirma pagamento automaticamente;
- o estoque não é centralizado;
- não existe login ou banco de dados.

Para uso profissional completo, o próximo passo é adicionar backend, banco de dados, autenticação e integração oficial com provedor Pix.

## LGPD e segurança

O cadastro salva nome, CPF, endereço e WhatsApp no navegador.

Use apenas com autorização do cliente. Para publicar de forma pública e profissional, recomenda-se adicionar política de privacidade completa e reduzir a coleta de dados ao mínimo necessário.

## Como publicar no GitHub Pages

1. Mescle esta branch no `main`.
2. No GitHub, abra o repositório.
3. Vá em **Settings**.
4. Clique em **Pages**.
5. Em **Build and deployment**, selecione:
   - Source: `Deploy from a branch`
   - Branch: `main`
   - Folder: `/root`
6. Salve e aguarde o link público ser gerado.

# Mística Presentes - Site comercial

Projeto estático em **HTML, CSS e JavaScript** para publicar no GitHub Pages.

## O que foi criado

- Página inicial comercial com visual moderno e xamânico.
- Área sobre a Mística Presentes.
- Catálogo de produtos da loja.
- Carrinho de venda simples.
- Cadastro de cliente com nome, CPF, endereço e WhatsApp.
- Geração de Pix copia e cola e QR Code Pix pelo navegador.
- Imagens SVG locais em `assets/`.
- Dados salvos no navegador via `localStorage`.

## Arquivos principais

- `index.html`: estrutura da página.
- `styles.css`: layout, cores, responsividade e visual xamânico.
- `app.js`: produtos, carrinho, clientes, Pix e QR Code.
- `assets/logo-mistica.svg`: logo do site.
- `assets/hero-xamanico.svg`: arte principal do topo.

## Como personalizar

### Alterar produtos

Edite a lista `products` no arquivo `app.js`.

### Alterar WhatsApp

No `index.html`, troque este trecho:

```html
https://wa.me/5500000000000
```

Use o número com código do Brasil e DDD, sem espaços. Exemplo:

```html
https://wa.me/5549999999999
```

### Alterar chave Pix padrão

No `index.html`, localize:

```html
<input id="pixKey" type="text" value="misticapresentes@email.com" />
```

Troque pelo e-mail, telefone, CPF/CNPJ ou chave aleatória da loja.

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

## Observações importantes

Este projeto é ideal para apresentação, vendas simples e demonstração comercial. Para uma loja real com pagamentos confirmados automaticamente, estoque centralizado e dados seguros, o próximo passo é adicionar backend, banco de dados, autenticação e integração oficial com provedor de Pix.

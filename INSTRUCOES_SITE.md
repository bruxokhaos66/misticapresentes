# Mística Presentes - Site comercial

Projeto estático em **HTML, CSS e JavaScript** para publicar no GitHub Pages.

## O que foi criado

- Página inicial comercial com visual moderno e xamânico.
- Área sobre a Mística Presentes.
- Catálogo de produtos da loja.
- Botão **Comprar pelo WhatsApp** em cada produto.
- Carrinho de venda simples.
- Envio do pedido para o WhatsApp da loja.
- Cadastro de cliente com nome, CPF, endereço e WhatsApp.
- Validação básica de CPF, WhatsApp e quantidade.
- Controle simples de estoque salvo no navegador.
- Histórico visível das últimas vendas.
- Exportação de clientes e vendas em CSV.
- Geração de Pix copia e cola e QR Code Pix pelo navegador.
- Aviso para conferir nome do recebedor e valor antes de pagar.
- Área administrativa protegida por senha local.
- Dashboard com faturamento diário, semanal, mensal e total de vendas.
- Cadastro de fornecedores.
- Alerta de estoque mínimo.
- Impressão do último cupom de venda.
- Envio do último comprovante/pedido pelo WhatsApp.
- Backup automático local e download de backup JSON.
- Área inicial da IA Isis para atendimento, vendas, estoque, fornecedores e pesquisa.
- Planejamento de integração futura com banco de dados.
- Dados salvos no navegador via `localStorage`.

## Arquivos principais

- `index.html`: estrutura da página.
- `styles.css`: layout, cores, responsividade, painel admin e Isis.
- `app.js`: produtos, carrinho, clientes, vendas, estoque, Pix, WhatsApp, fornecedores, backup, cupom, dashboard e Isis.
- `assets/logo-mistica.svg`: logo do site.
- `assets/hero-xamanico.svg`: arte principal do topo.

## Configuração atual

O arquivo `app.js` já está configurado com:

```js
const storeConfig = {
  name: "Mística Presentes",
  whatsappNumber: "5549984090802",
  pixKey: "07353652969",
  merchantName: "FREDINEI JEAN BACH",
  merchantCity: "PINHALZINHO",
  instagram: "@misticaprodutos",
  adminPassword: "mistica2026",
  minStock: 3
};
```

### WhatsApp

Número configurado:

```txt
(49) 98409-0802
```

No código, o formato usado é:

```txt
5549984090802
```

### Pix

Pix CPF configurado:

```txt
073.536.529-69
```

Titular configurado:

```txt
FREDINEI JEAN BACH
```

Antes de publicar, faça um teste de Pix com valor pequeno e confira se o banco exibe o recebedor corretamente.

## Senha administrativa

Senha inicial configurada:

```txt
mistica2026
```

Atenção: como este projeto é estático, essa senha fica no JavaScript e serve apenas como bloqueio simples de tela. Para segurança real, será necessário backend com login, senha criptografada e permissões.

## Como alterar produtos, preços, estoque e fotos reais

No arquivo `app.js`, edite a lista `products`:

```js
{
  id: "incenso-natural",
  name: "Incenso Natural",
  category: "Aromas",
  description: "Aromas para purificação...",
  price: 12.90,
  stock: 30,
  icon: "🌿",
  imageUrl: ""
}
```

Campos importantes:

- `price`: preço de venda.
- `stock`: estoque inicial.
- `icon`: ícone usado quando não houver foto.
- `imageUrl`: link da foto real do produto.

Para usar foto real, coloque uma URL de imagem em `imageUrl` ou futuramente adicione uma pasta `assets/produtos/` com fotos próprias.

## Como usar a venda

1. Escolha a quantidade de um produto.
2. Clique em **Adicionar**.
3. Confira o carrinho e o total.
4. Clique em **Enviar pedido WhatsApp** para mandar a venda para a loja.
5. Clique em **Gerar QR Code Pix** para gerar pagamento.
6. Confira no banco se o valor e o recebedor estão corretos.

Quando o Pix é gerado, a venda é salva no histórico e o estoque é baixado neste navegador.

## Histórico, cupom e comprovante

Na área de histórico é possível:

- exportar vendas CSV;
- imprimir o último cupom de venda;
- enviar o último comprovante/pedido pelo WhatsApp.

## Área administrativa

A área administrativa inclui:

- faturamento de hoje;
- faturamento da semana;
- faturamento do mês;
- total de vendas registradas;
- alertas de estoque mínimo;
- cadastro de fornecedores;
- backup local e download JSON;
- plano de evolução para banco de dados.

## Backup

O sistema salva um backup automático no próprio navegador sempre que os dados mudam.

Também existe botão para baixar um arquivo `.json` com:

- produtos;
- clientes;
- vendas;
- estoque;
- fornecedores.

## Isis

A área da Isis responde comandos locais como:

- vendas hoje;
- faturamento;
- estoque baixo;
- fornecedores;
- pesquisar produtos.

Quando o comando envolve pesquisa, ela abre uma busca no navegador. Para uma Isis realmente inteligente com internet, memória e ações avançadas, será necessário integrar backend e API de IA.

## Limitações importantes

Este projeto ainda é um site estático.

Isso significa:

- dados ficam salvos somente no navegador usado;
- outro computador/celular não verá os mesmos clientes, vendas e estoque;
- o Pix não confirma pagamento automaticamente;
- o estoque não é centralizado;
- a senha administrativa é apenas uma barreira visual;
- não existe banco de dados real ainda.

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

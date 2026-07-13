# Issue #300 — Plano da Fase 2

## Base

Esta fase parte do squash merge do PR #298 (`6ca5fda`) e mantém as garantias da Fase 1: catálogo oficial, checkout único, payload mínimo e ausência de persistência local sensível.

## Frentes de trabalho

### 1. Autoridade de preço, desconto e estoque

- mapear o contrato atual de criação do pedido;
- confirmar que preço, subtotal, desconto e total recebidos do navegador são ignorados;
- recalcular todos os valores no backend;
- validar produto ativo, quantidade e disponibilidade na mesma transação;
- garantir que o payload Pix use o total final calculado pelo servidor;
- cobrir preço adulterado, cupom inválido, produto inativo, estoque insuficiente e concorrência no último item.

### 2. Produtos sob encomenda

- localizar a regra atual de encomenda no frontend e backend;
- criar distinção explícita entre estoque normal e encomenda;
- permitir estoque zero somente quando o produto estiver configurado para encomenda;
- exigir confirmação do cliente;
- aplicar limite máximo de quantidade no backend;
- bloquear produto inativo ou comercialmente indisponível.

### 3. Sanitização e renderização segura

- inventariar pontos que usam `innerHTML` com dados da API;
- migrar campos de produto para `textContent` e criação segura de elementos;
- validar URLs de imagem e links externos;
- adicionar testes contra scripts, atributos HTML maliciosos e marcação inválida.

### 4. Cadastro e edição de produtos

- normalizar códigos removendo espaços periféricos e diferenças de caixa;
- impedir códigos duplicados normalizados;
- limitar tamanho dos campos textuais;
- limitar preço, custo, estoque e estoque mínimo;
- rejeitar `NaN`, infinito e valores inválidos;
- exigir no máximo duas casas decimais;
- recalcular margem e lucro no servidor;
- validar URLs de imagem.

## Ordem de implementação

1. Auditoria do backend e testes existentes.
2. Testes de regressão para payload adulterado e concorrência.
3. Correções de autoridade comercial no backend.
4. Regra de produto sob encomenda.
5. Sanitização do frontend público.
6. Validações do cadastro administrativo.
7. Playwright desktop/mobile e revisão final.

## Regra de merge

O PR deve permanecer em draft enquanto houver qualquer teste Python, Playwright ou Lighthouse falhando. O merge será feito somente após revisão final e autorização explícita.

# Painel Mobile - rotina funcional

Data do registro: 04/07/2026

## Estado que funcionou

O painel mobile voltou a funcionar depois que a sincronizacao passou a enviar primeiro os usuarios, depois produtos e vendas em lote.

Fluxo correto:

1. Sincronizar usuarios do desktop para a API.
2. Sincronizar produtos.
3. Sincronizar vendas em lote.
4. Abrir o app Android.
5. Entrar com o usuario sincronizado.
6. Tocar em Atualizar.

## Comando principal

Sempre que o login ou o painel mobile ficar estranho depois de atualizacao da API, rodar no Git Bash:

```bash
cd /c/Users/fredi/BruxoBR/misticapresentes
git pull origin main
python tools/sincronizar_painel_online.py
```

Esse comando sincroniza:

- Usuarios
- Produtos
- Vendas

## Usuario confirmado

Usuario usado no teste funcional:

```text
login: bruxo
senha: 1234
perfil: adm
nome: Fredi Bach
```

## Sintomas que indicam falta de sincronizacao

- App mostra login ou senha invalidos.
- API lista apenas o usuario admin em `/api/auth/usuarios-debug`.
- Painel aparece zerado mesmo com vendas no desktop.
- Vendas hoje e vendas mes aparecem R$ 0,00.
- Produtos aparecem 0.

## Verificacoes uteis

Listar usuarios existentes na API:

```bash
curl https://api.misticaesotericos.com.br/api/auth/usuarios-debug
```

Testar login direto na API:

```bash
curl -X POST "https://api.misticaesotericos.com.br/api/auth/login" -H "Content-Type: application/json" -d '{"login":"bruxo","senha":"1234"}'
```

Resultado esperado: retorno com `status: ok` e usuario `bruxo`.

## Commits importantes relacionados

- `8acac2c` - Sincroniza usuarios antes do painel online.
- `2580e4d` - Usa envio em lote para vendas do painel online.
- `305a763` - Corrige endpoint de sincronizacao de vendas.
- `876facf` - Corrige timeout e atualizacao do painel Android.

## Observacao

Se a API online reiniciar/atualizar e perder os usuarios sincronizados, o login `bruxo` pode falhar ate que o comando `python tools/sincronizar_painel_online.py` seja executado novamente.

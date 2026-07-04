# API Mística Presentes — SQLite persistente

O painel mobile só mantém vendas, produtos e usuários se o banco da API ficar em um local persistente.

Se a hospedagem recriar o servidor e o arquivo `.db` estiver dentro da pasta temporária do app, a API volta com:

```text
produtos: 0
vendas: 0
```

## Correção no código

A API agora aceita a variável de ambiente:

```text
MISTICA_DB_PATH
```

Ela deve apontar para o arquivo SQLite dentro de um volume/disco persistente.

Exemplos:

```text
/data/mistica_gestao_v20.db
/var/data/mistica_gestao_v20.db
/mnt/data/mistica_gestao_v20.db
```

Também é aceito `DATABASE_PATH`, mas o recomendado é usar `MISTICA_DB_PATH`.

## Configuração recomendada

Na hospedagem da API, configure:

```text
MISTICA_DB_PATH=/data/mistica_gestao_v20.db
```

E monte um volume persistente na pasta:

```text
/data
```

Depois reinicie/redeploye a API.

## Teste depois de configurar

No computador da loja:

```bash
cd /c/Users/fredi/BruxoBR/misticapresentes
git pull origin main
python tools/sincronizar_painel_online.py
python tools/testar_painel_mobile.py
```

O esperado:

```text
Status API: produtos 5, vendas 42
Vendas que o painel deveria mostrar hoje: 5 R$ 63,00
```

Depois reinicie a API na hospedagem e rode novamente:

```bash
python tools/testar_painel_mobile.py
```

Se continuar mostrando produtos e vendas, o volume persistente está funcionando.

## Render

Se estiver usando Render:

1. Abra o serviço da API.
2. Vá em `Disks`.
3. Crie um disco persistente.
4. Mount path: `/data`.
5. Vá em `Environment`.
6. Adicione:

```text
MISTICA_DB_PATH=/data/mistica_gestao_v20.db
```

7. Faça redeploy.
8. Rode a sincronização completa pelo computador da loja.

## Railway

Se estiver usando Railway:

1. Crie/adicione um volume persistente no serviço da API.
2. Monte o volume em `/data`.
3. Em `Variables`, adicione:

```text
MISTICA_DB_PATH=/data/mistica_gestao_v20.db
```

4. Redeploy.
5. Sincronize novamente pelo desktop.

## VPS/Linux próprio

Crie uma pasta fora do diretório temporário do app:

```bash
sudo mkdir -p /data/mistica
sudo chown -R $USER:$USER /data/mistica
```

Configure:

```text
MISTICA_DB_PATH=/data/mistica/mistica_gestao_v20.db
```

Reinicie a API e sincronize novamente.

## Observação

SQLite persistente resolve a perda de dados por restart/redeploy quando o disco realmente é persistente.

Para uma solução ainda mais profissional e segura, a próxima etapa recomendada é migrar a API para PostgreSQL.
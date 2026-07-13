# Backup consistente do SQLite

Este documento descreve como os backups do banco SQLite são criados hoje no
projeto (site/API, app desktop e servidor de sincronização) e como restaurar
um backup manualmente. Não inclui valores reais de ambiente ou caminhos
internos de nenhuma instância específica.

## Por que não copiar o arquivo `.db` diretamente

O banco roda em modo `journal_mode=WAL`. Nesse modo, transações confirmadas
recentemente podem estar apenas no arquivo `-wal` (write-ahead log) e ainda
não terem sido consolidadas no arquivo principal `.db`. Uma cópia de arquivo
simples (`shutil.copy2`, `cp`, etc.) pode capturar o `.db` num instante em
que ele ainda não reflete os pedidos e pagamentos mais recentes — o backup
parece ter funcionado, mas fica incompleto ou inconsistente, e isso só é
descoberto no momento em que alguém tenta restaurá-lo.

## Como o snapshot é criado

Toda criação de backup passa pela função central
`database.backup.criar_backup_seguro(origem_path, destino_dir, prefixo, tag_extra=None)`,
que:

1. abre a origem e o destino como duas conexões SQLite separadas;
2. usa a API oficial `Connection.backup()` do SQLite (não cópia de arquivo) —
   ela produz um snapshot consistente mesmo com o banco em WAL e com outras
   conexões escrevendo ao mesmo tempo;
3. valida o snapshot resultante: existe, tem tamanho maior que zero, não é o
   mesmo arquivo da origem, abre normalmente e passa em
   `PRAGMA integrity_check`;
4. se a validação falhar, remove **apenas** o arquivo inválido recém-criado
   e propaga o erro — nenhum backup anterior é tocado;
5. calcula o checksum SHA-256 do arquivo validado e grava um arquivo
   `<backup>.sha256` ao lado dele (formato `hash  nome_do_arquivo`, sem
   caminho absoluto);
6. sanitiza o nome do arquivo de backup (apenas letras, números, `_` e `-`)
   e garante que o caminho final continua dentro do diretório de destino,
   rejeitando qualquer tentativa de nome malicioso ou "path traversal".

Essa função é reutilizada por três fluxos diferentes:

- **App desktop / POS** (`database/backup.py:realizar_backup`) — backup
  automático em pontos-chave (venda, fechamento, antes de restaurar) e
  backup manual pela tela de administração;
- **App desktop, backups locais avulsos** (`services/backup_service.py`) —
  backup ao iniciar o app e antes de atualizações;
- **Site/API** (`backend/backup_routes.py`) — backup manual via
  `POST /api/backup/manual` e download via `GET /api/backup/download`,
  ambos restritos a quem possui a chave de API administrativa.

## Onde os backups ficam

O diretório de backups é definido por configuração (`BACKUP_DIR`), fora da
pasta pública servida pelo site. O nome de cada arquivo segue o padrão
`<prefixo>_<data>_<hora>[_<tag>].db`, sem dados sensíveis no nome (sem CPF,
telefone, nome de cliente, etc.).

## Retenção

- Os backups automáticos do app desktop (`mistica_auto_*`) têm retenção de
  **30 dias**: arquivos mais antigos são removidos automaticamente a cada
  novo backup automático.
- A limpeza só remove arquivos cujo nome já é reconhecido como backup da
  aplicação (prefixo esperado) — nunca remove arquivos arbitrários do
  diretório.
- O backup recém-criado nunca é removido pela própria rotina de limpeza que
  ele dispara (a limpeza só olha para a idade dos arquivos, e um arquivo
  recém-criado nunca é "antigo").
- Os backups manuais e de download feitos pela API não entram nessa rotina
  de limpeza automática; a cópia efêmera criada especificamente para
  download é apagada do disco assim que a resposta HTTP termina de ser
  enviada, para não acumular arquivos temporários.

## Como validar um backup manualmente

```bash
python3 - <<'PY'
import sqlite3
conn = sqlite3.connect("caminho/para/o/backup.db")
print(conn.execute("PRAGMA integrity_check").fetchone())
conn.close()
PY
```

O resultado esperado é `('ok',)`. Também é possível conferir o checksum:

```bash
sha256sum -c caminho/para/o/backup.db.sha256
```

## Procedimento manual de restauração

Este PR **não** adiciona uma rota pública de restauração — restaurar um
backup é uma operação destrutiva e deve ser feita deliberadamente por um
administrador, nunca automaticamente.

1. Pare a aplicação que está usando o banco ativo (ou garanta que ninguém
   mais está escrevendo nele).
2. Copie o backup escolhido para um arquivo **separado**, fora do caminho do
   banco ativo, e valide-o com `PRAGMA integrity_check` (comando acima).
3. Só depois de validado, substitua o arquivo do banco ativo pelo backup
   (o app desktop já tem uma tela de administração para isso, que também
   cria uma cópia de segurança do estado atual antes de restaurar).
4. Reinicie a aplicação para garantir que nenhuma conexão antiga continue
   apontando para o arquivo anterior.

Um teste automatizado (`tests/test_backup_consistency.py`) cobre exatamente
esse fluxo — restaurar em um arquivo separado e consultar os dados — sem
nunca sobrescrever um banco "ativo" de verdade.

## Cuidados em produção (Render e discos persistentes)

- O backup só é útil se **origem e destino estiverem no mesmo disco
  persistente montado** (ou se o destino for copiado para fora da instância
  logo em seguida). Um backup salvo no mesmo filesystem efêmero que o banco
  não sobrevive a um redeploy.
- Sempre que possível, envie uma cópia periódica do backup para **fora da
  instância** (outro serviço de armazenamento, outro volume, download
  manual por um administrador) — um disco persistente protege contra
  reinício do container, mas não contra corrupção do próprio disco.
- O endpoint `GET /api/backup/download` existe justamente para permitir que
  um administrador baixe uma cópia para fora da instância periodicamente.

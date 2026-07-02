# Plano seguro antes de gerar o EXE

Este checklist deve ser seguido antes de cada rodada grande com Continue, Copilot ou outro agente.

## 1. Backup obrigatório

Antes de qualquer alteração grande:

```bash
git status
git add .
git commit -m "Backup antes da nova rodada de IA"
git push
```

Se houver alterações locais que ainda não estão no GitHub, não continue antes de salvar.

## 2. Banco de cópia para testes

Nunca teste venda, cancelamento, caixa ou auditoria usando o banco real da loja.

1. Feche o sistema.
2. Copie o banco atual do Documents para uma pasta de teste.
3. Configure o sistema para apontar para a cópia usando `mistica_config_rede.json`.
4. Abra o sistema e confirme visualmente que está no ambiente de teste.

Exemplo de arquivo `mistica_config_rede.json` no Documents:

```json
{
  "db_path": "C:/CAMINHO/DA/COPIA/mistica_gestao_teste.db"
}
```

## 3. Testes mínimos obrigatórios

### Login

- Entrar como administrador.
- Entrar como vendedor.
- Testar senha incorreta.
- Confirmar que `admin/admin` não é aceito.

### Caixa

- Abrir caixa.
- Confirmar que o sistema bloqueia venda sem caixa aberto.
- Registrar entrada/saída manual, se existir essa função.
- Fechar caixa.

### Estoque

- Cadastrar produto de teste.
- Editar preço, custo e quantidade.
- Confirmar produto na listagem.
- Testar estoque baixo.

### Venda

- Fazer venda com produto de teste.
- Confirmar baixa de estoque.
- Confirmar item em `vendas_itens`.
- Confirmar entrada no `fluxo_caixa`.

### Cancelamento

- Cancelar a venda de teste.
- Confirmar retorno do estoque.
- Confirmar status `Cancelado`.
- Confirmar saída/estorno no `fluxo_caixa`.

### Isis

- Perguntar resumo da loja.
- Perguntar estoque baixo.
- Pedir auditoria apenas análise.
- Não pedir correção automática em banco real.

## 4. Gerar EXE somente depois dos testes

Gerar o `.exe` apenas se todos os testes acima passarem.

Comando base:

```bash
pyinstaller --onefile --windowed app.py
```

Depois de gerar:

- Abrir o EXE.
- Fazer login.
- Testar venda simples no banco de cópia.
- Fechar e abrir novamente.
- Confirmar que o banco continua íntegro.

## 5. Regra para agentes de IA

Nunca pedir para o agente "corrigir tudo" direto na branch principal.

Fluxo recomendado:

1. Criar branch.
2. Fazer alteração pequena.
3. Revisar diff.
4. Testar localmente.
5. Commit/push.
6. Só depois continuar para a próxima etapa.

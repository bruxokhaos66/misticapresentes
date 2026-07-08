# Guia de Entrega e Teste Real — Mística Presentes

Este guia serve para testar o sistema na máquina real da loja após os workflows ficarem verdes no GitHub Actions.

---

## 1. Arquivos que devem ser baixados

### Instalador completo

Workflow:

```text
Build Instalador Windows
```

Artifact:

```text
Instalador_Mistica_Presentes
```

Uso:

```text
Use este pacote quando for instalar o sistema em uma máquina nova ou reinstalar tudo.
```

---

### Launcher inteligente

Workflow:

```text
Build Mistica Launcher
```

Artifact:

```text
MisticaLauncher-Windows
```

Uso:

```text
Use o MisticaLauncher.exe para abrir o sistema no dia a dia.
```

O Launcher:

```text
- verifica atualização online antes do login
- mostra barra de progresso
- detecta Windows 7/10/11
- escolhe o canal correto
- abre o sistema local se não houver internet
- faz rollback se uma atualização falhar
```

---

### Pacote de atualização online

Workflow:

```text
Build Online Update Package
```

Artifact:

```text
MisticaPresentes-Updates
```

Uso:

```text
Serve para conferir o pacote de atualização gerado antes de publicar.
```

---

## 2. Ordem recomendada para instalar/testar

```text
1. Baixar Instalador_Mistica_Presentes.zip
2. Extrair o arquivo
3. Rodar Instalar_Mistica_Presentes.bat
4. Baixar MisticaLauncher-Windows.zip
5. Extrair MisticaLauncher.exe
6. Abrir o sistema sempre pelo MisticaLauncher.exe
7. Fazer login
8. Testar vendas, caixa, backup e sincronização
```

---

## 3. Primeiro teste obrigatório

Antes de usar com venda real, testar:

```text
- abrir caixa
- cadastrar ou conferir produto em estoque
- fazer venda simples em dinheiro
- fazer venda em Pix
- fazer venda em Débito
- fazer venda em Crédito 1x
- fazer venda mista com 2 formas
- fazer venda mista com 3 formas
- cancelar uma venda simples
- cancelar uma venda mista
- fechar caixa
```

---

## 4. Teste do pagamento misto

Exemplo:

```text
Venda total: R$ 100,00
Pagamento:
Dinheiro R$ 30,00
Pix R$ 40,00
Débito R$ 30,00
```

Conferir:

```text
- se a venda salva corretamente
- se o cupom mostra as formas separadas
- se o caixa lança as entradas separadas
- se o fechamento mostra os valores corretos
```

---

## 5. Teste do backup

Na aba:

```text
Manutenção
```

Testar:

```text
FAZER BACKUP AGORA
VER ÚLTIMO BACKUP
ABRIR PASTA DE BACKUPS
```

Pasta esperada:

```text
Documents/Mistica_Presentes_App/backups
```

Status esperado:

```text
Documents/Mistica_Presentes_App/ultimo_backup.json
```

---

## 6. Teste da sincronização

Na aba:

```text
Manutenção
```

Testar:

```text
VER STATUS DA SINCRONIZAÇÃO
RODAR SINCRONIZAÇÃO
```

Conferir:

```text
- se mostra Online ou Offline
- se mostra pendências
- se não trava a tela
```

---

## 7. Teste do atualizador online

Rodar o workflow:

```text
Publish Online Update
```

Informar uma versão nova, exemplo:

```text
1.0.500
```

Depois abrir:

```text
MisticaLauncher.exe
```

Conferir:

```text
- se verifica atualização
- se baixa pacote
- se cria backup antes de instalar
- se abre o sistema normalmente
```

---

## 8. Cuidados antes de usar com venda real

Antes de começar a vender oficialmente:

```text
- confirmar estoque inicial
- abrir caixa com valor correto
- fazer backup manual
- testar impressora/cupom, se houver
- testar internet
- testar venda mista
- testar fechamento de caixa
```

---

## 9. Arquivos importantes do sistema

```text
MisticaPresentes.exe
MisticaLauncher.exe
ServidorMisticaApp
Documents/Mistica_Presentes_App/backups
Documents/Mistica_Presentes_App/ultimo_backup.json
Documents/Mistica_Presentes_App/updates
```

---

## 10. Recomendação de uso diário

```text
1. Abrir pelo MisticaLauncher.exe
2. Conferir se abriu sem erro
3. Abrir caixa
4. Vender normalmente
5. Fazer backup manual no fim do dia
6. Fechar caixa
7. Conferir valores por forma de pagamento
```

---

## Status

Sistema pronto para teste controlado em máquina real.

Se algum erro aparecer no teste real, registrar:

```text
- print da tela
- horário do erro
- ação que estava sendo feita
- se havia internet
- se foi venda, caixa, backup, sincronização ou atualização
```

# Atualização Online 1.0.500

## Primeira atualização oficial pelo Launcher

**Status:** Preparada

## Objetivo
Publicar a primeira atualização online para validar o fluxo completo do sistema:

```text
GitHub Actions
Publish Online Update
updates/manifest.json
MisticaLauncher.exe
Download automático antes do login
Backup pré-atualização
Abertura do sistema atualizado
```

---

## Conteúdo desta atualização

Esta versão consolida as etapas já implementadas:

```text
- Launcher inteligente
- Atualização online por canal de Windows
- Pagamento misto com até 4 formas
- Cupom com pagamento detalhado
- Caixa com pagamento separado por forma
- Estorno de venda mista separado por forma
- Backup automático ao iniciar
- Backup antes da atualização online
- Aba Manutenção para administradores
- Status de backup
- Status de sincronização
- Verificação do atualizador
- Fechamento de caixa avançado
```

---

## Versão

```text
1.0.500
```

---

## Como publicar

No GitHub Actions, rodar:

```text
Publish Online Update
```

Informar a versão:

```text
1.0.500
```

---

## Como testar depois de publicar

Na máquina da loja:

```text
1. Fechar o sistema se estiver aberto.
2. Abrir MisticaLauncher.exe.
3. Aguardar a verificação online.
4. Confirmar que o Launcher baixa a atualização.
5. Confirmar que o sistema abre normalmente.
6. Entrar na aba Manutenção.
7. Verificar backup e sincronização.
```

---

## Resultado esperado

```text
O Launcher deve detectar a versão 1.0.500, baixar o pacote, criar backup pré-atualização e abrir o sistema atualizado.
```

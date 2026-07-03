# Auditoria de aprovação - Mística Presentes

Data: 03/07/2026

## Resultado geral

Status: **aprovação parcial**.

O sistema principal da loja, a API, o painel mobile e o instalador já possuem a estrutura necessária para funcionar. Durante a auditoria foram encontrados alguns pontos que precisavam de correção antes da aprovação total.

## Itens verificados

### 1. Inicialização do programa desktop

Arquivo verificado: `app.py`.

O launcher carrega `mistica_presentes.py` a partir da pasta interna do executável (`_MEIPASS`) ou da pasta do projeto. Isso é correto para executável PyInstaller, desde que o arquivo `mistica_presentes.py` seja incluído como dado interno no build.

Conclusão: **correto com uso do arquivo spec**.

### 2. Build do EXE correto

Arquivo verificado: `MisticaPresentes_CORRETO.spec`.

O spec inclui os arquivos internos necessários:

- `mistica_presentes.py`
- `app_runtime_patch.py`
- `app_sync_status_patch.py`
- `app_scroll_patch.py`
- `config.py`
- `database`
- `services`
- `isis`
- `backend`
- `painel`

Conclusão: **correto**.

Correção aplicada: o gerador `installer/Gerar_EXE_CORRETO_Area_Trabalho.bat` foi ajustado para usar o arquivo `.spec`, evitando o erro "Arquivo principal não encontrado".

### 3. Configuração oficial do painel

Arquivo verificado: `config.py`.

Problema encontrado: o `DEFAULT_SERVER_URL` apontava para:

`https://api.misticaesotericos.com.br/painel/`

Essa rota não existe na API e retorna `Not Found`. O painel correto é:

`https://misticaesotericos.com.br/painel/`

Correção aplicada: `DEFAULT_SERVER_URL` foi atualizado para a área interna correta do site.

Conclusão: **corrigido**.

### 4. API oficial

Arquivo verificado: `backend/main.py`.

Endpoints existentes e esperados:

- `GET /`
- `GET /api/health`
- `GET /api/status`
- `POST /api/auth/login`
- `GET /api/painel/resumo`
- `GET /api/produtos`
- `POST /api/produtos`
- `GET /api/clientes`
- `POST /api/clientes`
- `GET /api/vendas`
- `POST /api/vendas`
- `POST /api/sync/venda`
- `GET /api/estoque/baixo`

Conclusão: **funcional**.

Observação: a API serve dados. A tela visual do painel fica em `https://misticaesotericos.com.br/painel/`, não dentro da rota `/painel/` da API.

### 5. Sincronização de usuários do programa com o app

Arquivos verificados:

- `backend/user_sync_routes.py`
- `services/usuario_sync_service.py`

A API recebeu a rota:

`POST /api/sync/usuarios`

O serviço desktop envia:

- nome
- login
- hash da senha
- salt
- perfil
- ativo

Conclusão: **estrutura criada**.

Ponto de atenção: o envio automático após login ainda depende de ligação no runtime do desktop. O serviço já existe e pode ser executado manualmente com:

```bash
python -c "from services.usuario_sync_service import sincronizar_usuarios_com_api; print(sincronizar_usuarios_com_api())"
```

### 6. Instalador para Windows 10 e Windows 11

Arquivos verificados:

- `installer/Gerar_Instalador_Area_Trabalho.bat`
- `installer/Instalar_Mistica_Presentes.bat`
- `servidor_app.py`

O gerador cria uma pasta de instalação na Área de Trabalho:

`Instalador_Mistica_Presentes`

O instalador copia:

- Programa Mística Presentes
- Servidor do Aplicativo

Conclusão: **funcional para instalação por pasta**.

Ponto de atenção: ainda não é instalador profissional `.msi`; é um instalador `.bat` simples e prático.

### 7. Servidor local do aplicativo

Arquivo verificado: `servidor_app.py`.

O servidor inicia `backend.main:app` com `uvicorn` em:

`http://127.0.0.1:8000`

Conclusão: **funcional se as dependências estiverem empacotadas no build**.

### 8. Botão Mostrar senha

Situação: **não aprovado ainda**.

A alteração foi solicitada para:

- login do desktop
- login do painel mobile

Durante tentativas anteriores, a alteração automática foi bloqueada pela ferramenta de escrita. Portanto, não há confirmação de que o botão esteja instalado no repositório.

Correção necessária antes da aprovação total: aplicar manualmente ou por Codex local nos arquivos:

- `mistica_presentes.py`
- `painel/index.html`

## Correções aplicadas nesta auditoria

1. Corrigido `config.py` para apontar o painel para:

`https://misticaesotericos.com.br/painel/`

2. Corrigido `installer/Gerar_EXE_CORRETO_Area_Trabalho.bat` para usar:

`MisticaPresentes_CORRETO.spec`

3. Criado este relatório de auditoria.

## Pendências para aprovação total

### Pendência 1 - testar novo EXE correto

Rodar:

```bash
cd /c/Users/fredi/BruxoBR/misticapresentes
git pull origin main
./installer/Gerar_EXE_CORRETO_Area_Trabalho.bat
```

Abrir:

`C:\Users\fredi\Desktop\mistica exe correto\MisticaPresentes_CORRETO.exe`

Resultado esperado: abrir o sistema sem erro de `mistica_presentes.py` não encontrado.

### Pendência 2 - testar sincronização de usuários

Rodar:

```bash
python -c "from services.usuario_sync_service import sincronizar_usuarios_com_api; print(sincronizar_usuarios_com_api())"
```

Resultado esperado:

`status: ok`

### Pendência 3 - aplicar Mostrar senha

Aplicar nos dois pontos:

- login desktop
- login web/mobile

## Veredito

Aprovação recomendada: **aprovar para teste interno**.

Não recomendar ainda para instalação em todos os computadores da loja antes de:

1. gerar novamente o EXE pelo spec;
2. confirmar que o EXE abre sem erro;
3. confirmar sincronização de usuários;
4. aplicar e testar o botão Mostrar senha.

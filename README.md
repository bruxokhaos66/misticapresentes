# Mística Presentes

Sistema desktop em Python para gestão da loja Mística Presentes.

## Recursos principais

- Dashboard com indicadores da loja.
- Vendas com carrinho, conferência antes de salvar e cupom.
- Controle de estoque, custo, margem, preço e estoque mínimo.
- Clientes, fornecedores, marketing e relatórios.
- Financeiro com caixa diário, contas a pagar, fluxo de caixa e DRE.
- Administração de usuários e logs de auditoria.
- Isis a Bruxinha com comandos operacionais, memória local e pesquisa web.

## Site e domínio oficial

O domínio oficial configurado para publicação é:

```text
misticaesotericos.com.br
```

O arquivo `CNAME` mantém o domínio configurado para o GitHub Pages.

O arquivo `site-config.js` centraliza os dados públicos do site, incluindo domínio oficial, URL pública, modo de produção, Instagram e WhatsApp.

Enquanto o DNS do Registro.br propaga, o site continua funcionando pelo endereço padrão do GitHub Pages. Depois da propagação, o acesso deve ser feito pelo domínio oficial.

## Requisitos

- Windows 10 ou 11.
- Python 3.12 ou superior recomendado.
- Git instalado.

## Instalação

Abra o terminal dentro da pasta do projeto e rode:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Como executar

Entrada recomendada:

```bash
python app.py
```

Também é possível executar diretamente:

```bash
python mistica_presentes.py
```

## Login inicial

No primeiro uso, o sistema cria o usuário `admin` com uma senha temporária segura.

A senha fica em um arquivo local dentro da pasta Documentos:

```text
mistica_senha_admin_inicial.txt
```

Por segurança, a senha antiga `admin/admin` fica bloqueada.

## Banco de dados

O banco local padrão é criado na pasta Documentos:

```text
mistica_gestao_v20.db
```

Se o modo rede estiver configurado, o caminho do banco pode ser lido de:

```text
mistica_config_rede.json
```

## Backup

O sistema realiza backup automático na saída e durante operações importantes. Os backups ficam na pasta local de backups configurada pelo sistema.

Não envie arquivos `.db`, backups ou logs para o GitHub.

## Pesquisa web da Isis

A pesquisa web usa o pacote `ddgs`, já listado em `requirements.txt`.

Exemplo de comando dentro da Isis:

```text
pesquise na internet fornecedores de incensos atacado
```

## Gerar executável

Exemplo básico com PyInstaller:

```bash
pyinstaller --onefile --windowed app.py --name "Mistica Presentes"
```

Depois de gerar o executável, teste vendas, estoque, login, caixa e relatórios antes de usar em produção.

## Cuidados importantes

- Não versionar `.env`.
- Não versionar banco `.db`.
- Não versionar `build/`, `dist/` e `__pycache__/`.
- Fazer backup antes de grandes alterações.
- Testar o sistema com dados fictícios antes de vender de verdade.

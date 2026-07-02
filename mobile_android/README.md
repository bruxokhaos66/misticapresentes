# Mística Painel Android

Aplicativo Android para acompanhar o painel da loja pelo celular.

Esta versão usa um app nativo com WebView, tela de configuração premium e seção Sobre / Atualização. Ele abre o painel local criado pela API do Mística Presentes.

## Visual e experiência

- Tela inicial mais bonita e fácil de entender.
- Identidade visual escura, dourada e mística.
- Cartão de conexão com instruções claras.
- Campo para endereço do servidor.
- Campo para token da API.
- Botão de atualizar painel.
- Botão de configuração sempre visível.
- Status de conexão: CONFIG, ABRINDO, ONLINE ou ERRO.
- Botão para limpar configuração.
- Tela Sobre / Atualização.

## Sobre / Atualização

A seção mostra:

- versão instalada do app;
- código interno da versão;
- servidor configurado;
- versão disponível informada pela API da loja;
- botão Verificar atualização.

Quando houver nova versão, o app avisa para gerar um novo APK no computador e instalar por cima do app atual.

## O que o app faz

- Abre o painel mobile da loja.
- Permite configurar o endereço do servidor local.
- Salva o endereço e o token no celular.
- Atualiza as informações em tempo real pelo painel WebSocket.
- Funciona dentro da rede Wi-Fi da loja.
- Verifica a versão disponível no servidor local.

## O que o app ainda não faz

- Não registra venda.
- Não altera estoque.
- Não fecha caixa.
- Não atualiza sozinho pela Play Store.
- Não acessa fora da loja sem uma conexão segura configurada.

## Como usar

1. No computador principal da loja, iniciar a API:

```bash
python scripts/iniciar_servidor_local.py
```

2. Anotar o endereço mostrado no terminal, por exemplo:

```text
http://192.168.0.115:8000
```

3. Abrir o app no celular.
4. Informar o endereço do servidor.
5. Informar o token da API.
6. Tocar em `Salvar e abrir painel`.

## Como verificar atualização

1. Abra o app.
2. Toque em `Sobre` ou no botão de configuração.
3. Confira a versão instalada.
4. Toque em `Verificar atualização`.

## Como abrir no Android Studio

1. Instale o Android Studio.
2. Abra a pasta:

```text
mobile_android
```

3. Espere o Gradle sincronizar.
4. Conecte o celular Android por USB ou use um emulador.
5. Clique em Run.

## Como gerar APK

No Android Studio:

```text
Build > Generate App Bundles or APKs > Generate APK
```

O APK será gerado em:

```text
mobile_android/app/build/outputs/apk/debug/app-debug.apk
```

## Segurança

Use somente dentro da rede da loja.

Não abra portas do roteador diretamente para a internet.

Para acompanhar fora da loja, use uma solução segura como VPN, Tailscale ou Cloudflare Tunnel.

## Próximas etapas

- Tela de login visual no app.
- Notificações de venda nova.
- Atalho para favoritos.
- Versão PWA instalável.
- Futuramente, operações autorizadas como estoque e caixa.

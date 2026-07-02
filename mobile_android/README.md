# Mística Painel Android

Aplicativo Android para acompanhar o painel da loja pelo celular.

Esta versão usa um app nativo com WebView e tela de configuração premium. Ele abre o painel local criado pela API do Mística Presentes.

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

## O que o app faz

- Abre o painel mobile da loja.
- Permite configurar o endereço do servidor local.
- Salva o endereço e o token no celular.
- Atualiza as informações em tempo real pelo painel WebSocket.
- Funciona dentro da rede Wi-Fi da loja.

## O que o app ainda não faz

- Não registra venda.
- Não altera estoque.
- Não fecha caixa.
- Não acessa fora da loja sem VPN/Tailscale/Cloudflare Tunnel.

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
5. Token padrão:

```text
mistica-local
```

6. Tocar em `Salvar e abrir painel`.

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
Build > Build Bundle(s) / APK(s) > Build APK(s)
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

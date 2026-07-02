# Mística Painel Android

Aplicativo Android para acompanhar o painel da loja pelo celular.

Esta versão usa um app nativo com WebView, tela de configuração premium, seção Sobre / Atualização e suporte a endereço externo seguro em HTTPS.

## Atualização online

O app funciona como um container que abre o painel web do servidor da loja.

Por isso, várias melhorias passam a ser atualizadas online, sem reinstalar APK:

- layout do painel;
- cards;
- textos;
- indicadores;
- alertas;
- dashboard;
- novas seções web.

Essas mudanças ficam no arquivo:

```text
api/painel.html
```

Depois de atualizar o GitHub, basta rodar no computador da loja:

```bash
git pull origin main
```

E reiniciar o servidor dedicado:

```bash
python scripts/iniciar_servidor_dedicado.py
```

Ao abrir o app no celular, ele carrega o painel atualizado.

Mudanças nativas do Android, como ícone, permissões, nome do app e tela nativa de configuração, ainda exigem gerar um novo APK. Isso é uma regra de segurança do Android.

## Visual e experiência

- Tela inicial mais bonita e fácil de entender.
- Identidade visual escura, dourada e mística.
- Cartão de conexão com instruções claras.
- Campo para endereço do servidor.
- Aceita endereço local `http://` e endereço externo seguro `https://`.
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

Quando houver nova versão nativa, o app avisa para gerar um novo APK no computador e instalar por cima do app atual.

## O que o app faz

- Abre o painel mobile da loja.
- Permite configurar o endereço do servidor.
- Salva o endereço e o token no celular.
- Atualiza as informações em tempo real pelo painel WebSocket.
- Funciona dentro da rede Wi-Fi da loja.
- Funciona fora da loja quando usado com endereço externo seguro.
- Verifica a versão disponível no servidor.

## O que o app ainda não faz

- Não registra venda.
- Não altera estoque.
- Não fecha caixa.
- Não atualiza sozinho pela Play Store.

## Como usar dentro da loja

1. No computador principal da loja, iniciar o servidor dedicado:

```bash
python scripts/iniciar_servidor_dedicado.py
```

2. Anotar o endereço mostrado no terminal, por exemplo:

```text
http://192.168.0.115:8000
```

3. Abrir o app no celular.
4. Informar o endereço do servidor.
5. Informar o token da API.
6. Tocar em `Salvar e abrir painel`.

## Como usar fora da loja

Configure um acesso externo seguro apontando para o servidor dedicado, como VPN, Tailscale ou Cloudflare Tunnel.

Depois coloque no app um endereço em HTTPS, por exemplo:

```text
https://seu-endereco-seguro
```

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

Não abra portas do roteador diretamente para a internet.

Para acompanhar fora da loja, use uma solução segura como VPN, Tailscale ou Cloudflare Tunnel.

## Próximas etapas

- Tela de login visual no app.
- Notificações de venda nova.
- Atalho para favoritos.
- Melhorias no painel web online.
- Futuramente, operações autorizadas como estoque e caixa.

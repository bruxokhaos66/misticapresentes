# Atualização online do app Android

## Como funciona

O app Android da Mística funciona como um container nativo que abre o painel web servido pelo computador/servidor da loja.

Isso significa que várias melhorias podem ser feitas sem instalar APK novo no celular.

## Atualiza online, sem novo APK

Podem ser atualizados pelo servidor:

- layout do painel;
- cards;
- cores;
- textos;
- indicadores;
- relatórios exibidos;
- alertas da Isis;
- dashboard;
- regras de exibição;
- novas seções web;
- melhorias no painel mobile.

Essas mudanças ficam no arquivo:

```text
api/painel.html
```

Depois de alterar o painel no GitHub, basta rodar no computador da loja:

```bash
git pull origin main
```

Depois reinicie o servidor dedicado:

```bash
python scripts/iniciar_servidor_dedicado.py
```

Ao abrir o app no celular, ele carregará o painel novo.

## Ainda precisa de APK novo

O Android ainda exige APK novo quando mudar algo nativo do app, como:

- ícone do app;
- nome do app;
- permissões Android;
- WebView nativa;
- tela nativa de configuração;
- botão nativo de Sobre;
- recursos que não vêm do painel web.

Isso é uma limitação de segurança do Android.

## Estratégia recomendada

A partir de agora, colocar o máximo possível de funções dentro do painel web `api/painel.html`.

Assim o app instalado no celular fica estável e quase todas as melhorias são feitas online pelo servidor.

## Para acesso fora da loja

Use o servidor dedicado com acesso externo seguro por Tailscale, VPN ou Cloudflare Tunnel.

No app Android, configure o endereço externo seguro em HTTPS quando disponível.

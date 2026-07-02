# Servidor dedicado do Mística Presentes

## Objetivo

Permitir que o painel e o app Android continuem acessando as informações da loja mesmo com o programa desktop fechado.

O computador principal da loja precisa estar ligado e o servidor dedicado precisa estar rodando.

## Como iniciar

Na pasta do projeto:

```bash
python scripts/iniciar_servidor_dedicado.py
```

O terminal mostrará:

```text
Local:      http://127.0.0.1:8000
Rede loja:  http://IP-DA-LOJA:8000
```

## Diferença para o programa desktop

O programa desktop é usado para vender, cadastrar produtos e controlar a loja.

O servidor dedicado é usado para consulta pelo painel e pelo app Android.

Eles são separados. O desktop pode estar fechado e o painel continua funcionando, desde que o servidor dedicado esteja aberto.

## Acesso dentro da loja

No app Android, use o endereço local da rede:

```text
http://IP-DA-LOJA:8000
```

Exemplo:

```text
http://192.168.0.115:8000
```

## Acesso de fora da loja

Para acessar de qualquer lugar pela internet, use um acesso externo seguro apontando para o servidor dedicado.

Opções recomendadas:

- Tailscale;
- VPN;
- Cloudflare Tunnel.

Não é recomendado abrir porta do roteador diretamente para a internet.

Quando o acesso externo estiver configurado, o app Android poderá usar um endereço seguro em HTTPS, por exemplo:

```text
https://seu-endereco-seguro
```

## Token

O token padrão local continua sendo:

```text
mistica-local
```

Para produção, troque o token com variável de ambiente:

```bash
set MISTICA_API_TOKEN=um-token-forte
python scripts/iniciar_servidor_dedicado.py
```

Depois configure o mesmo token no app Android.

## Próximo passo profissional

Para o servidor iniciar automaticamente com o Windows, configure o script `scripts/iniciar_servidor_dedicado.py` na inicialização do sistema ou no Agendador de Tarefas do Windows.

## Limite importante

Se o computador principal da loja estiver desligado, o servidor dedicado local também ficará indisponível.

Para funcionar mesmo com o computador da loja desligado, a próxima etapa seria contratar um servidor em nuvem com banco online e criar sincronização segura dos dados.

# Isis — Chat Inteligente (homologação controlada)

## Objetivo

Homologar, de forma controlada, o chat inteligente da Isis 2.0 focado em
**recomendação de produtos e apoio comercial** dentro do site (busca de
produtos/kits/cursos, comparação objetiva, orçamento). Este módulo **não**
ativa o Estúdio Inteligente de Conteúdo (Fase 3, `backend/isis_content_*`),
não gera conteúdo automaticamente, não gera imagem, não publica nada e não
integra com Instagram, Facebook, WhatsApp ou qualquer rede social.

O chat funciona hoje inteiramente em **modo determinístico** (sem provedor
de IA externo, sem chave de API, custo zero) e usa apenas o catálogo real
da loja (produtos ativos e cursos ativos da Escola Mística) como fonte de
verdade.

## Arquitetura (10 camadas)

| Camada | Arquivo |
| --- | --- |
| 1. Autorização de homologação | `backend/isis_chat_auth.py` (reaproveita `backend/isis2_homolog.py`, PR #354) |
| 2. Sessão de conversa | `backend/isis_chat_session.py` |
| 3. Interpretação de intenção | `backend/isis_chat_intent.py` |
| 4. Busca no catálogo | `backend/isis_chat_catalog.py` |
| 5–6. Ranqueamento de produtos | `backend/isis_chat_ranking.py` |
| Abstração de IA | `backend/isis_chat_providers.py` |
| 7–8. Orquestração, limites e observabilidade | `backend/isis_chat_service.py` |
| 9. Interface web (endpoints públicos) | `backend/isis_chat_routes.py`, `isis2/chat-gate.js`, `isis2/chat-widget.js`/`.css` |
| 10. Painel administrativo | `backend/isis_chat_admin_routes.py`, `isis2-chat-admin.js` |

## Flags

Independentes das quatro flags do Estúdio de Conteúdo (Fase 3) —
`backend/isis_chat_flags.py` nunca lê nem escreve nelas.

```
MISTICA_ISIS_CHAT_ENABLED=false                      # chat aparece para clientes comuns
MISTICA_ISIS_CHAT_HOMOLOG_ENABLED=false               # restringe a admin/allowlist
MISTICA_ISIS_CHAT_AI_ENABLED=false                    # modo determinístico quando false
MISTICA_ISIS_CHAT_PRODUCT_RECOMMENDATIONS_ENABLED=false

MISTICA_ISIS_CHAT_MAX_MESSAGES_PER_SESSION=20
MISTICA_ISIS_CHAT_MAX_SESSIONS_PER_HOUR=5
MISTICA_ISIS_CHAT_MESSAGE_MAX_LENGTH=1000
MISTICA_ISIS_CHAT_SESSION_TTL_MINUTES=60
MISTICA_ISIS_CHAT_DAILY_AI_CALL_LIMIT=0
MISTICA_ISIS_CHAT_DAILY_COST_LIMIT_CENTS=0
```

As quatro flags do Estúdio de Conteúdo (Fase 3) **permanecem `false`** e
não são tocadas por este trabalho:

```
MISTICA_ISIS_CONTENT_STUDIO_ENABLED=false
MISTICA_ISIS_CONTENT_AUTO_GENERATION_ENABLED=false
MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED=false
MISTICA_ISIS_CONTENT_AUTO_PUBLISH_ENABLED=false
```

Todas as flags são lidas **só no backend** (`os.environ`, nunca query
string/header/cookie/`localStorage`). O frontend (`isis2/chat-gate.js`)
só confia na resposta de `GET /api/isis2/chat/config` — nunca decide
sozinho se deve mostrar o widget.

## Modo sem IA

Com `MISTICA_ISIS_CHAT_AI_ENABLED=false` (default), toda mensagem passa
por `backend/isis_chat_providers.DeterministicChatProvider`: nenhuma
chamada de rede, custo zero, respostas construídas por regras +
busca/ranqueamento reais do catálogo (`backend/isis_chat_intent.py`,
`backend/isis_chat_ranking.py`). Intenções reconhecidas: buscar produto,
pedir recomendação, informar finalidade/aroma/faixa de preço, comparar
produtos, montar kit, pedir complementar, buscar curso, perguntar
disponibilidade/preço/modo de uso.

Se `MISTICA_ISIS_CHAT_AI_ENABLED=true` mas nenhum provedor de IA real
estiver configurado (nenhuma chave de API existe no código nesta fase),
`DisabledAIChatProvider` registra o erro e cai no mesmo fallback
determinístico — o chat nunca quebra.

## Homologação e autorização

Reaproveita a mesma allowlist fechada da PR #354
(`isis2_homolog_testers`) e as mesmas sessões HttpOnly já existentes
(`mistica_painel_sessao` para admin, `mistica_aluno_sessao` para aluno):

- admin autenticado é sempre autorizado automaticamente;
- aluno autenticado só é autorizado se estiver na allowlist;
- com `MISTICA_ISIS_CHAT_ENABLED` ou `MISTICA_ISIS_CHAT_HOMOLOG_ENABLED`
  desligada, ninguém tem acesso (nem admin) — as rotas de chat respondem
  404;
- qualquer erro, sessão ausente/expirada ou conta fora da allowlist
  resulta em "não autorizado" (fail closed).

Ver `backend/isis_chat_auth.py`.

## Limites

| Limite | Variável | Onde é aplicado |
| --- | --- | --- |
| Mensagens por sessão | `MISTICA_ISIS_CHAT_MAX_MESSAGES_PER_SESSION` | `backend/isis_chat_session.registrar_mensagem` |
| Sessões novas por hora (por conta) | `MISTICA_ISIS_CHAT_MAX_SESSIONS_PER_HOUR` | `backend/isis_chat_session.criar_sessao` |
| Tamanho máximo da mensagem | `MISTICA_ISIS_CHAT_MESSAGE_MAX_LENGTH` | `backend/isis_chat_service.sanitizar_entrada` |
| TTL da sessão | `MISTICA_ISIS_CHAT_SESSION_TTL_MINUTES` | `backend/isis_chat_session` |
| Rate limit por IP | fixo (10 sessões/min, 30 mensagens/min) | `backend/rate_limit.limitar_requisicoes` (já trata `X-Forwarded-For`) |
| Resultados consultados no catálogo | fixo (100) | `backend/isis_chat_service._LIMITE_RESULTADOS_CONSULTADOS` |
| Chamadas de IA / custo diário | `MISTICA_ISIS_CHAT_DAILY_AI_CALL_LIMIT` / `_COST_LIMIT_CENTS` | sempre 0 com IA desligada |

## Métricas

`isis_chat_metrics` (contadores, sem dado pessoal): `sessao_iniciada`,
`mensagem_recebida`, `recomendacoes_exibidas`, `kit_sugerido`,
`fallback_sem_resultado`, `prompt_injection_bloqueado`,
`dado_sensivel_orientado`. Consultar agregado em
`GET /api/admin/isis2/chat/metricas`.

## Privacidade

Aviso fixo no widget: "A Isis usa as informações desta conversa apenas
para ajudar na recomendação de produtos e melhorar o atendimento." A
sessão nunca guarda o texto integral da conversa (só um resumo curto por
mensagem, intenção, preferências, faixa de preço e IDs sugeridos). Se o
cliente enviar CPF/cartão/dado sensível, a Isis não repete o valor e
orienta a não enviar esse tipo de informação (`isis_chat_service.py`).

## Como ativar (homologação)

1. No servidor: `MISTICA_ISIS_CHAT_ENABLED=true` e
   `MISTICA_ISIS_CHAT_HOMOLOG_ENABLED=true` (as quatro flags do Estúdio
   de Conteúdo continuam `false`).
2. Um admin autenticado já pode testar automaticamente.
3. Para autorizar um aluno de teste, use a mesma allowlist da
   homologação da PR #354 (`POST /api/isis2/homolog-testers/{aluno_id}`,
   ver `isis2-homolog-admin.js`).
4. Abrir o site normalmente: com autorização confirmada pelo servidor, o
   botão flutuante "Falar com a Isis" aparece no canto inferior esquerdo,
   com o selo "Isis em homologação".

## Como desativar

Basta desligar `MISTICA_ISIS_CHAT_ENABLED` (ou
`MISTICA_ISIS_CHAT_HOMOLOG_ENABLED`) no ambiente do servidor e reiniciar
o processo — as rotas de chat voltam a responder 404 e o widget não
monta em nenhuma página. Não requer deploy manual adicional além da
troca da variável de ambiente já usada pelo processo em execução.

## Como testar

Backend: `python -m pytest tests/test_isis_chat.py`.
Frontend/E2E: `npx playwright test tests/e2e/isis-chat-widget.spec.js`.

## Como verificar custo zero

Com `MISTICA_ISIS_CHAT_AI_ENABLED=false` (default), `GET
/api/admin/isis2/chat/metricas` sempre mostra
`chamadas_ia_hoje: 0` e `custo_estimado_centavos_hoje: 0` — nenhuma rota
deste módulo chama um provedor de IA externo nesse modo (ver
`backend/isis_chat_providers.DeterministicChatProvider`, que nunca faz
requisição de rede).

## Como limpar sessões expiradas

`POST /api/admin/isis2/chat/sessoes/limpar-expiradas` (admin), ou pelo
painel "Isis — Chat Inteligente" em `admin.html`, botão "Limpar sessões
expiradas". Gera log de auditoria (`isis_chat_audit_log` via
`backend/audit.registrar_auditoria`).

## Troubleshooting

| Sintoma | Causa provável |
| --- | --- |
| Widget não aparece mesmo logado como admin | Confirme `MISTICA_ISIS_CHAT_ENABLED=true` e `MISTICA_ISIS_CHAT_HOMOLOG_ENABLED=true` no servidor (não no navegador) |
| `404` em qualquer rota `/api/isis2/chat/*` | Uma das duas flags acima está desligada — comportamento esperado (fail closed) |
| `401` ao criar sessão | Conta não autorizada — aluno fora da allowlist, ou sessão de admin/aluno expirada |
| `429` ao enviar mensagem/criar sessão | Limite de mensagens por sessão, sessões por hora ou rate limit por IP atingido — ver seção "Limites" |
| Resposta sempre "não encontrei" | Catálogo sem produtos ativos correspondentes — não é um bug, é o comportamento de "nunca inventar" |

## Procedimento de rollback

1. Definir `MISTICA_ISIS_CHAT_ENABLED=false` no ambiente do servidor e
   reiniciar o processo — efeito imediato, sem precisar reverter código.
2. Se necessário reverter o código: `git revert` dos commits deste PR
   (nenhuma migração destrutiva foi criada — as tabelas novas
   `isis_chat_*` podem ser mantidas ou removidas manualmente sem afetar
   `produtos`, `pedidos`, `cursos_materiais` ou qualquer tabela da
   Escola/checkout/pagamento).

## Fora de escopo (garantidamente não implementado)

Estúdio Inteligente de Conteúdo, geração automática/de imagem,
publicação automática, integração com redes sociais, alteração de
checkout/pagamentos/pedidos/estoque/regras da Escola, deploy manual,
credenciais reais ou chaves de API no código, merge automático.

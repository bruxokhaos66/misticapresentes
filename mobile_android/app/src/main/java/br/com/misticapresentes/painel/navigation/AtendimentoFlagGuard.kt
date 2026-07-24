package br.com.misticapresentes.painel.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.FeatureFlagsRepository

/**
 * Defesa em profundidade da Central de Atendimento nativa (PR #412): garante
 * que nenhuma rota da Central (lista/detalhe) chegue a compor seu conteúdo
 * real -- e portanto nenhum ViewModel/Repository seja instanciado nem
 * nenhuma chamada de API aconteça -- quando `FeatureFlag.NATIVE_WHATSAPP_ENABLED`
 * está desligada, mesmo que a navegação até a rota não tenha passado pelo
 * botão da Home (navegação programática direta, ou restauração de back stack
 * com a rota nativa salva de uma sessão anterior).
 *
 * Importante: esta flag é só uma decisão de UI (visibilidade), NUNCA uma
 * autorização -- ela não substitui e não enfraquece nenhuma validação de
 * sessão/perfil que o backend já faz em cada chamada de `AtendimentoApi`.
 * Com a flag ligada, toda ação continua sujeita às mesmas regras de sempre
 * no servidor.
 *
 * Reavalia a flag a cada composição (o `remember`/`LaunchedEffect` abaixo são
 * escopados a esta entrada específica na árvore de composição -- uma nova
 * entrada, como a que a navegação cria ao recompor a rota, começa do zero),
 * então cobre tanto a navegação inicial quanto a restauração do back stack
 * (processo recriado com a rota ainda salva) e uma eventual mudança de valor
 * da flag enquanto a rota está montada.
 *
 * Usa `remember` + `LaunchedEffect` em vez de `produceState` de propósito:
 * `produceState` colide com o lint `ProduceStateDoesNotAssignValue` quando a
 * atribuição de `value` acontece dentro do `collect { }` de um Flow (o lint
 * não enxerga essa atribuição indireta), então preferimos este padrão mais
 * explícito, que tem exatamente a mesma semântica.
 */
@Composable
fun AtendimentoFlagGuard(
    featureFlagsRepository: FeatureFlagsRepository,
    onDenied: () -> Unit,
    content: @Composable () -> Unit,
) {
    // `null` = ainda não chegou o primeiro valor do Flow (evita expulsar a
    // tela por um instante mesmo com a flag ligada, só por causa do delay
    // natural de coletar o primeiro valor de um Flow assíncrono).
    var enabled by remember(featureFlagsRepository) { mutableStateOf<Boolean?>(null) }

    LaunchedEffect(featureFlagsRepository) {
        featureFlagsRepository.isEnabled(FeatureFlag.NATIVE_WHATSAPP_ENABLED).collect { enabled = it }
    }

    // onDenied() navega (efeito colateral) -- precisa rodar fora da fase de
    // composição, daí o LaunchedEffect em vez de chamar direto no `when`.
    LaunchedEffect(enabled) {
        if (enabled == false) onDenied()
    }

    if (enabled == true) {
        content()
    }
}

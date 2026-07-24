package br.com.misticapresentes.painel.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
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
 * Reavalia a flag a cada composição (não guarda estado fora do Composable),
 * então cobre tanto a navegação inicial quanto a restauração do back stack
 * (processo recriado com a rota ainda salva) e uma eventual mudança de valor
 * da flag enquanto a rota está montada.
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
    val enabled by produceState<Boolean?>(initialValue = null, featureFlagsRepository) {
        featureFlagsRepository.isEnabled(FeatureFlag.NATIVE_WHATSAPP_ENABLED).collect { value = it }
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

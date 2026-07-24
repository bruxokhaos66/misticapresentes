package br.com.misticapresentes.painel.testutil

import br.com.misticapresentes.painel.common.FeatureFlag
import br.com.misticapresentes.painel.common.FeatureFlagsRepository
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow

/**
 * Fake em memória de [FeatureFlagsRepository]. Usado para testar ViewModels
 * sem depender do DataStore real (evita acoplar o teste ao timing
 * assíncrono de I/O real do DataStore, que roda em um dispatcher próprio,
 * não controlado pelo TestDispatcher do teste).
 */
class FakeFeatureFlagsRepository(
    initialOverrides: Map<FeatureFlag, Boolean> = emptyMap(),
) : FeatureFlagsRepository {

    private val flags = FeatureFlag.entries.associateWith { flag ->
        MutableStateFlow(initialOverrides[flag] ?: flag.defaultValue)
    }

    override fun isEnabled(flag: FeatureFlag): Flow<Boolean> = flags.getValue(flag)

    override suspend fun setEnabled(flag: FeatureFlag, enabled: Boolean) {
        flags.getValue(flag).value = enabled
    }
}

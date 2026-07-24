package br.com.misticapresentes.painel.testutil

import br.com.misticapresentes.painel.common.LegacyPrefsMigrator

/** Fake no-op de [LegacyPrefsMigrator], para testar ViewModels sem SharedPreferences/DataStore reais. */
class FakeLegacyPrefsMigration : LegacyPrefsMigrator {
    var migrateCallCount = 0
        private set

    override suspend fun migrateIfNeeded() {
        migrateCallCount++
    }
}

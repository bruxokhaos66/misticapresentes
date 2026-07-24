package br.com.misticapresentes.painel.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

private val MisticaColorScheme = darkColorScheme(
    primary = MisticaGold,
    onPrimary = MisticaBackground,
    secondary = MisticaGreen,
    onSecondary = MisticaBackground,
    background = MisticaBackground,
    onBackground = MisticaTextPrimary,
    surface = MisticaSurface,
    onSurface = MisticaTextPrimary,
    surfaceVariant = MisticaSurfaceVariant,
    onSurfaceVariant = MisticaTextMuted,
    error = MisticaError,
    onError = MisticaTextPrimary,
)

/**
 * A identidade da Mística é intencionalmente sempre escura (dourado/verde
 * sobre fundo escuro) — não alterna com o tema claro do sistema, da mesma
 * forma que o app legado já era fixo em modo escuro.
 */
@Composable
fun MisticaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = MisticaColorScheme,
        typography = MisticaTypography,
        content = content,
    )
}

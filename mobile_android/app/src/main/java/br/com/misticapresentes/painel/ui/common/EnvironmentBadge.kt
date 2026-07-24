package br.com.misticapresentes.painel.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import br.com.misticapresentes.painel.common.Environment

/** Indicador visual de ambiente, sempre visível, para nunca confundir dev/homolog com produção. */
@Composable
fun EnvironmentBadge(environment: Environment, modifier: Modifier = Modifier) {
    Text(
        text = environment.label,
        color = MaterialTheme.colorScheme.primary,
        style = MaterialTheme.typography.labelSmall,
        modifier = modifier
            .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(999.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp)
            .semantics { contentDescription = "Ambiente: ${environment.label}" },
    )
}

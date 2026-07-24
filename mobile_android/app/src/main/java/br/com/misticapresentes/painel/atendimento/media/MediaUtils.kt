package br.com.misticapresentes.painel.atendimento.media

/**
 * Limites de tamanho para pré-checagem RÁPIDA no cliente antes de subir
 * imagem/áudio -- espelham os defaults de
 * `whatsapp_outbound_image_max_bytes()`/`whatsapp_outbound_audio_max_bytes()`
 * (`backend/whatsapp_flags.py`). Servem só para dar feedback imediato ao
 * usuário e evitar um upload inteiro fadado a um 413; o backend continua
 * sendo a única fonte de verdade real (o valor lá pode ter sido customizado
 * por variável de ambiente, então esta checagem é deliberadamente uma UX,
 * nunca um bloqueio definitivo de regra de negócio).
 */
object MediaLimits {
    const val MAX_IMAGE_BYTES: Long = 5L * 1024 * 1024
    const val MAX_AUDIO_BYTES: Long = 16L * 1024 * 1024
}

/** Formata milissegundos de gravação/áudio como "m:ss" (nunca negativo). */
fun formatRecordingDuration(elapsedMs: Long): String {
    val totalSeconds = (elapsedMs / 1000).coerceAtLeast(0)
    val minutes = totalSeconds / 60
    val seconds = totalSeconds % 60
    return "%d:%02d".format(minutes, seconds)
}

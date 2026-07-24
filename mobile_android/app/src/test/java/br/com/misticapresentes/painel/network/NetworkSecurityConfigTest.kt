package br.com.misticapresentes.painel.network

import java.io.File
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Rede de segurança estática: garante que a configuração usada em
 * homolog/prod (`network_security_config.xml`, o padrão) nunca libera
 * cleartext, e que a exceção de cleartext do flavor dev fica restrita aos
 * hosts locais de desenvolvimento. O teste lê o XML direto do módulo (não
 * depende de instrumentação), então falha o build se alguém reintroduzir
 * `cleartextTrafficPermitted="true"` de forma global.
 */
class NetworkSecurityConfigTest {

    private fun readConfig(fileName: String): String {
        val candidates = listOf(
            File("src/main/res/xml/$fileName"),
            File("app/src/main/res/xml/$fileName"),
        )
        val file = candidates.firstOrNull { it.exists() }
            ?: error("Não encontrei $fileName em nenhum dos caminhos esperados: $candidates")
        return file.readText()
    }

    @Test
    fun `default network security config never allows cleartext`() {
        val xml = readConfig("network_security_config.xml")
        assertTrue(xml.contains("cleartextTrafficPermitted=\"false\""))
        assertFalse(xml.contains("cleartextTrafficPermitted=\"true\""))
    }

    @Test
    fun `dev network security config only allows cleartext for local hosts`() {
        val xml = readConfig("network_security_config_dev.xml")
        assertTrue(xml.contains("<base-config cleartextTrafficPermitted=\"false\">"))

        val allowedCleartextHosts = setOf("10.0.2.2", "localhost", "127.0.0.1")
        val domainRegex = Regex("<domain[^>]*>([^<]+)</domain>")
        val domainsInCleartextBlock = domainRegex.findAll(
            xml.substringAfter("<domain-config cleartextTrafficPermitted=\"true\">"),
        ).map { it.groupValues[1].trim() }.toSet()

        assertTrue(domainsInCleartextBlock.isNotEmpty())
        assertTrue(allowedCleartextHosts.containsAll(domainsInCleartextBlock))
        assertFalse(domainsInCleartextBlock.any { it.contains("misticaesotericos") })
    }
}

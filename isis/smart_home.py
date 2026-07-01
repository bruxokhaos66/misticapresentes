"""Controle de automação local.
Por segurança, este módulo apenas registra a intenção e orienta integração futura.
Pode ser ligado depois a Home Assistant, Tuya, Smart Life ou comandos locais.
"""

def executar(texto):
    p = str(texto or "").lower()
    alvos = []
    if "luz" in p or "lampada" in p or "lâmpada" in p:
        alvos.append("luzes")
    if "ar condicionado" in p or "clima" in p:
        alvos.append("ar-condicionado")
    if not alvos:
        return None
    acao = "ligar" if any(x in p for x in ["ligar", "acender", "ativar"]) else "desligar" if any(x in p for x in ["desligar", "apagar", "desativar"]) else "acionar"
    return f"Comando recebido para {acao} {', '.join(alvos)}. Para executar de verdade, conecte este módulo ao Home Assistant/Tuya da loja."

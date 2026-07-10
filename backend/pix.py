from __future__ import annotations

import os
import re
import unicodedata


def _sanitizar_texto_pix(valor: str, tamanho_maximo: int) -> str:
    texto = unicodedata.normalize("NFD", str(valor or ""))
    texto = "".join(ch for ch in texto if unicodedata.category(ch) != "Mn")
    texto = re.sub(r"[^a-zA-Z0-9 .@+\-_]", "", texto)
    return texto.upper()[:tamanho_maximo]


def _emv(campo_id: str, valor: str) -> str:
    valor = str(valor)
    if len(valor) > 99:
        raise ValueError(f"Campo Pix {campo_id} excedeu 99 caracteres.")
    return f"{campo_id}{len(valor):02d}{valor}"


def _crc16(payload: str) -> str:
    crc = 0xFFFF
    for char in payload:
        crc ^= ord(char) << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return format(crc, "04X")


def montar_txid_pedido(pedido_id: int) -> str:
    """Gera um txid determinístico e ligado ao id real do pedido, para que o Pix
    exibido ao cliente e o pedido persistido no banco sejam sempre o mesmo."""
    return _sanitizar_texto_pix(f"MISTICA{pedido_id:09d}", 25) or "MISTICA"


def config_pix() -> dict:
    return {
        "chave": os.environ.get("MISTICA_PIX_KEY", "").strip(),
        "nome": os.environ.get("MISTICA_PIX_NOME", "").strip() or "MISTICA PRESENTES",
        "cidade": os.environ.get("MISTICA_PIX_CIDADE", "").strip() or "PINHALZINHO",
    }


def montar_payload_pix(*, chave: str, nome: str, cidade: str, valor: float, txid: str) -> str:
    if not chave:
        raise ValueError("Chave Pix não configurada.")
    conta_recebedor = _emv("26", _emv("00", "br.gov.bcb.pix") + _emv("01", str(chave).strip()))
    sem_crc = (
        _emv("00", "01")
        + conta_recebedor
        + _emv("52", "0000")
        + _emv("53", "986")
        + _emv("54", f"{float(valor):.2f}")
        + _emv("58", "BR")
        + _emv("59", _sanitizar_texto_pix(nome, 25) or "MISTICA PRESENTES")
        + _emv("60", _sanitizar_texto_pix(cidade, 15) or "PINHALZINHO")
        + _emv("62", _emv("05", _sanitizar_texto_pix(txid, 25) or "MISTICA"))
        + "6304"
    )
    return sem_crc + _crc16(sem_crc)


def gerar_pix_do_pedido(pedido_id: int, valor: float) -> dict | None:
    """Gera o payload Pix (copia e cola) ligado ao id real do pedido. Retorna None
    quando a chave Pix da loja não está configurada no ambiente do servidor, para
    não travar a criação do pedido por causa disso."""
    cfg = config_pix()
    if not cfg["chave"] or valor <= 0:
        return None
    txid = montar_txid_pedido(pedido_id)
    try:
        payload = montar_payload_pix(chave=cfg["chave"], nome=cfg["nome"], cidade=cfg["cidade"], valor=valor, txid=txid)
    except ValueError:
        return None
    return {"txid": txid, "copia_cola": payload}

def aplicar_sync_pagamento_misto_payload_runtime(fonte):
    """Inclui pagamentos_mistos no payload de sincronizacao sem alterar o sync_service inteiro."""
    try:
        from services.pagamento_misto_service import extrair_pagamentos_mistos
        import services.sync_service as sync_service

        original = getattr(sync_service, "montar_payload_venda", None)
        if original and not getattr(original, "_mistica_pagamento_misto_patch", False):
            def montar_payload_venda_com_pagamento_misto(venda_id):
                payload = original(venda_id)
                forma = payload.get("forma_pagamento", "")
                payload["pagamentos_mistos"] = extrair_pagamentos_mistos(forma)
                return payload

            montar_payload_venda_com_pagamento_misto._mistica_pagamento_misto_patch = True
            sync_service.montar_payload_venda = montar_payload_venda_com_pagamento_misto
    except Exception as exc:
        print(f"[Patch Sync Misto] {exc}")
    return fonte

"""Reconhecimento e fala opcionais para a Isis.

O sistema deve continuar funcionando por texto mesmo sem microfone, PyAudio
ou permissao de audio no Windows.
"""


def reconhecer_fala_ptbr(timeout=6, phrase_time_limit=10):
    try:
        import speech_recognition as sr
    except Exception as exc:
        raise RuntimeError("Reconhecimento de voz indisponivel: instale SpeechRecognition para usar este recurso opcional.") from exc

    try:
        mic = sr.Microphone()
    except Exception as exc:
        raise RuntimeError("Microfone indisponivel neste computador. A Isis continua funcionando por texto normalmente.") from exc

    rec = sr.Recognizer()
    try:
        with mic as source:
            rec.adjust_for_ambient_noise(source, duration=0.6)
            audio = rec.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    except Exception as exc:
        raise RuntimeError(f"Nao consegui acessar o microfone agora. Use texto normalmente. Detalhe: {exc}") from exc

    try:
        return rec.recognize_google(audio, language="pt-BR").strip()
    except sr.UnknownValueError:
        return ""
    except Exception as exc:
        raise RuntimeError(f"Falha ao reconhecer fala. Use texto normalmente. Detalhe: {exc}") from exc


def falar_texto(texto):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(str(texto))
        engine.runAndWait()
        return True
    except Exception:
        return False

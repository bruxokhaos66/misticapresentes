"""Reconhecimento de voz opcional para a Isis.
Funciona com speech_recognition quando instalado. Se não estiver instalado,
levanta uma mensagem clara para o sistema mostrar ao usuário.
"""

def reconhecer_fala_ptbr(timeout=6, phrase_time_limit=10):
    try:
        import speech_recognition as sr
    except Exception as exc:
        raise RuntimeError("Instale o pacote SpeechRecognition e PyAudio para usar o microfone.") from exc

    rec = sr.Recognizer()
    with sr.Microphone() as source:
        rec.adjust_for_ambient_noise(source, duration=0.6)
        audio = rec.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
    try:
        return rec.recognize_google(audio, language="pt-BR").strip()
    except sr.UnknownValueError:
        return ""
    except Exception as exc:
        raise RuntimeError(f"Falha ao reconhecer fala: {exc}") from exc


def falar_texto(texto):
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(str(texto))
        engine.runAndWait()
        return True
    except Exception:
        return False

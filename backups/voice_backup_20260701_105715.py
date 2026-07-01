def reconhecer_fala_ptbr():
    try:
        import speech_recognition as sr
    except Exception:
        raise RuntimeError("Para usar voz, instale: python -m pip install SpeechRecognition pyaudio")
    rec = sr.Recognizer()
    with sr.Microphone() as source:
        rec.adjust_for_ambient_noise(source, duration=0.5)
        audio = rec.listen(source, timeout=6, phrase_time_limit=12)
    return rec.recognize_google(audio, language="pt-BR")


def falar_texto(texto):
    try:
        import pyttsx3
    except Exception:
        return False
    engine = pyttsx3.init()
    engine.say(texto)
    engine.runAndWait()
    return True

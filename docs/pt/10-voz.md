# 10. Voz (STT / TTS)

[← Operação](06-operacao.md) · [Índice](README.md)

---

## Arquitetura

```text
Microfone → STT 9router → GameMasterRuntime (LLM 9router + tools)
  → Campaign State gravado
  → VoiceDirector → TTS ElevenLabs (ou mock / TTS 9router)
  → WebSocket gm_audio → Vue reproduz os bytes
```

A API key nunca sai do backend. O browser só recebe `content_type` + `data_base64`.

## Setup

```bash
VOICE_TTS_PROVIDER=elevenlabs
ELEVENLABS_ENABLED=true
ELEVENLABS_API_KEY=          # segredo que começa com sk_ (não o ID da key)
ELEVENLABS_DEFAULT_VOICE_ID=
ELEVENLABS_DEFAULT_MODEL_ID=eleven_v3
ELEVENLABS_OUTPUT_FORMAT=mp3_44100_128
ELEVENLABS_TIMEOUT_SECONDS=30
VOICE_STT_PROVIDER=9router
```

Copie [config/voices.example.json](../../config/voices.example.json) e use `VOICE_PROFILES_PATH` ou `VOICE_PROFILES_JSON`. Speakers (`gm`, `villain`, …) mapeiam para `voice_id`. NPC desconhecido cai na voz do GM.

## Modelo

O modelo padrão é configurável: `eleven_v3`. Expressividade via **Audio Tags** no texto (ex. `[whispers]`), não via parâmetros inventados de emoção/ritmo. Tags só na família `eleven_v3*`.

## Teste manual

```bash
python scripts/gm_voice_test.py --text "A porta começa a se abrir lentamente..." --speaker gm
```

Precisa de `ELEVENLABS_API_KEY` e `ELEVENLABS_DEFAULT_VOICE_ID`. Não corre no CI.

Teste de integração: `ELEVENLABS_INTEGRATION_TEST=true pytest tests/test_voice_elevenlabs_integration.py`.

## Segurança

Nunca coloque `ELEVENLABS_API_KEY` no frontend Vue. A reprodução é só o evento `gm_audio`.

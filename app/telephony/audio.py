"""Conversioni audio tra Twilio e Gemini.

- Twilio: G.711 u-law (audio/x-mulaw) a 8 kHz, mono.
- Gemini Live: PCM16 mono a 16 kHz in ingresso, 24 kHz in uscita.

Il modulo `audioop` è fornito dal pacchetto `audioop-lts` (rimosso dalla stdlib
in Python 3.13). `ratecv` mantiene lo stato tra i chunk: va usato un Resampler
per ogni direzione e per ogni chiamata.
"""
from __future__ import annotations

import audioop  # fornito da audioop-lts su Python 3.13+

_WIDTH = 2       # PCM 16-bit
_CHANNELS = 1    # mono


def ulaw_to_pcm16(ulaw: bytes) -> bytes:
    """G.711 u-law (8-bit) -> PCM lineare 16-bit."""
    return audioop.ulaw2lin(ulaw, _WIDTH)


def pcm16_to_ulaw(pcm16: bytes) -> bytes:
    """PCM lineare 16-bit -> G.711 u-law (8-bit)."""
    return audioop.lin2ulaw(pcm16, _WIDTH)


class Resampler:
    """Ricampionatore PCM16 mono con stato continuo (per uno stream).

    Istanziane uno per direzione e per chiamata: lo stato interno di `ratecv`
    garantisce continuità tra un chunk e il successivo.
    """

    def __init__(self, in_rate: int, out_rate: int) -> None:
        self._in_rate = in_rate
        self._out_rate = out_rate
        self._state = None

    def process(self, pcm16: bytes) -> bytes:
        if self._in_rate == self._out_rate:
            return pcm16
        converted, self._state = audioop.ratecv(
            pcm16, _WIDTH, _CHANNELS, self._in_rate, self._out_rate, self._state
        )
        return converted

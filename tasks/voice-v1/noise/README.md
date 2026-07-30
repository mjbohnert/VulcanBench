# Ambient noise clips — provenance and licensing

Both clips were sourced from Wikimedia Commons, then trimmed to ~20 s and
converted to the suite master format (24 kHz mono PCM16 WAV) with
`harness/voice/audio.py` utilities. The noise condition mixes one of these
under each rendered question at **10 dB SNR** (RMS-based); the clip per item
is chosen deterministically by hashing the item id (`pick_noise_clip`).

## street.wav

- Source: [File:2023-Mai-20 14h34min Wien innerer Lerchenfelder Gürtel Thaliagasse Nachmittagsverkehr.wav](https://commons.wikimedia.org/wiki/File:2023-Mai-20_14h34min_Wien_innerer_Lerchenfelder_G%C3%BCrtel_Thaliagasse_Nachmittagsverkehr.wav)
- Author: DrTrumpet · License: **CC BY-SA 4.0**
- Content: afternoon street traffic, Vienna
- Modifications: trimmed (5 s–25 s), downmixed to mono, resampled to 24 kHz.
  This derivative remains under CC BY-SA 4.0.

## crowd.wav

- Source: [File:Geräuschkulisse in der Dreifachturnhalle (JCRG) 20240830 C1006.wav](https://commons.wikimedia.org/wiki/File:Ger%C3%A4uschkulisse_in_der_Dreifachturnhalle_(JCRG)_20240830_C1006.wav)
- Author: PantheraLeo1359531 · License: **CC BY 4.0**
- Content: indoor crowd soundscape (sports hall) — used as the babble/crowd
  condition
- Modifications: trimmed (5 s–23 s), downmixed to mono, resampled to 24 kHz.

These licenses apply to the audio clips only, independently of the
repository's code license.

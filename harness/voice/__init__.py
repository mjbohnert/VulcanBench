"""Voice Eval Suite: text-vs-audio delta ("voice tax") measurement.

The suite sends the same held-out question set to a model twice, once as
plain text, once rendered to speech, and reports the accuracy delta. See
``docs/VOICE_EVAL.md`` for the full methodology and ``tasks/voice-v1/`` for
the question set.
"""

from __future__ import annotations

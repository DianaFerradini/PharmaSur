"""Transcription des vocaux en wolof (D32), isolée du reste du bot.

Pour la démo : ElevenLabs Scribe. Pour passer à Google Cloud Speech-to-Text (wo-SN),
la cible de D32, il suffit d'écrire une autre classe avec la même méthode
`transcrire(audio) -> str`, et de la renvoyer dans `creer_transcripteur`.

Le vocal n'est jamais écrit sur disque : il est envoyé tel quel, puis oublié (même
esprit que D22 pour les photos).
"""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from .config import Config

log = logging.getLogger(__name__)

URL_ELEVENLABS = "https://api.elevenlabs.io/v1/speech-to-text"
MODELE_SCRIBE = "scribe_v2"
LANGUE_WOLOF = "wol"
DELAI = 60.0  # secondes : un vocal WhatsApp dure rarement plus d'une minute


class EchecTranscription(Exception):
    """La transcription a échoué : le bot répond le menu « non compris » (D8)."""


class Transcripteur(Protocol):
    def transcrire(self, audio: bytes) -> str:
        """Renvoie le texte du vocal (chaîne vide si rien n'a été compris)."""
        ...


class TranscripteurElevenLabs:
    def __init__(
        self,
        cle: str,
        client: httpx.Client | None = None,
        modele: str = MODELE_SCRIBE,
        langue: str = LANGUE_WOLOF,
    ) -> None:
        self.cle = cle
        self.client = client or httpx.Client(timeout=DELAI)
        self.modele = modele
        self.langue = langue

    def transcrire(self, audio: bytes) -> str:
        if not audio:
            raise EchecTranscription("vocal vide")
        try:
            reponse = self.client.post(
                URL_ELEVENLABS,
                headers={"xi-api-key": self.cle},
                data={"model_id": self.modele, "language_code": self.langue, "tag_audio_events": "false"},
                # Les vocaux WhatsApp sont en OGG/Opus (D37), un format qu'ElevenLabs accepte tel quel.
                files={"file": ("vocal.ogg", audio, "audio/ogg")},
            )
        except httpx.HTTPError as e:
            raise EchecTranscription("connexion à ElevenLabs impossible") from e
        if reponse.is_error:
            raise EchecTranscription(f"erreur d'ElevenLabs ({reponse.status_code})")
        try:
            texte = reponse.json()["text"]
        except (ValueError, KeyError, TypeError) as e:
            raise EchecTranscription("réponse d'ElevenLabs illisible") from e
        return (texte or "").strip()


def creer_transcripteur(config: Config) -> Transcripteur | None:
    """None sans clé ElevenLabs : un vocal reçoit alors la réponse provisoire."""
    if not config.elevenlabs_api_key:
        return None
    return TranscripteurElevenLabs(config.elevenlabs_api_key)

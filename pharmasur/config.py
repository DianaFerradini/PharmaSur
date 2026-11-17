"""Réglages du bot, lus dans les variables d'environnement (D38).

Sur le PC, les variables viennent du fichier `.env` (jamais commité).
Sur Railway, elles sont saisies dans l'onglet Variables du service.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Modèles Claude par défaut (D39) : Haiku pour le texte, Opus pour les photos.
MODELE_TEXTE = "claude-haiku-5-5"
MODELE_PHOTO = "claude-opus-5-5"


@dataclass(frozen=True)
class ModelesClaude:
    """Un modèle par tâche, réglable tâche par tâche (D39)."""

    tri: str = MODELE_TEXTE  # salutation, recherche, hors sujet, urgence
    extraction: str = MODELE_TEXTE  # médicaments dans un texte ou une transcription
    photo: str = MODELE_PHOTO  # lecture d'une photo d'ordonnance ou de boîte
    pharmacie: str = MODELE_TEXTE  # messages des pharmacies en texte libre


@dataclass(frozen=True)
class Config:
    whatsapp_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_verify_token: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_api_version: str = "v25.0"
    anthropic_api_key: str = ""
    elevenlabs_api_key: str = ""
    numero_pharmacie_baobab: str = ""
    db_path: str = "pharmasur.db"
    modeles: ModelesClaude = ModelesClaude()


def charger_config() -> Config:
    """Lit le fichier .env s'il existe, puis les variables d'environnement."""
    load_dotenv()
    env = os.environ.get
    return Config(
        whatsapp_token=env("WHATSAPP_TOKEN", ""),
        whatsapp_phone_number_id=env("WHATSAPP_PHONE_NUMBER_ID", ""),
        whatsapp_verify_token=env("WHATSAPP_VERIFY_TOKEN", ""),
        whatsapp_app_secret=env("WHATSAPP_APP_SECRET", ""),
        whatsapp_api_version=env("WHATSAPP_API_VERSION", "v25.0"),
        anthropic_api_key=env("ANTHROPIC_API_KEY", ""),
        elevenlabs_api_key=env("ELEVENLABS_API_KEY", ""),
        numero_pharmacie_baobab=env("NUMERO_PHARMACIE_BAOBAB", ""),
        db_path=env("DB_PATH", "pharmasur.db"),
        modeles=ModelesClaude(
            tri=env("CLAUDE_MODELE_TRI", MODELE_TEXTE),
            extraction=env("CLAUDE_MODELE_EXTRACTION", MODELE_TEXTE),
            photo=env("CLAUDE_MODELE_PHOTO", MODELE_PHOTO),
            pharmacie=env("CLAUDE_MODELE_PHARMACIE", MODELE_TEXTE),
        ),
    )

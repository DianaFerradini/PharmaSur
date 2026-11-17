"""Réglages du bot, lus dans les variables d'environnement (D38).

Sur le PC, les variables viennent du fichier `.env` (jamais commité).
Sur Railway, elles sont saisies dans l'onglet Variables du service.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# Modèle Claude par défaut, en attendant la réponse à Q32 (voir DECISIONS.md).
MODELE_PAR_DEFAUT = "claude-opus-5-5"


@dataclass(frozen=True)
class ModelesClaude:
    """Un modèle par tâche, pour pouvoir changer de modèle tâche par tâche (Q32)."""

    tri: str = MODELE_PAR_DEFAUT  # salutation, recherche, hors sujet, urgence
    extraction: str = MODELE_PAR_DEFAUT  # médicaments dans un texte ou une transcription
    photo: str = MODELE_PAR_DEFAUT  # lecture d'une photo d'ordonnance ou de boîte
    pharmacie: str = MODELE_PAR_DEFAUT  # messages des pharmacies en texte libre


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
            tri=env("CLAUDE_MODELE_TRI", MODELE_PAR_DEFAUT),
            extraction=env("CLAUDE_MODELE_EXTRACTION", MODELE_PAR_DEFAUT),
            photo=env("CLAUDE_MODELE_PHOTO", MODELE_PAR_DEFAUT),
            pharmacie=env("CLAUDE_MODELE_PHARMACIE", MODELE_PAR_DEFAUT),
        ),
    )

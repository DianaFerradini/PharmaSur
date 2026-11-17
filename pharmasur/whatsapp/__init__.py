"""Accès à WhatsApp, isolé du reste du bot (D29).

Tout ce qui dépend du fournisseur (Meta aujourd'hui, Twilio peut-être demain) vit
dans ce paquet. Le reste du bot ne connaît que :

- `MessageRecu` : un message entrant, déjà normalisé ;
- `Option` : un choix neutre (« Oui », « Non »…), affiché en bouton chez Meta,
  et qui serait affiché en réponse numérotée chez Twilio ;
- `Fournisseur` : les opérations disponibles (lire les messages reçus, envoyer
  du texte, un choix, une image, un vocal, télécharger un média).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class TypeMessage(str, Enum):
    TEXTE = "texte"
    IMAGE = "image"
    AUDIO = "audio"
    CHOIX = "choix"  # la personne a touché une des options proposées
    AUTRE = "autre"  # autocollant, position, document… : non géré


@dataclass(frozen=True)
class MessageRecu:
    expediteur: str  # numéro au format international, chiffres seulement (ex. 221771234567)
    type: TypeMessage
    texte: str | None = None  # corps d'un texte, légende d'une image, ou libellé du choix touché
    media_id: str | None = None  # image ou audio : à passer à `telecharger_media`
    choix_id: str | None = None  # identifiant de l'`Option` touchée
    id_message: str | None = None


@dataclass(frozen=True)
class Option:
    id: str  # identifiant neutre, renvoyé dans `MessageRecu.choix_id`
    libelle: str  # texte affiché (20 caractères au plus chez Meta)


class Fournisseur(ABC):
    """Ce que le bot attend d'un fournisseur WhatsApp."""

    # --- Réception ---

    @abstractmethod
    def verifier_abonnement(self, parametres: Mapping[str, str]) -> str | None:
        """Vérification du webhook à son enregistrement.

        Renvoie le texte à répondre si la demande est valide, sinon None.
        """

    @abstractmethod
    def verifier_requete(self, corps: bytes, entetes: Mapping[str, str]) -> bool:
        """Vérifie que la requête reçue vient bien du fournisseur (signature)."""

    @abstractmethod
    def lire_messages(self, corps: bytes, entetes: Mapping[str, str]) -> list[MessageRecu]:
        """Extrait les messages d'une requête reçue. Ignore les accusés de lecture."""

    # --- Envoi ---

    @abstractmethod
    def envoyer_texte(self, destinataire: str, texte: str) -> None: ...

    @abstractmethod
    def envoyer_choix(self, destinataire: str, texte: str, options: list[Option]) -> None:
        """Envoie un texte suivi de 2 ou 3 options neutres."""

    @abstractmethod
    def envoyer_image(self, destinataire: str, url: str, legende: str | None = None) -> None: ...

    @abstractmethod
    def envoyer_audio(self, destinataire: str, chemin_fichier: str) -> None:
        """Envoie un vocal préenregistré (fichier OGG/Opus, D37)."""

    @abstractmethod
    def telecharger_media(self, media_id: str) -> bytes:
        """Renvoie le contenu d'une image ou d'un audio reçu."""


__all__ = ["Fournisseur", "MessageRecu", "Option", "TypeMessage"]

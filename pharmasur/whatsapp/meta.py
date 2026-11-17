"""Implémentation du fournisseur WhatsApp avec l'API officielle de Meta (D29).

Documentation : https://developers.facebook.com/docs/whatsapp/cloud-api
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import mimetypes
from pathlib import Path
from typing import Any, Mapping

import httpx

from . import Fournisseur, MessageRecu, Option, TypeMessage

log = logging.getLogger(__name__)

URL_GRAPH = "https://graph.facebook.com"
TITRE_BOUTON_MAX = 20  # limite de Meta pour le libellé d'un bouton
NOMBRE_BOUTONS_MAX = 3  # limite de Meta pour un message à boutons


def signature_attendue(secret: str, corps: bytes) -> str:
    """Valeur attendue de l'en-tête X-Hub-Signature-256."""
    return "sha256=" + hmac.new(secret.encode(), corps, hashlib.sha256).hexdigest()


def _entete(entetes: Mapping[str, str], nom: str) -> str | None:
    nom = nom.lower()
    for cle, valeur in entetes.items():
        if cle.lower() == nom:
            return valeur
    return None


def analyser_message(message: dict[str, Any]) -> MessageRecu:
    """Convertit un message du webhook Meta en `MessageRecu`."""
    expediteur = str(message.get("from", ""))
    id_message = message.get("id")
    type_meta = message.get("type")

    if type_meta == "text":
        return MessageRecu(expediteur, TypeMessage.TEXTE, texte=message["text"]["body"], id_message=id_message)
    if type_meta == "image":
        image = message["image"]
        return MessageRecu(
            expediteur, TypeMessage.IMAGE, texte=image.get("caption"), media_id=image["id"], id_message=id_message
        )
    if type_meta == "audio":
        return MessageRecu(expediteur, TypeMessage.AUDIO, media_id=message["audio"]["id"], id_message=id_message)
    if type_meta == "interactive":
        interactif = message["interactive"]
        reponse = interactif.get("button_reply") or interactif.get("list_reply") or {}
        return MessageRecu(
            expediteur,
            TypeMessage.CHOIX,
            texte=reponse.get("title"),
            choix_id=reponse.get("id"),
            id_message=id_message,
        )
    if type_meta == "button":  # bouton d'un modèle de message validé par Meta
        bouton = message["button"]
        return MessageRecu(
            expediteur,
            TypeMessage.CHOIX,
            texte=bouton.get("text"),
            choix_id=bouton.get("payload"),
            id_message=id_message,
        )
    return MessageRecu(expediteur, TypeMessage.AUTRE, id_message=id_message)


class FournisseurMeta(Fournisseur):
    def __init__(
        self,
        token: str,
        phone_number_id: str,
        verify_token: str,
        app_secret: str,
        api_version: str = "v25.0",
        client: httpx.Client | None = None,
    ) -> None:
        self.token = token
        self.phone_number_id = phone_number_id
        self.verify_token = verify_token
        self.app_secret = app_secret
        self.api_version = api_version
        self.client = client or httpx.Client(timeout=30)

    # --- Réception ---

    def verifier_abonnement(self, parametres: Mapping[str, str]) -> str | None:
        if (
            self.verify_token
            and parametres.get("hub.mode") == "subscribe"
            and hmac.compare_digest(parametres.get("hub.verify_token", ""), self.verify_token)
        ):
            return parametres.get("hub.challenge", "")
        return None

    def verifier_requete(self, corps: bytes, entetes: Mapping[str, str]) -> bool:
        recue = _entete(entetes, "X-Hub-Signature-256")
        if not self.app_secret or not recue:
            return False
        return hmac.compare_digest(recue, signature_attendue(self.app_secret, corps))

    def lire_messages(self, corps: bytes, entetes: Mapping[str, str]) -> list[MessageRecu]:
        try:
            donnees = json.loads(corps)
        except ValueError:
            log.warning("Corps de webhook illisible")
            return []
        messages: list[MessageRecu] = []
        for entree in donnees.get("entry", []):
            for changement in entree.get("changes", []):
                valeur = changement.get("value", {})
                # Les « statuses » (envoyé, lu…) n'ont pas de clé « messages » : ignorés.
                for message in valeur.get("messages", []):
                    messages.append(analyser_message(message))
        return messages

    # --- Envoi ---

    def _url(self, chemin: str) -> str:
        return f"{URL_GRAPH}/{self.api_version}/{chemin}"

    def _entetes(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}

    def _envoyer(self, destinataire: str, contenu: dict[str, Any]) -> None:
        corps = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": destinataire, **contenu}
        reponse = self.client.post(self._url(f"{self.phone_number_id}/messages"), headers=self._entetes(), json=corps)
        if reponse.is_error:
            log.error("Envoi WhatsApp refusé (%s) : %s", reponse.status_code, reponse.text)
        reponse.raise_for_status()

    def envoyer_texte(self, destinataire: str, texte: str) -> None:
        self._envoyer(destinataire, {"type": "text", "text": {"body": texte, "preview_url": False}})

    def envoyer_choix(self, destinataire: str, texte: str, options: list[Option]) -> None:
        if not 1 <= len(options) <= NOMBRE_BOUTONS_MAX:
            raise ValueError(f"Meta accepte 1 à {NOMBRE_BOUTONS_MAX} boutons, reçu {len(options)}")
        boutons = [
            {"type": "reply", "reply": {"id": option.id, "title": option.libelle[:TITRE_BOUTON_MAX]}}
            for option in options
        ]
        self._envoyer(
            destinataire,
            {
                "type": "interactive",
                "interactive": {"type": "button", "body": {"text": texte}, "action": {"buttons": boutons}},
            },
        )

    def envoyer_image(self, destinataire: str, url: str, legende: str | None = None) -> None:
        image: dict[str, str] = {"link": url}
        if legende:
            image["caption"] = legende
        self._envoyer(destinataire, {"type": "image", "image": image})

    def envoyer_audio(self, destinataire: str, chemin_fichier: str) -> None:
        media_id = self._televerser(Path(chemin_fichier))
        self._envoyer(destinataire, {"type": "audio", "audio": {"id": media_id}})

    def _televerser(self, chemin: Path) -> str:
        type_mime = mimetypes.guess_type(chemin.name)[0] or "audio/ogg"
        with chemin.open("rb") as fichier:
            reponse = self.client.post(
                self._url(f"{self.phone_number_id}/media"),
                headers=self._entetes(),
                data={"messaging_product": "whatsapp", "type": type_mime},
                files={"file": (chemin.name, fichier, type_mime)},
            )
        reponse.raise_for_status()
        return reponse.json()["id"]

    def telecharger_media(self, media_id: str) -> bytes:
        # 1. Meta donne une adresse temporaire, 2. on télécharge le fichier avec le même jeton.
        infos = self.client.get(self._url(media_id), headers=self._entetes())
        infos.raise_for_status()
        fichier = self.client.get(infos.json()["url"], headers=self._entetes())
        fichier.raise_for_status()
        return fichier.content

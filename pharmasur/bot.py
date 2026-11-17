"""Traitement d'un message reçu : routage (D4) puis parcours.

Un seul numéro WhatsApp pour tout le monde (D4) : un numéro inscrit comme pharmacie
partenaire est traité comme une pharmacie, tout autre numéro comme une personne qui
cherche.
"""

from __future__ import annotations

import logging
import sqlite3

from . import db, textes
from .recherche import decouper_texte, formater_fiche, rechercher
from .whatsapp import Fournisseur, MessageRecu, TypeMessage

log = logging.getLogger(__name__)


def traiter_message(message: MessageRecu, fournisseur: Fournisseur, chemin_db: str) -> None:
    connexion = db.connecter(chemin_db)
    try:
        pharmacie = db.pharmacie_par_numero(connexion, message.expediteur)
        if pharmacie is not None:
            traiter_message_pharmacie(message, pharmacie, fournisseur, connexion)
        else:
            traiter_message_personne(message, fournisseur, connexion)
    except Exception:
        log.exception("Échec du traitement du message %s", message.id_message)
    finally:
        connexion.close()


def traiter_message_personne(message: MessageRecu, fournisseur: Fournisseur, connexion: sqlite3.Connection) -> None:
    """Personne qui cherche. Version provisoire du parcours 1, sans IA :
    le texte est découpé aux virgules et aux « et », en attendant l'extraction par Claude."""
    numero = message.expediteur
    if message.type is TypeMessage.IMAGE:
        fournisseur.envoyer_texte(numero, textes.PROVISOIRE_PHOTO)
        return
    if message.type is TypeMessage.AUDIO:
        fournisseur.envoyer_texte(numero, textes.PROVISOIRE_VOCAL)
        return
    if message.type is not TypeMessage.TEXTE or not message.texte:
        fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
        return

    premier_contact = db.enregistrer_premier_contact(connexion, numero)
    demandes = decouper_texte(message.texte)
    if not demandes:
        fournisseur.envoyer_texte(numero, textes.ACCUEIL_COMPLET if premier_contact else textes.NON_COMPRIS)
        return
    if premier_contact:
        fournisseur.envoyer_texte(numero, textes.ACCUEIL_COURT)

    resultat = rechercher(demandes, db.charger_pharmacies(connexion))
    db.enregistrer_recherche(connexion, resultat)
    fiche = formater_fiche(resultat)
    if fiche:
        fournisseur.envoyer_texte(numero, fiche)
    for introuvable in resultat.introuvables:
        # Provisoire : la proposition de demande d'équivalent arrive avec le parcours 2.
        fournisseur.envoyer_texte(numero, textes.INTROUVABLE.format(medicament=introuvable.libelle))


def traiter_message_pharmacie(
    message: MessageRecu, pharmacie: sqlite3.Row, fournisseur: Fournisseur, connexion: sqlite3.Connection
) -> None:
    """Pharmacie partenaire. Emplacement : rupture, retour en stock et résumé (parcours 3)
    et réponses aux demandes d'équivalent (parcours 2) arrivent ensuite."""
    fournisseur.envoyer_texte(message.expediteur, textes.PROVISOIRE_PHARMACIE.format(pharmacie=pharmacie["nom"]))

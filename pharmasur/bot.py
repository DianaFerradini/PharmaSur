"""Traitement d'un message reçu : routage (D4) puis parcours.

Un seul numéro WhatsApp pour tout le monde (D4) : un numéro inscrit comme pharmacie
partenaire est traité comme une pharmacie, tout autre numéro comme une personne qui
cherche.
"""

from __future__ import annotations

import logging
import sqlite3
from difflib import SequenceMatcher

from . import db, textes
from .ia import AnalyseurClaude, Categorie, EchecAnalyse, LecteurPhoto, Lisibilite
from .recherche import Medicament, analyser_medicament, decouper_texte, formater_fiche, normaliser, rechercher
from .whatsapp import Fournisseur, MessageRecu, Option, TypeMessage

log = logging.getLogger(__name__)

# Identifiants neutres des choix de la confirmation de lecture (D13).
CHOIX_LECTURE_OUI = "lecture_oui"
CHOIX_LECTURE_CORRIGER = "lecture_corriger"

# En dessous de cette ressemblance, un nom donné après une lecture partielle est
# compté comme le médicament qui n'a pas pu être lu, pas comme une correction.
SEUIL_RESSEMBLANCE = 0.6


def traiter_message(
    message: MessageRecu,
    fournisseur: Fournisseur,
    chemin_db: str,
    analyseur: AnalyseurClaude | None = None,
    lecteur: LecteurPhoto | None = None,
) -> None:
    connexion = db.connecter(chemin_db)
    try:
        pharmacie = db.pharmacie_par_numero(connexion, message.expediteur)
        if pharmacie is not None:
            traiter_message_pharmacie(message, pharmacie, fournisseur, connexion)
        elif analyseur is not None:
            traiter_message_personne_ia(message, fournisseur, connexion, analyseur, lecteur)
        else:
            traiter_message_personne(message, fournisseur, connexion)
    except Exception:
        log.exception("Échec du traitement du message %s", message.id_message)
    finally:
        connexion.close()


def traiter_message_personne_ia(
    message: MessageRecu,
    fournisseur: Fournisseur,
    connexion: sqlite3.Connection,
    analyseur: AnalyseurClaude,
    lecteur: LecteurPhoto | None = None,
) -> None:
    """Personne qui cherche, parcours 1 et 6 avec Claude (D8, D9, D12, D13, D21)."""
    numero = message.expediteur
    if message.type is TypeMessage.IMAGE:
        if lecteur is None or not message.media_id:
            fournisseur.envoyer_texte(numero, textes.PROVISOIRE_PHOTO)
        else:
            traiter_photo(message, fournisseur, connexion, lecteur)
        return
    if message.type is TypeMessage.CHOIX:
        traiter_choix(message, fournisseur, connexion)
        return
    if message.type is TypeMessage.AUDIO:
        fournisseur.envoyer_texte(numero, textes.PROVISOIRE_VOCAL)
        return
    if message.type is not TypeMessage.TEXTE or not message.texte or not message.texte.strip():
        fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
        return

    premier_contact = db.enregistrer_premier_contact(connexion, numero)

    # Une lecture de photo attend une correction (✏️) ou le nom d'un médicament non lu (D21).
    lecture = db.lire_lecture(connexion, numero)
    if lecture is not None:
        if lecture["attend_correction"] or lecture["non_lus"]:
            corriger_lecture(numero, message.texte, lecture, fournisseur, connexion, analyseur)
            return
        # Tout autre message abandonne la photo en attente et se traite normalement.
        db.supprimer_lecture(connexion, numero)

    # Réponses au menu « non compris » (D8).
    choix = message.texte.strip().rstrip(".")
    if choix == "1":
        fournisseur.envoyer_texte(numero, textes.INVITATION)
        return
    if choix == "2":
        fournisseur.envoyer_texte(numero, textes.ACCUEIL_COMPLET)
        return

    try:
        analyse = analyseur.analyser(message.texte)
    except EchecAnalyse as e:
        log.warning("Analyse impossible (%s) : menu « non compris »", e)
        fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
        return

    if analyse.categorie is Categorie.URGENCE:
        fournisseur.envoyer_texte(numero, textes.URGENCE)
        return

    demandes = [m for m in (analyser_medicament(t) for t in analyse.medicaments) if m is not None]
    if analyse.categorie is Categorie.RECHERCHE and demandes:
        if premier_contact:
            fournisseur.envoyer_texte(numero, textes.ACCUEIL_COURT)
        elif analyse.salue:
            fournisseur.envoyer_texte(numero, textes.SALUTATION)
        envoyer_resultats(numero, demandes, fournisseur, connexion)
        return

    if analyse.categorie is Categorie.HORS_SUJET:
        if premier_contact:
            fournisseur.envoyer_texte(numero, textes.ACCUEIL_COMPLET)
        fournisseur.envoyer_texte(numero, textes.HORS_SUJET)
        return

    if analyse.categorie is Categorie.SALUTATION:
        fournisseur.envoyer_texte(numero, textes.ACCUEIL_COMPLET if premier_contact else textes.SALUTATION_RETOUR)
        return

    # « autre », ou une recherche sans aucun nom exploitable.
    fournisseur.envoyer_texte(numero, textes.ACCUEIL_COMPLET if premier_contact else textes.NON_COMPRIS)


def traiter_photo(
    message: MessageRecu, fournisseur: Fournisseur, connexion: sqlite3.Connection, lecteur: LecteurPhoto
) -> None:
    """Parcours 6 : lecture de la photo, puis confirmation de lecture (D12, D13, D21)."""
    numero = message.expediteur
    premier_contact = db.enregistrer_premier_contact(connexion, numero)
    ancienne = db.lire_lecture(connexion, numero)
    if ancienne is not None:
        premier_contact = premier_contact or ancienne["premier_contact"]

    try:
        image = fournisseur.telecharger_media(message.media_id)
    except Exception:
        log.warning("Téléchargement de la photo impossible : menu « non compris »")
        fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
        return
    try:
        lecture = lecteur.lire(image, message.texte)
    except EchecAnalyse as e:
        log.warning("Lecture de la photo impossible (%s) : menu « non compris »", e)
        fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
        return
    finally:
        del image  # D22 : l'image n'est ni écrite sur disque ni gardée après la lecture.

    if lecture.lisibilite is Lisibilite.ILLISIBLE:
        db.supprimer_lecture(connexion, numero)
        fournisseur.envoyer_texte(numero, textes.PHOTO_ILLISIBLE)
        return

    medicaments = list(lecture.medicaments)
    db.enregistrer_lecture(connexion, numero, medicaments, lecture.non_lus, premier_contact)
    envoyer_confirmation(numero, medicaments, lecture.non_lus, fournisseur, textes.LECTURE_INTRO)


def envoyer_confirmation(
    numero: str, medicaments: list[str], non_lus: int, fournisseur: Fournisseur, intro: str
) -> None:
    """Confirmation de lecture (D13), avec l'avertissement de lecture partielle (D21)."""
    lignes = [intro] + [f"{rang}. {nom}" for rang, nom in enumerate(medicaments, start=1)]
    if non_lus == 1:
        lignes.append(textes.LECTURE_PARTIELLE_UN)
    elif non_lus > 1:
        lignes.append(textes.LECTURE_PARTIELLE_PLUSIEURS.format(nombre=non_lus))
    lignes.append(textes.LECTURE_QUESTION)
    fournisseur.envoyer_choix(
        numero,
        "\n".join(lignes),
        [
            Option(CHOIX_LECTURE_OUI, textes.BOUTON_LECTURE_OUI),
            Option(CHOIX_LECTURE_CORRIGER, textes.BOUTON_LECTURE_CORRIGER),
        ],
    )


def traiter_choix(message: MessageRecu, fournisseur: Fournisseur, connexion: sqlite3.Connection) -> None:
    """La personne a touché un bouton. Pour l'instant : la confirmation de lecture (D13)."""
    numero = message.expediteur
    lecture = db.lire_lecture(connexion, numero)
    if lecture is None:
        # Bouton d'une lecture déjà confirmée ou expirée.
        fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
        return

    if message.choix_id == CHOIX_LECTURE_OUI:
        # D22 : le lien entre le numéro et les noms lus est effacé dès la confirmation.
        db.supprimer_lecture(connexion, numero)
        demandes = [m for m in (analyser_medicament(nom) for nom in lecture["medicaments"]) if m is not None]
        if not demandes:
            fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
            return
        if lecture["premier_contact"]:
            fournisseur.envoyer_texte(numero, textes.ACCUEIL_COURT)
        envoyer_resultats(numero, demandes, fournisseur, connexion)
        return

    if message.choix_id == CHOIX_LECTURE_CORRIGER:
        db.mettre_a_jour_lecture(connexion, numero, attend_correction=True)
        fournisseur.envoyer_texte(numero, textes.DEMANDE_CORRECTION)
        return

    fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)


def _cle_ressemblance(nom: str) -> str:
    medicament = analyser_medicament(nom)
    return " ".join(medicament.nom) if medicament else normaliser(nom)


def corriger_lecture(
    numero: str,
    texte: str,
    lecture: dict,
    fournisseur: Fournisseur,
    connexion: sqlite3.Connection,
    analyseur: AnalyseurClaude,
) -> None:
    """Applique la réponse de la personne à la liste lue, puis redemande confirmation (D13).

    Chaque nom donné remplace le nom lu qui lui ressemble le plus ; seul le couple
    « lu → corrigé » est gardé, sans image ni numéro (D22). Après une lecture partielle,
    un nom qui ne ressemble à aucun nom lu est ajouté : c'est le médicament non lu (D21).
    """
    try:
        analyse = analyseur.analyser(texte)
    except EchecAnalyse as e:
        log.warning("Analyse de la correction impossible (%s) : menu « non compris »", e)
        fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
        return
    if analyse.categorie is Categorie.URGENCE:
        fournisseur.envoyer_texte(numero, textes.URGENCE)
        return
    if not analyse.medicaments:
        fournisseur.envoyer_texte(numero, textes.DEMANDE_CORRECTION)
        return

    medicaments = list(lecture["medicaments"])
    non_lus = lecture["non_lus"]
    deja_corriges: set[int] = set()
    for nom in analyse.medicaments:
        candidats = [i for i in range(len(medicaments)) if i not in deja_corriges]
        meilleur, score = None, 0.0
        for i in candidats:
            ressemblance = SequenceMatcher(None, _cle_ressemblance(nom), _cle_ressemblance(medicaments[i])).ratio()
            if ressemblance > score:
                meilleur, score = i, ressemblance
        # Sans médicament non lu, toute correction remplace forcément un nom lu.
        remplace = meilleur is not None and (score >= SEUIL_RESSEMBLANCE or not non_lus)
        if remplace:
            lu = medicaments[meilleur]
            if lu != nom:
                db.enregistrer_correction(connexion, lu, nom)
                medicaments[meilleur] = nom
            deja_corriges.add(meilleur)
        else:
            medicaments.append(nom)
            deja_corriges.add(len(medicaments) - 1)
            non_lus = max(0, non_lus - 1)

    db.mettre_a_jour_lecture(connexion, numero, medicaments=medicaments, non_lus=non_lus, attend_correction=False)
    envoyer_confirmation(numero, medicaments, non_lus, fournisseur, textes.LECTURE_INTRO_CORRIGEE)


def envoyer_resultats(
    numero: str, demandes: list[Medicament], fournisseur: Fournisseur, connexion: sqlite3.Connection
) -> None:
    """Fiche résultat (D7) puis les introuvables (D5)."""
    resultat = rechercher(demandes, db.charger_pharmacies(connexion))
    db.enregistrer_recherche(connexion, resultat)
    fiche = formater_fiche(resultat)
    if fiche:
        fournisseur.envoyer_texte(numero, fiche)
    for introuvable in resultat.introuvables:
        # Provisoire : la proposition de demande d'équivalent arrive avec le parcours 2.
        fournisseur.envoyer_texte(numero, textes.INTROUVABLE.format(medicament=introuvable.libelle))


def traiter_message_personne(message: MessageRecu, fournisseur: Fournisseur, connexion: sqlite3.Connection) -> None:
    """Personne qui cherche, sans clé Anthropic : repli sur le découpage provisoire
    du texte aux virgules et aux « et »."""
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
    envoyer_resultats(numero, demandes, fournisseur, connexion)


def traiter_message_pharmacie(
    message: MessageRecu, pharmacie: sqlite3.Row, fournisseur: Fournisseur, connexion: sqlite3.Connection
) -> None:
    """Pharmacie partenaire. Emplacement : rupture, retour en stock et résumé (parcours 3)
    et réponses aux demandes d'équivalent (parcours 2) arrivent ensuite."""
    fournisseur.envoyer_texte(message.expediteur, textes.PROVISOIRE_PHARMACIE.format(pharmacie=pharmacie["nom"]))

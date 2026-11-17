"""Réponses en vocal pour les personnes qui parlent au bot (D23, D24, D37).

Le bot ne sait pas parler wolof : il envoie l'un des 12 vocaux préenregistrés de
VOCAUX.md, choisi selon la situation, puis le message écrit habituel, qui garde les
noms, adresses et numéros (D23). Les vocaux ne disent aucun nom.

Le reste du bot n'a pas à y penser : `AvecVocaux` enveloppe le fournisseur WhatsApp.
Quand le dernier message de la personne était un vocal, chaque texte connu qu'on lui
envoie est précédé du vocal qui lui correspond. Tant qu'un fichier manque (les
enregistrements ne sont pas encore faits), seul le texte part, et le journal le signale.
"""

from __future__ import annotations

import logging
from enum import IntEnum
from pathlib import Path
from typing import Callable, Mapping

from . import textes
from .whatsapp import Fournisseur, MessageRecu, Option

log = logging.getLogger(__name__)

DOSSIER_VOCAUX = Path(__file__).parent / "vocaux"


class Vocal(IntEnum):
    """Les 12 vocaux de VOCAUX.md (D24)."""

    ACCUEIL_COMPLET = 1
    ACCUEIL_COURT = 2
    CONFIRMATION_LECTURE = 3
    PHOTO_ILLISIBLE = 4
    RESULTATS = 5
    INTROUVABLE = 6
    DEMANDE_ENVOYEE = 7
    SOLUTION_TROUVEE = 8
    AUCUNE_SOLUTION = 9
    HORS_SUJET = 10
    URGENCE = 11
    NON_COMPRIS = 12


# Noms des fichiers, tels que VOCAUX.md demande de les ranger.
FICHIERS = {
    Vocal.ACCUEIL_COMPLET: "01-accueil-complet.ogg",
    Vocal.ACCUEIL_COURT: "02-accueil-court.ogg",
    Vocal.CONFIRMATION_LECTURE: "03-confirmation-lecture.ogg",
    Vocal.PHOTO_ILLISIBLE: "04-photo-illisible.ogg",
    Vocal.RESULTATS: "05-resultats.ogg",
    Vocal.INTROUVABLE: "06-introuvable.ogg",
    Vocal.DEMANDE_ENVOYEE: "07-demande-envoyee.ogg",
    Vocal.SOLUTION_TROUVEE: "08-solution-trouvee.ogg",
    Vocal.AUCUNE_SOLUTION: "09-aucune-solution.ogg",
    Vocal.HORS_SUJET: "10-hors-sujet.ogg",
    Vocal.URGENCE: "11-urgence.ogg",
    Vocal.NON_COMPRIS: "12-non-compris.ogg",
}


def _debut(modele: str) -> str:
    """Partie fixe d'un texte à trous : « 💡 La {pharmacie} a… » → « 💡 La »."""
    return modele.split("{", 1)[0]


# Situation → vocal, d'après le début (ou le contenu) du texte envoyé. L'ordre compte :
# le premier qui correspond l'emporte. Les textes viennent tous de textes.py.
_COMMENCE_PAR: list[tuple[str, Vocal]] = [
    (textes.ACCUEIL_COMPLET, Vocal.ACCUEIL_COMPLET),
    (textes.SALUTATION_RETOUR, Vocal.ACCUEIL_COMPLET),  # « comment faire », pour qui ne lit pas
    (textes.INVITATION, Vocal.ACCUEIL_COMPLET),
    (textes.ACCUEIL_COURT, Vocal.ACCUEIL_COURT),
    (textes.LECTURE_INTRO, Vocal.CONFIRMATION_LECTURE),
    (textes.LECTURE_INTRO_VOCAL, Vocal.CONFIRMATION_LECTURE),
    (textes.LECTURE_INTRO_CORRIGEE, Vocal.CONFIRMATION_LECTURE),
    (textes.PHOTO_ILLISIBLE, Vocal.PHOTO_ILLISIBLE),
    (textes.EQUIVALENT_ENVOYE, Vocal.DEMANDE_ENVOYEE),
    (_debut(textes.SOLUTION_TROUVEE), Vocal.SOLUTION_TROUVEE),
    (_debut(textes.AUCUNE_SOLUTION), Vocal.AUCUNE_SOLUTION),
    (textes.HORS_SUJET, Vocal.HORS_SUJET),
    (textes.URGENCE, Vocal.URGENCE),
    (textes.NON_COMPRIS, Vocal.NON_COMPRIS),
]
_CONTIENT: list[tuple[str, Vocal]] = [
    (textes.RAPPEL_SECURITE, Vocal.RESULTATS),  # la fiche résultat (D7, D8)
    (textes.PROPOSITION_EQUIVALENT, Vocal.INTROUVABLE),  # lignes 🚫 + ✅ / ❌ (D10)
]


def vocal_pour(texte: str) -> Vocal | None:
    """Le vocal qui accompagne ce texte, ou None (ex. « Bonjour 👋 » seul, « Écrivez ou dites le bon nom »)."""
    for debut, vocal in _COMMENCE_PAR:
        if texte.startswith(debut):
            return vocal
    for morceau, vocal in _CONTIENT:
        if morceau in texte:
            return vocal
    return None


class BanqueVocaux:
    """Les fichiers des 12 vocaux, rangés dans `pharmasur/vocaux/` (VOCAUX.md)."""

    def __init__(self, dossier: str | Path = DOSSIER_VOCAUX) -> None:
        self.dossier = Path(dossier)
        self._deja_signales: set[Vocal] = set()

    def chemin(self, vocal: Vocal) -> Path | None:
        """Le fichier du vocal, ou None s'il n'est pas encore enregistré.

        Le disque est relu à chaque fois : un vocal ajouté pendant que le serveur
        tourne est utilisé tout de suite.
        """
        attendu = self.dossier / FICHIERS[vocal]
        if attendu.is_file():
            return attendu
        # Même nom, autre extension (.opus, .mp3, .m4a…) : utilisé, mais signalé (D37).
        autres = sorted(p for p in self.dossier.glob(attendu.stem + ".*") if p.is_file())
        if autres:
            log.warning(
                "Vocal %s en %s et non en .ogg : WhatsApp ne l'affichera peut-être pas comme message vocal (D37)",
                int(vocal),
                autres[0].suffix,
            )
            return autres[0]
        if vocal not in self._deja_signales:
            self._deja_signales.add(vocal)
            log.warning("Vocal %s absent (%s) : le texte part seul", int(vocal), attendu)
        return None

    def envoyer(self, fournisseur: Fournisseur, destinataire: str, vocal: Vocal) -> bool:
        """Envoie le vocal s'il existe. Un échec n'empêche jamais le texte de partir."""
        chemin = self.chemin(vocal)
        if chemin is None:
            return False
        try:
            fournisseur.envoyer_audio(destinataire, str(chemin))
        except Exception:
            log.exception("Envoi du vocal %s impossible : le texte part seul", int(vocal))
            return False
        return True


class AvecVocaux(Fournisseur):
    """Enveloppe un fournisseur : pour une personne qui parle en vocal, chaque texte
    connu est précédé de son vocal (D23, D24). Tout le reste passe tel quel."""

    def __init__(self, interne: Fournisseur, banque: BanqueVocaux, est_vocal: Callable[[str], bool]) -> None:
        self.interne = interne
        self.banque = banque
        self.est_vocal = est_vocal

    def _annoncer(self, destinataire: str, texte: str) -> None:
        vocal = vocal_pour(texte)
        if vocal is None:
            return
        try:
            vocal_demande = self.est_vocal(destinataire)
        except Exception:
            log.exception("Forme de la conversation illisible : texte seul")
            return
        if vocal_demande:
            self.banque.envoyer(self.interne, destinataire, vocal)

    # --- Envoi ---

    def envoyer_texte(self, destinataire: str, texte: str) -> None:
        self._annoncer(destinataire, texte)
        self.interne.envoyer_texte(destinataire, texte)

    def envoyer_choix(self, destinataire: str, texte: str, options: list[Option]) -> None:
        self._annoncer(destinataire, texte)
        self.interne.envoyer_choix(destinataire, texte, options)

    def envoyer_image(self, destinataire: str, url: str, legende: str | None = None) -> None:
        self.interne.envoyer_image(destinataire, url, legende)

    def envoyer_audio(self, destinataire: str, chemin_fichier: str) -> None:
        self.interne.envoyer_audio(destinataire, chemin_fichier)

    def telecharger_media(self, media_id: str) -> bytes:
        return self.interne.telecharger_media(media_id)

    # --- Réception ---

    def verifier_abonnement(self, parametres: Mapping[str, str]) -> str | None:
        return self.interne.verifier_abonnement(parametres)

    def verifier_requete(self, corps: bytes, entetes: Mapping[str, str]) -> bool:
        return self.interne.verifier_requete(corps, entetes)

    def lire_messages(self, corps: bytes, entetes: Mapping[str, str]) -> list[MessageRecu]:
        return self.interne.lire_messages(corps, entetes)

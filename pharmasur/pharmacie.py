"""Parcours 3 : côté pharmacie (D2, D14, D18, D19, D20).

La pharmacie écrit comme elle parle (D18) : « plus de doliprane 1000 », « le Mag 2 est
revenu », « résumé ». Haiku (D39) comprend l'intention et rapproche chaque nom cité d'un
produit du catalogue de cette pharmacie, sans jamais en choisir un autre.

- Sûr d'avoir compris : le changement est appliqué et le bot accuse réception (D19).
- Un doute (nom approximatif, plusieurs produits possibles, message ambigu) :
  confirmation avec les boutons Oui / Non (D19).
- Un médicament hors catalogue : toujours une confirmation, puis il entre dans le
  catalogue, disponible ou en rupture (D20).
- « résumé » : les deux chiffres de la semaine (D14), seulement sur demande.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from enum import StrEnum

import anthropic

from . import db, equivalent, textes
from .config import Config
from .ia import EchecAnalyse, appeler_claude, creer_client
from .recherche import analyser_medicament, correspond
from .whatsapp import Fournisseur, MessageRecu, Option, TypeMessage

log = logging.getLogger(__name__)

# Identifiants des boutons de confirmation : préfixe + « : » + identifiant du signalement.
STOCK_OUI = "stock_oui"
STOCK_NON = "stock_non"


class Intention(StrEnum):
    RUPTURE = "rupture"
    RETOUR = "retour"  # retour en stock
    RESUME = "resume"
    AUTRE = "autre"


@dataclass(frozen=True)
class Signalement:
    cite: str  # le nom tel que la pharmacie l'a écrit
    produit: str | None  # le produit du catalogue correspondant, None s'il est hors catalogue
    certain: bool


@dataclass(frozen=True)
class AnalysePharmacie:
    intention: Intention
    signalements: tuple[Signalement, ...]


PROMPT_PHARMACIE = """Tu analyses les messages WhatsApp qu'une pharmacie partenaire envoie à PharmaSûr, un service sénégalais qui indique dans quelles pharmacies un médicament est disponible. Le pharmacien écrit comme il parle, en français, parfois avec des fautes ou des mots en wolof, pour signaler une rupture de stock, un retour en stock, ou demander son résumé.

Le catalogue de la pharmacie est donné avant son message. Réponds uniquement avec le JSON demandé :

1. "intention", une seule valeur :
   - "rupture" : un ou plusieurs médicaments ne sont plus disponibles (« plus de Smecta », « Doliprane fini », « le mag 2 est en rupture de stock », « on n'a plus d'Amoxicilline sirop »).
   - "retour" : un ou plusieurs médicaments sont de nouveau disponibles (« le Doliprane est revenu », « Mag 2 de nouveau disponible », « on a reçu le Smecta »).
   - "resume" : la pharmacie demande son résumé ou ses chiffres (« résumé », « mes stats », « mon bilan de la semaine »).
   - "autre" : tout le reste (salutation, question, message incompréhensible).

2. "medicaments" : pour "rupture" et "retour", une entrée par médicament cité, dans l'ordre du message. Liste vide sinon. Chaque entrée contient :
   - "cite" : le nom tel que le pharmacien l'a écrit, avec le dosage et la forme s'il les a donnés (« doliprane 1000 », « dolipran sirop », « Ventoline »).
   - "produit" : le libellé EXACT, recopié caractère pour caractère, du produit du catalogue qui correspond, ou une chaîne vide si aucun produit du catalogue ne correspond (médicament hors catalogue).
   - "certain" : true seulement si le nom est écrit correctement et désigne sans hésitation ce seul produit du catalogue. false si le nom est approximatif ou mal orthographié (« dolipran », « smekta »), ou si plusieurs produits du catalogue pourraient correspondre.
   - Si le nom correspond à plusieurs produits du catalogue (« Doliprane » quand il y a un sirop et des comprimés), donne une entrée par produit possible, chacune avec "certain" à false.
   - Ne choisis jamais un produit qui porte un autre nom, même au même principe actif : « Efferalgan » ne correspond jamais à « Doliprane ». Un médicament absent du catalogue a "produit" vide.
   - « Mag2 », « mag 2 » et « Mag 2 » sont le même nom : une espace ou une majuscule de différence n'empêche pas d'être certain."""

SCHEMA_PHARMACIE = {
    "type": "object",
    "properties": {
        "intention": {"type": "string", "enum": [i.value for i in Intention]},
        "medicaments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cite": {"type": "string"},
                    "produit": {"type": "string"},
                    "certain": {"type": "boolean"},
                },
                "required": ["cite", "produit", "certain"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["intention", "medicaments"],
    "additionalProperties": False,
}


class AnalyseurPharmacie:
    def __init__(self, client: anthropic.Anthropic, modele: str, effort: str = "high"):
        self.client = client
        self.modele = modele
        self.effort = effort

    def analyser(self, texte: str, catalogue: list[str]) -> AnalysePharmacie:
        # Le catalogue va dans le message, pas dans le prompt système, pour garder celui-ci en cache.
        contenu = (
            "Catalogue de la pharmacie :\n"
            + "\n".join(f"- {libelle}" for libelle in catalogue)
            + "\n\nMessage du pharmacien :\n"
            + texte
        )
        donnees = appeler_claude(self.client, self.modele, self.effort, 4096, PROMPT_PHARMACIE, contenu, SCHEMA_PHARMACIE)
        try:
            intention = Intention(donnees["intention"])
            signalements = []
            for entree in donnees["medicaments"]:
                cite = str(entree["cite"]).strip()
                produit = str(entree["produit"]).strip() or None
                if not cite and not produit:
                    continue
                signalements.append(Signalement(cite or produit, produit, bool(entree["certain"])))
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise EchecAnalyse("réponse illisible") from e
        return AnalysePharmacie(intention, tuple(signalements))


def creer_analyseur_pharmacie(config: Config, client: anthropic.Anthropic | None = None) -> AnalyseurPharmacie | None:
    """None sans clé Anthropic : la pharmacie reçoit alors la réponse provisoire."""
    client = client or creer_client(config)
    if client is None:
        return None
    return AnalyseurPharmacie(client, config.modeles.pharmacie)


# --- Traitement ---


def _certain(signalement: Signalement) -> bool:
    """D19 : sûr seulement si Haiku l'est ET si le nom cité correspond vraiment au produit
    selon les règles de la recherche (même nom, dosage et forme s'ils sont donnés)."""
    if not signalement.certain or signalement.produit is None:
        return False
    demande, produit = analyser_medicament(signalement.cite), analyser_medicament(signalement.produit)
    return demande is not None and produit is not None and correspond(demande, produit)


def _nom_hors_catalogue(signalement: Signalement) -> str:
    """Le nom à ajouter au catalogue (D20), avec une majuscule (« ventoline » → « Ventoline »)."""
    nom = signalement.cite.strip()
    return nom[:1].upper() + nom[1:]


def traiter_message_pharmacie(
    message: MessageRecu,
    pharmacie: sqlite3.Row,
    fournisseur: Fournisseur,
    connexion: sqlite3.Connection,
    analyseur: AnalyseurPharmacie | None,
) -> None:
    numero = message.expediteur
    if message.type is TypeMessage.CHOIX:
        # Les boutons des demandes d'équivalent (parcours 2) d'abord, inchangés.
        if equivalent.repondre_pharmacie(message, pharmacie, fournisseur, connexion):
            return
        if repondre_confirmation(message, pharmacie, fournisseur, connexion):
            return
        fournisseur.envoyer_texte(numero, textes.AIDE_PHARMACIE)
        return
    if analyseur is None:
        fournisseur.envoyer_texte(numero, textes.PROVISOIRE_PHARMACIE.format(pharmacie=pharmacie["nom"]))
        return
    if message.type is not TypeMessage.TEXTE or not message.texte:
        fournisseur.envoyer_texte(numero, textes.AIDE_PHARMACIE)
        return

    catalogue = [ligne["libelle"] for ligne in db.catalogue_pharmacie(connexion, pharmacie["id"])]
    try:
        analyse = analyseur.analyser(message.texte, catalogue)
    except EchecAnalyse as e:
        log.warning("Message de pharmacie non analysé : %s", e)
        fournisseur.envoyer_texte(numero, textes.AIDE_PHARMACIE)
        return

    if analyse.intention is Intention.RESUME:
        envoyer_resume(numero, pharmacie, fournisseur, connexion)
        return
    if analyse.intention is Intention.AUTRE or not analyse.signalements:
        fournisseur.envoyer_texte(numero, textes.AIDE_PHARMACIE)
        return

    rupture = analyse.intention is Intention.RUPTURE
    for signalement in analyse.signalements:
        if signalement.produit is not None and signalement.produit not in catalogue:
            # Haiku a renvoyé un libellé qui n'est pas exactement dans le catalogue : doute.
            signalement = Signalement(signalement.cite, None, False)
        if signalement.produit is None:
            # D20 : hors catalogue, toujours une confirmation.
            nom = _nom_hors_catalogue(signalement)
            texte = (textes.HORS_CATALOGUE_RUPTURE if rupture else textes.HORS_CATALOGUE_RETOUR).format(produit=nom)
            demander_confirmation(numero, pharmacie, nom, rupture, True, texte, fournisseur, connexion)
        elif _certain(signalement):
            db.definir_rupture(connexion, pharmacie["id"], signalement.produit, rupture)
            texte = textes.RUPTURE_NOTEE if rupture else textes.RETOUR_NOTE
            fournisseur.envoyer_texte(numero, texte.format(produit=signalement.produit))
        else:
            # D19 : un doute, donc une confirmation.
            texte = (textes.CONFIRMER_RUPTURE if rupture else textes.CONFIRMER_RETOUR).format(produit=signalement.produit)
            demander_confirmation(numero, pharmacie, signalement.produit, rupture, False, texte, fournisseur, connexion)


def demander_confirmation(
    numero: str,
    pharmacie: sqlite3.Row,
    produit: str,
    rupture: bool,
    hors_catalogue: bool,
    texte: str,
    fournisseur: Fournisseur,
    connexion: sqlite3.Connection,
) -> None:
    signalement_id = db.creer_signalement(connexion, pharmacie["id"], produit, rupture, hors_catalogue)
    fournisseur.envoyer_choix(
        numero,
        texte,
        [
            Option(f"{STOCK_OUI}:{signalement_id}", textes.BOUTON_STOCK_OUI),
            Option(f"{STOCK_NON}:{signalement_id}", textes.BOUTON_STOCK_NON),
        ],
    )


def repondre_confirmation(
    message: MessageRecu, pharmacie: sqlite3.Row, fournisseur: Fournisseur, connexion: sqlite3.Connection
) -> bool:
    """Oui / Non sur une confirmation de signalement. Renvoie False si ce n'est pas un de ces boutons."""
    prefixe, _, reste = (message.choix_id or "").partition(":")
    if prefixe not in (STOCK_OUI, STOCK_NON) or not reste.isdigit():
        return False
    numero = message.expediteur
    ligne = db.prendre_signalement(connexion, int(reste), pharmacie["id"])
    if ligne is None:
        fournisseur.envoyer_texte(numero, textes.SIGNALEMENT_EXPIRE)
        return True
    if prefixe == STOCK_NON:
        fournisseur.envoyer_texte(numero, textes.SIGNALEMENT_ANNULE)
        return True
    rupture = bool(ligne["rupture"])
    db.definir_rupture(connexion, pharmacie["id"], ligne["produit"], rupture)
    if ligne["hors_catalogue"]:
        texte = textes.AJOUT_RUPTURE if rupture else textes.AJOUT_DISPONIBLE
    else:
        texte = textes.RUPTURE_NOTEE if rupture else textes.RETOUR_NOTE
    fournisseur.envoyer_texte(numero, texte.format(produit=ligne["produit"]))
    return True


def _pluriel(nombre: int) -> str:
    return "" if nombre == 1 else "s"


def formater_resume(apparitions: int, manquee: list[tuple[str, int]]) -> str:
    lignes = [textes.RESUME_TITRE, textes.RESUME_APPARITIONS.format(nombre=apparitions, s=_pluriel(apparitions))]
    if manquee:
        lignes.append(textes.RESUME_MANQUEE)
        lignes += [
            textes.RESUME_MANQUEE_LIGNE.format(medicament=medicament, nombre=nombre, s=_pluriel(nombre))
            for medicament, nombre in manquee
        ]
    else:
        lignes.append(textes.RESUME_MANQUEE_AUCUNE)
    return "\n".join(lignes)


def envoyer_resume(numero: str, pharmacie: sqlite3.Row, fournisseur: Fournisseur, connexion: sqlite3.Connection) -> None:
    """D14 : envoyé seulement sur demande, sans notification."""
    apparitions, manquee = db.resume_pharmacie(connexion, pharmacie["id"])
    fournisseur.envoyer_texte(numero, formater_resume(apparitions, manquee))

"""Parcours 2 : demande d'équivalent (D10, D11, D15, D16, D17, D36, D40, D41).

1. Après des résultats avec des introuvables, la personne reçoit la proposition (D10) :
   les lignes 🚫 et les boutons ✅ / ❌.
2. Sur ✅, une demande d'équivalent par médicament introuvable est ouverte pour
   23 heures et envoyée aux pharmacies partenaires joignables (D16, D17).
3. Chaque « Oui » d'une pharmacie prévient aussitôt la personne, avec le seul nom de
   la pharmacie, jamais celui du produit (D11). Un « Oui » sur une demande close reçoit
   seulement une réponse à la pharmacie (D41).
4. Chaque minute, les demandes échues sont closes ; sans aucun « Oui », la personne
   reçoit le message de fin de délai (D17, D36). La clôture efface le numéro (D15).
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime

from . import db, textes
from .recherche import Medicament
from .whatsapp import Fournisseur, MessageRecu, Option

log = logging.getLogger(__name__)

# Identifiants des boutons : préfixe + « : » + identifiant en base. Chaque message a ses
# propres boutons, donc plusieurs demandes peuvent être ouvertes en même temps (D40).
PROPOSITION_OUI = "equiv_oui"
PROPOSITION_NON = "equiv_non"
PHARMACIE_OUI = "pharma_oui"
PHARMACIE_NON = "pharma_non"


def identifiant(prefixe: str, numero_en_base: int) -> str:
    return f"{prefixe}:{numero_en_base}"


def lire_identifiant(choix_id: str | None) -> tuple[str, int] | None:
    """« equiv_oui:12 » → (« equiv_oui », 12). None si ce n'est pas un bouton du parcours 2."""
    if not choix_id or ":" not in choix_id:
        return None
    prefixe, _, reste = choix_id.partition(":")
    if prefixe not in (PROPOSITION_OUI, PROPOSITION_NON, PHARMACIE_OUI, PHARMACIE_NON) or not reste.isdigit():
        return None
    return prefixe, int(reste)


def est_choix_personne(choix_id: str | None) -> bool:
    lu = lire_identifiant(choix_id)
    return lu is not None and lu[0] in (PROPOSITION_OUI, PROPOSITION_NON)


# --- Côté personne ---


def proposer(numero: str, introuvables: list[Medicament], fournisseur: Fournisseur, connexion: sqlite3.Connection) -> None:
    """D10 : un seul message pour tous les introuvables d'une recherche, avec ✅ / ❌."""
    if not introuvables:
        return
    noms = [m.libelle for m in introuvables]
    proposition_id = db.creer_proposition(connexion, numero, noms)
    lignes = [textes.INTROUVABLE.format(medicament=nom) for nom in noms]
    lignes.append(textes.PROPOSITION_EQUIVALENT)
    fournisseur.envoyer_choix(
        numero,
        "\n".join(lignes),
        [
            Option(identifiant(PROPOSITION_OUI, proposition_id), textes.BOUTON_EQUIVALENT_OUI),
            Option(identifiant(PROPOSITION_NON, proposition_id), textes.BOUTON_EQUIVALENT_NON),
        ],
    )


def repondre_proposition(
    message: MessageRecu,
    fournisseur: Fournisseur,
    connexion: sqlite3.Connection,
    instant: datetime | None = None,
) -> None:
    """La personne a touché ✅ ou ❌ sous une proposition."""
    numero = message.expediteur
    prefixe, proposition_id = lire_identifiant(message.choix_id)
    medicaments = db.prendre_proposition(connexion, proposition_id, numero)
    if medicaments is None:
        # Bouton déjà touché, ou proposition expirée.
        fournisseur.envoyer_texte(numero, textes.NON_COMPRIS)
        return
    if prefixe == PROPOSITION_NON:
        fournisseur.envoyer_texte(numero, textes.EQUIVALENT_REFUSE)
        return

    pharmacies = db.pharmacies_joignables(connexion)
    if not pharmacies:
        log.warning("Aucune pharmacie joignable : NUMERO_PHARMACIE_BAOBAB est-il renseigné ?")
    for medicament in medicaments:
        demande_id = db.creer_demande(connexion, medicament, numero, instant)
        for pharmacie in pharmacies:
            envoyer_demande(pharmacie, demande_id, medicament, fournisseur)
    fournisseur.envoyer_texte(numero, textes.EQUIVALENT_ENVOYE)


def envoyer_demande(pharmacie: sqlite3.Row, demande_id: int, medicament: str, fournisseur: Fournisseur) -> None:
    """D16 : la demande ne dit rien de la personne (D15). Un échec n'arrête pas les autres envois."""
    try:
        fournisseur.envoyer_choix(
            pharmacie["numero_whatsapp"],
            textes.DEMANDE_PHARMACIE.format(medicament=medicament),
            [
                Option(identifiant(PHARMACIE_OUI, demande_id), textes.BOUTON_PHARMACIE_OUI),
                Option(identifiant(PHARMACIE_NON, demande_id), textes.BOUTON_PHARMACIE_NON),
            ],
        )
    except Exception:
        # Par exemple : la pharmacie n'a pas écrit au bot depuis 24 h (fenêtre WhatsApp, D16).
        log.exception("Envoi de la demande %s à %s impossible", demande_id, pharmacie["nom"])


# --- Côté pharmacie ---


def repondre_pharmacie(
    message: MessageRecu,
    pharmacie: sqlite3.Row,
    fournisseur: Fournisseur,
    connexion: sqlite3.Connection,
    instant: datetime | None = None,
) -> bool:
    """Réponse d'une pharmacie à une demande d'équivalent. Renvoie False si le message n'en est pas une."""
    lu = lire_identifiant(message.choix_id)
    if lu is None or lu[0] not in (PHARMACIE_OUI, PHARMACIE_NON):
        return False
    prefixe, demande_id = lu
    numero_pharmacie = message.expediteur
    demande = db.lire_demande(connexion, demande_id)
    if demande is None:
        fournisseur.envoyer_texte(numero_pharmacie, textes.DEMANDE_CLOSE_PHARMACIE)
        return True
    if prefixe == PHARMACIE_NON:
        # Le silence vaut déjà non (D16) : rien n'est gardé.
        fournisseur.envoyer_texte(numero_pharmacie, textes.MERCI_PHARMACIE_NON)
        return True
    if not db.demande_ouverte(demande, instant) or not demande["numero"]:
        fournisseur.envoyer_texte(numero_pharmacie, textes.DEMANDE_CLOSE_PHARMACIE)  # D41
        return True

    nouveau = db.enregistrer_oui(connexion, demande_id, pharmacie["id"], instant)
    fournisseur.envoyer_texte(numero_pharmacie, textes.MERCI_PHARMACIE_OUI)
    if nouveau:
        # D11 : le nom de la pharmacie et le médicament cherché, jamais le produit proposé.
        fournisseur.envoyer_texte(
            demande["numero"],
            textes.SOLUTION_TROUVEE.format(
                pharmacie=pharmacie["nom"],
                medicament=demande["medicament"],
                adresse=pharmacie["adresse"],
                telephone=pharmacie["telephone"],
                lien=pharmacie["lien_itineraire"],
            ),
        )
    return True


# --- Fin de délai (D17, D36) ---


def traiter_echeances(chemin_db: str, fournisseur: Fournisseur, instant: datetime | None = None) -> int:
    """Clôt les demandes échues. Renvoie le nombre de demandes closes.

    Tout est en base : après un redémarrage, les demandes échues entre-temps sont
    traitées au passage suivant.
    """
    connexion = db.connecter(chemin_db)
    closes = 0
    try:
        for demande in db.demandes_echues(connexion, instant):
            try:
                if demande["numero"] and db.nombre_de_oui(connexion, demande["id"]) == 0:
                    fournisseur.envoyer_texte(
                        demande["numero"], textes.AUCUNE_SOLUTION.format(medicament=demande["medicament"])
                    )
            except Exception:
                log.exception("Message de fin de délai de la demande %s impossible", demande["id"])
            # La demande est close même si l'envoi a échoué, pour ne pas réessayer sans fin.
            db.clore_demande(connexion, demande["id"])
            closes += 1
    finally:
        connexion.close()
    return closes

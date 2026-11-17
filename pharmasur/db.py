"""Base SQLite du bot (D35).

Le fichier est créé et rempli avec les données simulées de PARCOURS.md s'il n'existe
pas au démarrage. `python -m pharmasur.reset` le remet à zéro avant une répétition.

Ce que la base garde (D15) :
- d'un numéro de personne, seulement le numéro et la date du premier contact ;
- les recherches, sans aucun lien avec le numéro ;
- le lien numéro ↔ demande d'équivalent, effacé à la clôture de la demande (D17) ;
- les corrections de lecture, sans image ni numéro (D22) ;
- la forme (vocal ou texte) du dernier message d'un numéro, effacée après 24 h (D23).
"""

from __future__ import annotations

import json
import logging
import random
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote_plus

from .recherche import (
    Medicament,
    Pharmacie,
    ProduitCatalogue,
    ResultatRecherche,
    analyser_medicament,
    rechercher,
)

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE pharmacie (
    id              INTEGER PRIMARY KEY,
    nom             TEXT NOT NULL,
    adresse         TEXT NOT NULL,
    telephone       TEXT NOT NULL,           -- affiché dans la fiche (D7)
    lien_itineraire TEXT NOT NULL,
    numero_whatsapp TEXT NOT NULL UNIQUE     -- reconnaît la pharmacie qui écrit au bot (D4)
);

-- Catalogue (D3) : un produit est disponible, sauf rupture signalée (D2).
CREATE TABLE catalogue (
    id           INTEGER PRIMARY KEY,
    pharmacie_id INTEGER NOT NULL REFERENCES pharmacie(id),
    libelle      TEXT NOT NULL,
    en_rupture   INTEGER NOT NULL DEFAULT 0,
    UNIQUE (pharmacie_id, libelle)
);

-- Premier contact (D8, D15) : seulement le numéro et la date.
CREATE TABLE premier_contact (
    numero TEXT PRIMARY KEY,
    date   TEXT NOT NULL
);

-- Recherches (D15) : aucun lien avec le numéro de la personne.
CREATE TABLE recherche (
    id   INTEGER PRIMARY KEY,
    date TEXT NOT NULL
);

CREATE TABLE recherche_medicament (
    id           INTEGER PRIMARY KEY,
    recherche_id INTEGER NOT NULL REFERENCES recherche(id),
    medicament   TEXT NOT NULL,
    introuvable  INTEGER NOT NULL
);

-- Pharmacies qui avaient chaque médicament (résumé D14, tableau de bord D26).
CREATE TABLE recherche_pharmacie (
    recherche_medicament_id INTEGER NOT NULL REFERENCES recherche_medicament(id),
    pharmacie_id            INTEGER NOT NULL REFERENCES pharmacie(id),
    PRIMARY KEY (recherche_medicament_id, pharmacie_id)
);

-- Demande d'équivalent (D10, D16, D17). Le numéro est effacé à la clôture (D15).
CREATE TABLE demande_equivalent (
    id         INTEGER PRIMARY KEY,
    medicament TEXT NOT NULL,
    numero     TEXT,
    cree_le    TEXT NOT NULL,
    fin_le     TEXT NOT NULL,                -- vérifiée chaque minute (D36)
    close      INTEGER NOT NULL DEFAULT 0
);

-- Seuls les « Oui » sont gardés : le silence vaut non (D16).
CREATE TABLE reponse_equivalent (
    demande_id   INTEGER NOT NULL REFERENCES demande_equivalent(id),
    pharmacie_id INTEGER NOT NULL REFERENCES pharmacie(id),
    date         TEXT NOT NULL,
    PRIMARY KEY (demande_id, pharmacie_id)
);

-- Corrections de lecture (D22) : « lu → corrigé », sans image ni numéro.
CREATE TABLE correction_lecture (
    id      INTEGER PRIMARY KEY,
    lu      TEXT NOT NULL,
    corrige TEXT NOT NULL,
    date    TEXT NOT NULL
);
"""

# Ajoutée avec le parcours 6 : créée aussi dans une base qui existait déjà.
SCHEMA_LECTURE = """
-- Lecture d'une photo en attente de confirmation (D13). Jamais l'image : seulement les
-- noms lus. Supprimée dès la confirmation (D22), et au plus tard après 24 h (D15).
CREATE TABLE IF NOT EXISTS lecture_en_attente (
    numero            TEXT PRIMARY KEY,
    medicaments       TEXT NOT NULL,             -- liste JSON des noms lus, puis corrigés
    non_lus           INTEGER NOT NULL DEFAULT 0, -- médicaments illisibles (D21)
    premier_contact   INTEGER NOT NULL DEFAULT 0, -- accueil court à envoyer avant les résultats (D8)
    attend_correction INTEGER NOT NULL DEFAULT 0, -- la personne a touché « Corriger »
    cree_le           TEXT NOT NULL
);
"""
DUREE_LECTURE_EN_ATTENTE = timedelta(hours=24)

# Ajoutée avec le parcours 2 : créée aussi dans une base qui existait déjà.
SCHEMA_EQUIVALENT = """
-- Proposition de demande d'équivalent (D10) en attente de ✅ ou ❌. Seulement les noms
-- introuvables ; supprimée dès la réponse, et au plus tard après 24 h (D15).
CREATE TABLE IF NOT EXISTS proposition_equivalent (
    id          INTEGER PRIMARY KEY,
    numero      TEXT NOT NULL,
    medicaments TEXT NOT NULL,                  -- liste JSON des médicaments introuvables
    cree_le     TEXT NOT NULL
);
"""
DUREE_PROPOSITION = timedelta(hours=24)

# Ajoutée avec le parcours 7 : créée aussi dans une base qui existait déjà.
SCHEMA_FORME = """
-- Forme du dernier message de la personne, vocal ou texte (D23), pour répondre dans la
-- même forme, y compris plus tard (demande d'équivalent). Une ligne par numéro, sans
-- historique, remplacée à chaque message et effacée après 24 h (D15).
CREATE TABLE IF NOT EXISTS forme_conversation (
    numero TEXT PRIMARY KEY,
    vocal  INTEGER NOT NULL DEFAULT 0,
    date   TEXT NOT NULL
);
"""
DUREE_FORME = timedelta(hours=24)
DUREE_DEMANDE = timedelta(hours=23)  # D17

# --- Données simulées (PARCOURS.md, « Données simulées à préparer ») ---
# Les noms, adresses et numéros sont fictifs, à remplacer.

PHARMACIES_SIMULEES = [
    {
        "nom": "Pharmacie Baobab",
        "adresse": "Rue 10, Grand Yoff",
        "telephone": "+221 33 000 00 01",
        "numero_whatsapp": None,  # vrai numéro, lu dans NUMERO_PHARMACIE_BAOBAB
        "catalogue": [
            "Amoxicilline 250 mg/5 ml sirop",
            "Doliprane 2,4 % sirop",
            "Doliprane 1000 mg comprimés",
            # Ordonnance de test : Richifer et Mag 2 disponibles ; UPSA-C est la solution
            # que Baobab a pour la vitamine C prescrite, introuvable (parcours 2, D11).
            "Richifer gélules",
            "Mag 2 100 mg comprimés",
            "UPSA-C 1000 mg comprimés effervescents",
        ],
    },
    {
        "nom": "Pharmacie Liberté",
        "adresse": "Liberté 6, Dakar",
        "telephone": "+221 33 000 00 02",
        "numero_whatsapp": "221330000002",
        "catalogue": ["Amoxicilline 250 mg/5 ml sirop", "Amoxicilline 500 mg gélules", "Mag 2 100 mg comprimés"],
    },
    {
        "nom": "Pharmacie Teranga",
        "adresse": "Avenue Cheikh Anta Diop, Fann",
        "telephone": "+221 33 000 00 03",
        "numero_whatsapp": "221330000003",
        "catalogue": ["Doliprane 1000 mg comprimés", "Efferalgan 500 mg", "Richifer gélules"],
    },
    {
        "nom": "Pharmacie Jamm",
        "adresse": "Sicap Amitié 2, Dakar",
        "telephone": "+221 33 000 00 04",
        "numero_whatsapp": "221330000004",
        "catalogue": ["Clamoxyl 500 mg"],
    },
]
NUMERO_BAOBAB_FICTIF = "221330000001"
# Numéros inventés : Meta refuserait d'y envoyer un message (seuls 5 numéros réels sont
# autorisés avec le numéro de test, D29). Les demandes d'équivalent les sautent.
NUMEROS_FICTIFS = frozenset(
    [p["numero_whatsapp"] for p in PHARMACIES_SIMULEES if p["numero_whatsapp"]] + [NUMERO_BAOBAB_FICTIF]
)

# Recherches simulées (D14) : (nombre de recherches, médicaments). Smecta et Spasfon
# ne sont dans aucun catalogue : ils alimentent la demande manquée du résumé.
RECHERCHES_SIMULEES = [
    (7, ["Smecta"]),
    (5, ["Smecta", "Doliprane"]),
    (5, ["Spasfon"]),
    (3, ["Spasfon", "Amoxicilline sirop"]),
    (6, ["Doliprane 1000 comprimés"]),
    (4, ["Amoxicilline 500 mg"]),
    (3, ["Efferalgan 500 mg"]),
    (2, ["Clamoxyl"]),
    (3, ["Ventoline"]),
    (2, ["Amoxicilline sirop", "Doliprane sirop"]),
]


def maintenant() -> datetime:
    return datetime.now(timezone.utc)


def normaliser_numero(numero: str) -> str:
    """« +221 77 123 45 67 » → « 221771234567 » (format des numéros chez WhatsApp)."""
    return re.sub(r"\D", "", numero or "")


def lien_itineraire(adresse: str) -> str:
    return "https://maps.google.com/?q=" + quote_plus(f"{adresse}, Sénégal")


def connecter(chemin: str) -> sqlite3.Connection:
    connexion = sqlite3.connect(chemin)
    connexion.row_factory = sqlite3.Row
    connexion.execute("PRAGMA foreign_keys = ON")
    return connexion


def initialiser(chemin: str, numero_baobab: str = "", graine: int | None = None) -> bool:
    """Crée et remplit la base si le fichier n'existe pas. Renvoie True si elle a été créée."""
    if Path(chemin).exists():
        connexion = connecter(chemin)
        try:
            with connexion:
                connexion.executescript(SCHEMA_LECTURE + SCHEMA_EQUIVALENT + SCHEMA_FORME)  # tables ajoutées depuis la création
        finally:
            connexion.close()
        return False
    connexion = connecter(chemin)
    try:
        with connexion:
            connexion.executescript(SCHEMA + SCHEMA_LECTURE + SCHEMA_EQUIVALENT + SCHEMA_FORME)
            remplir(connexion, numero_baobab, random.Random(graine))
    finally:
        connexion.close()
    log.info("Base créée avec les données simulées : %s", chemin)
    return True


def remettre_a_zero(chemin: str, numero_baobab: str = "") -> None:
    """Efface la base et la recrée avec les données simulées (avant une répétition)."""
    Path(chemin).unlink(missing_ok=True)
    initialiser(chemin, numero_baobab)


def remplir(connexion: sqlite3.Connection, numero_baobab: str, hasard: random.Random) -> None:
    numero_baobab = normaliser_numero(numero_baobab)
    if not numero_baobab:
        log.warning("NUMERO_PHARMACIE_BAOBAB est vide : Baobab reçoit un numéro fictif.")
        numero_baobab = NUMERO_BAOBAB_FICTIF
    for donnees in PHARMACIES_SIMULEES:
        curseur = connexion.execute(
            "INSERT INTO pharmacie (nom, adresse, telephone, lien_itineraire, numero_whatsapp)"
            " VALUES (?, ?, ?, ?, ?)",
            (
                donnees["nom"],
                donnees["adresse"],
                donnees["telephone"],
                lien_itineraire(donnees["adresse"]),
                donnees["numero_whatsapp"] or numero_baobab,
            ),
        )
        connexion.executemany(
            "INSERT INTO catalogue (pharmacie_id, libelle) VALUES (?, ?)",
            [(curseur.lastrowid, libelle) for libelle in donnees["catalogue"]],
        )

    # Recherches simulées, réparties sur les 7 derniers jours (D14).
    pharmacies = charger_pharmacies(connexion)
    debut = maintenant() - timedelta(days=7)
    for nombre, textes in RECHERCHES_SIMULEES:
        demandes = [m for m in (analyser_medicament(t) for t in textes) if m]
        for _ in range(nombre):
            date = debut + timedelta(seconds=hasard.randint(0, 7 * 24 * 3600))
            enregistrer_recherche(connexion, rechercher(demandes, pharmacies, hasard), date)


# --- Lecture ---


def charger_pharmacies(connexion: sqlite3.Connection) -> list[Pharmacie]:
    pharmacies = []
    for ligne in connexion.execute("SELECT * FROM pharmacie ORDER BY id"):
        catalogue = tuple(
            ProduitCatalogue(produit["libelle"], bool(produit["en_rupture"]))
            for produit in connexion.execute(
                "SELECT libelle, en_rupture FROM catalogue WHERE pharmacie_id = ? ORDER BY id", (ligne["id"],)
            )
        )
        pharmacies.append(
            Pharmacie(
                id=ligne["id"],
                nom=ligne["nom"],
                adresse=ligne["adresse"],
                telephone=ligne["telephone"],
                lien_itineraire=ligne["lien_itineraire"],
                catalogue=catalogue,
            )
        )
    return pharmacies


def pharmacie_par_numero(connexion: sqlite3.Connection, numero: str) -> sqlite3.Row | None:
    """La pharmacie partenaire inscrite à ce numéro, ou None (D4)."""
    return connexion.execute(
        "SELECT * FROM pharmacie WHERE numero_whatsapp = ?", (normaliser_numero(numero),)
    ).fetchone()


# --- Écriture ---


def enregistrer_premier_contact(connexion: sqlite3.Connection, numero: str) -> bool:
    """Note le premier contact d'un numéro. Renvoie True si c'est bien le premier (D8)."""
    with connexion:
        curseur = connexion.execute(
            "INSERT OR IGNORE INTO premier_contact (numero, date) VALUES (?, ?)",
            (normaliser_numero(numero), maintenant().isoformat()),
        )
    return curseur.rowcount == 1


def enregistrer_recherche(
    connexion: sqlite3.Connection, resultat: ResultatRecherche, date: datetime | None = None
) -> int:
    """Garde la recherche sans aucun lien avec le numéro (D15)."""
    date = date or maintenant()
    with connexion:
        recherche_id = connexion.execute(
            "INSERT INTO recherche (date) VALUES (?)", (date.isoformat(),)
        ).lastrowid
        for i, demande in enumerate(resultat.demandes):
            medicament_id = connexion.execute(
                "INSERT INTO recherche_medicament (recherche_id, medicament, introuvable) VALUES (?, ?, ?)",
                (recherche_id, demande.libelle, int(demande in resultat.introuvables)),
            ).lastrowid
            connexion.executemany(
                "INSERT INTO recherche_pharmacie (recherche_medicament_id, pharmacie_id) VALUES (?, ?)",
                [(medicament_id, r.pharmacie.id) for r in resultat.pharmacies if r.produits[i]],
            )
    return recherche_id


# --- Lecture de photo en attente de confirmation (parcours 6, D13, D22) ---


def _purger_lectures(connexion: sqlite3.Connection) -> None:
    limite = (maintenant() - DUREE_LECTURE_EN_ATTENTE).isoformat()
    connexion.execute("DELETE FROM lecture_en_attente WHERE cree_le < ?", (limite,))


def enregistrer_lecture(
    connexion: sqlite3.Connection, numero: str, medicaments: list[str], non_lus: int, premier_contact: bool
) -> None:
    """Remplace la lecture en attente de ce numéro (une nouvelle photo annule la précédente)."""
    with connexion:
        _purger_lectures(connexion)
        connexion.execute(
            "INSERT OR REPLACE INTO lecture_en_attente"
            " (numero, medicaments, non_lus, premier_contact, attend_correction, cree_le) VALUES (?, ?, ?, ?, 0, ?)",
            (normaliser_numero(numero), json.dumps(medicaments), non_lus, int(premier_contact), maintenant().isoformat()),
        )


def lire_lecture(connexion: sqlite3.Connection, numero: str) -> dict | None:
    with connexion:
        _purger_lectures(connexion)
    ligne = connexion.execute(
        "SELECT * FROM lecture_en_attente WHERE numero = ?", (normaliser_numero(numero),)
    ).fetchone()
    if ligne is None:
        return None
    return {
        "medicaments": json.loads(ligne["medicaments"]),
        "non_lus": ligne["non_lus"],
        "premier_contact": bool(ligne["premier_contact"]),
        "attend_correction": bool(ligne["attend_correction"]),
    }


def mettre_a_jour_lecture(
    connexion: sqlite3.Connection,
    numero: str,
    *,
    medicaments: list[str] | None = None,
    non_lus: int | None = None,
    attend_correction: bool | None = None,
) -> None:
    champs, valeurs = [], []
    if medicaments is not None:
        champs.append("medicaments = ?")
        valeurs.append(json.dumps(medicaments))
    if non_lus is not None:
        champs.append("non_lus = ?")
        valeurs.append(non_lus)
    if attend_correction is not None:
        champs.append("attend_correction = ?")
        valeurs.append(int(attend_correction))
    if not champs:
        return
    with connexion:
        connexion.execute(
            f"UPDATE lecture_en_attente SET {', '.join(champs)} WHERE numero = ?",
            (*valeurs, normaliser_numero(numero)),
        )


def supprimer_lecture(connexion: sqlite3.Connection, numero: str) -> None:
    """Efface le lien entre le numéro et les noms lus (D15, D22)."""
    with connexion:
        connexion.execute("DELETE FROM lecture_en_attente WHERE numero = ?", (normaliser_numero(numero),))


def enregistrer_correction(connexion: sqlite3.Connection, lu: str, corrige: str) -> None:
    """Garde seulement le couple « lu → corrigé », sans image ni numéro (D22)."""
    with connexion:
        connexion.execute(
            "INSERT INTO correction_lecture (lu, corrige, date) VALUES (?, ?, ?)", (lu, corrige, maintenant().isoformat())
        )


# --- Demande d'équivalent (parcours 2, D10, D15, D16, D17, D36, D40, D41) ---


def _instant(instant: datetime | None) -> datetime:
    return instant or maintenant()


def creer_proposition(
    connexion: sqlite3.Connection, numero: str, medicaments: list[str], instant: datetime | None = None
) -> int:
    """Garde les médicaments introuvables en attendant ✅ ou ❌ (D10)."""
    instant = _instant(instant)
    with connexion:
        limite = (instant - DUREE_PROPOSITION).isoformat()
        connexion.execute("DELETE FROM proposition_equivalent WHERE cree_le < ?", (limite,))
        return connexion.execute(
            "INSERT INTO proposition_equivalent (numero, medicaments, cree_le) VALUES (?, ?, ?)",
            (normaliser_numero(numero), json.dumps(medicaments), instant.isoformat()),
        ).lastrowid


def prendre_proposition(connexion: sqlite3.Connection, proposition_id: int, numero: str) -> list[str] | None:
    """Renvoie les médicaments de la proposition et l'efface (D15). None si elle n'existe plus."""
    with connexion:
        ligne = connexion.execute(
            "SELECT medicaments FROM proposition_equivalent WHERE id = ? AND numero = ?",
            (proposition_id, normaliser_numero(numero)),
        ).fetchone()
        if ligne is None:
            return None
        connexion.execute("DELETE FROM proposition_equivalent WHERE id = ?", (proposition_id,))
    return json.loads(ligne["medicaments"])


def creer_demande(
    connexion: sqlite3.Connection, medicament: str, numero: str, instant: datetime | None = None
) -> int:
    """Ouvre une demande d'équivalent pour 23 heures (D17). Plusieurs par numéro (D40)."""
    instant = _instant(instant)
    with connexion:
        return connexion.execute(
            "INSERT INTO demande_equivalent (medicament, numero, cree_le, fin_le) VALUES (?, ?, ?, ?)",
            (medicament, normaliser_numero(numero), instant.isoformat(), (instant + DUREE_DEMANDE).isoformat()),
        ).lastrowid


def lire_demande(connexion: sqlite3.Connection, demande_id: int) -> sqlite3.Row | None:
    return connexion.execute("SELECT * FROM demande_equivalent WHERE id = ?", (demande_id,)).fetchone()


def demande_ouverte(demande: sqlite3.Row, instant: datetime | None = None) -> bool:
    return not demande["close"] and demande["fin_le"] > _instant(instant).isoformat()


def pharmacies_joignables(connexion: sqlite3.Connection) -> list[sqlite3.Row]:
    """Les pharmacies partenaires à qui le bot peut vraiment écrire (numéro non fictif)."""
    return [
        ligne
        for ligne in connexion.execute("SELECT * FROM pharmacie ORDER BY id")
        if ligne["numero_whatsapp"] not in NUMEROS_FICTIFS
    ]


def enregistrer_oui(
    connexion: sqlite3.Connection, demande_id: int, pharmacie_id: int, instant: datetime | None = None
) -> bool:
    """Garde le « Oui » d'une pharmacie (D16). Renvoie False si elle l'avait déjà dit."""
    with connexion:
        curseur = connexion.execute(
            "INSERT OR IGNORE INTO reponse_equivalent (demande_id, pharmacie_id, date) VALUES (?, ?, ?)",
            (demande_id, pharmacie_id, _instant(instant).isoformat()),
        )
    return curseur.rowcount == 1


def nombre_de_oui(connexion: sqlite3.Connection, demande_id: int) -> int:
    return connexion.execute(
        "SELECT COUNT(*) FROM reponse_equivalent WHERE demande_id = ?", (demande_id,)
    ).fetchone()[0]


def demandes_echues(connexion: sqlite3.Connection, instant: datetime | None = None) -> list[sqlite3.Row]:
    """Demandes encore ouvertes dont les 23 heures sont écoulées (D36)."""
    return connexion.execute(
        "SELECT * FROM demande_equivalent WHERE close = 0 AND fin_le <= ? ORDER BY id",
        (_instant(instant).isoformat(),),
    ).fetchall()


def clore_demande(connexion: sqlite3.Connection, demande_id: int) -> None:
    """Clôt la demande et efface le lien avec le numéro de la personne (D15)."""
    with connexion:
        connexion.execute("UPDATE demande_equivalent SET close = 1, numero = NULL WHERE id = ?", (demande_id,))


__all__ = [
    "Medicament",
    "charger_pharmacies",
    "connecter",
    "enregistrer_premier_contact",
    "enregistrer_recherche",
    "initialiser",
    "normaliser_numero",
    "pharmacie_par_numero",
    "remettre_a_zero",
]


# --- Forme de la conversation, vocal ou texte (parcours 7, D23) ---


def definir_forme(connexion: sqlite3.Connection, numero: str, vocal: bool) -> None:
    """Retient si le dernier message de la personne était un vocal. Remplace la valeur précédente."""
    with connexion:
        limite = (maintenant() - DUREE_FORME).isoformat()
        connexion.execute("DELETE FROM forme_conversation WHERE date < ?", (limite,))
        connexion.execute(
            "INSERT OR REPLACE INTO forme_conversation (numero, vocal, date) VALUES (?, ?, ?)",
            (normaliser_numero(numero), int(vocal), maintenant().isoformat()),
        )


def est_vocal(connexion: sqlite3.Connection, numero: str) -> bool:
    """True si le dernier message de ce numéro, depuis moins de 24 h, était un vocal."""
    limite = (maintenant() - DUREE_FORME).isoformat()
    ligne = connexion.execute(
        "SELECT vocal FROM forme_conversation WHERE numero = ? AND date >= ?", (normaliser_numero(numero), limite)
    ).fetchone()
    return bool(ligne and ligne["vocal"])

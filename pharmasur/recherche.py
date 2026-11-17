"""Recherche : quelles pharmacies partenaires ont les médicaments demandés.

Logique pure, sans réseau ni IA, testable seule. Règles appliquées :

- D5  : une recherche peut porter sur plusieurs médicaments ; « introuvable » se juge
        médicament par médicament.
- D27 : la comparaison suit ce que la personne précise. Dosage et forme ne comptent
        que s'ils sont donnés. Un autre nom commercial n'est jamais compté.
- D28 : un principe actif se cherche comme un nom : un produit compte si son nom
        contient les mots demandés (« amoxicilline » → « Amoxicilline 500 mg gélules »,
        mais pas « Clamoxyl 500 mg »).
- D3  : un médicament du catalogue est disponible, sauf rupture signalée.
- D25 : d'abord les pharmacies qui ont le plus de médicaments de la liste, puis le
        hasard entre ex æquo.
- D7, D8 : contenu de la fiche résultat et rappel de sécurité.
"""

from __future__ import annotations

import random
import re
import unicodedata
from dataclasses import dataclass, field

from .textes import RAPPEL_SECURITE

# Formes reconnues, sous leur forme normalisée (sans accent, au singulier) → forme canonique.
FORMES = {
    "sirop": "sirop",
    "comprime": "comprime",
    "cp": "comprime",
    "cps": "comprime",
    "gelule": "gelule",
    "capsule": "capsule",
    "sachet": "sachet",
    "suppositoire": "suppositoire",
    "suppo": "suppositoire",
    "pommade": "pommade",
    "creme": "creme",
    "gel": "gel",
    "goutte": "goutte",
    "injectable": "injectable",
    "ampoule": "ampoule",
    "suspension": "suspension",
    "solution": "solution",
    "collyre": "collyre",
    "spray": "spray",
    "inhalateur": "inhalateur",
    "effervescent": "effervescent",
}

# Mots sans rapport avec le nom du médicament, ignorés dans un texte libre.
MOTS_VIDES = {
    "a", "au", "aux", "avec", "besoin", "bonjour", "bonsoir", "buvable", "cherche", "d", "de", "des",
    "du", "en", "et", "faut", "fille", "fils", "il", "j", "je", "l", "la", "le", "les", "ma", "me",
    "merci", "mes", "mon", "plait", "pour", "recherche", "s", "salut", "stp", "svp", "un", "une",
    "veux", "vous", "voudrais",
}

UNITES = r"mg|g|ml|%|mcg|µg|ug|ui"
# Un dosage : « 1000 », « 1000mg », « 2,4 % », « 250 mg/5 ml »…
DOSAGE_RE = re.compile(
    rf"(?<![\w,.])(\d+(?:[.,]\d+)?)\s*({UNITES})?(?:\s*/\s*(\d+(?:[.,]\d+)?)?\s*({UNITES}))?(?![\w])",
    re.IGNORECASE,
)


def normaliser(mot: str) -> str:
    """Minuscules, sans accents."""
    decompose = unicodedata.normalize("NFKD", mot.lower())
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _forme_canonique(mot_normalise: str) -> str | None:
    if mot_normalise in FORMES:
        return FORMES[mot_normalise]
    if mot_normalise.endswith("s") and mot_normalise[:-1] in FORMES:
        return FORMES[mot_normalise[:-1]]
    return None


def _valeur(nombre: str, unite: str | None) -> float:
    valeur = float(nombre.replace(",", "."))
    if unite and unite.lower() == "g":
        valeur *= 1000  # 1 g = 1000 mg
    return valeur


@dataclass(frozen=True)
class Medicament:
    """Un médicament tel qu'il est écrit, découpé en nom, dosage et forme."""

    libelle: str  # texte à afficher, nettoyé (« Amoxicilline sirop »)
    nom: tuple[str, ...]  # mots du nom, normalisés (« amoxicilline »,)
    dosage: tuple[float, ...] = ()  # nombres du dosage, en mg pour les grammes (250.0, 5.0)
    forme: str | None = None  # forme canonique (« sirop »)

    @property
    def cle(self) -> tuple:
        return (self.nom, self.dosage, self.forme)


def analyser_medicament(texte: str) -> Medicament | None:
    """Découpe un texte (« Doliprane 1000 comprimés ») en nom, dosage et forme.

    Renvoie None si le texte ne contient aucun mot de nom (par exemple « Bonjour »).
    """
    texte = texte.strip()
    dosage: list[float] = []
    morceaux_dosage: list[str] = []
    for correspondance in DOSAGE_RE.finditer(texte):
        nombre1, unite1, nombre2, unite2 = correspondance.groups()
        dosage.append(_valeur(nombre1, unite1))
        if nombre2:
            dosage.append(_valeur(nombre2, unite2))
        morceaux_dosage.append(correspondance.group(0).strip())
    reste = DOSAGE_RE.sub(" ", texte)

    nom_affiche: list[str] = []
    nom: list[str] = []
    forme: str | None = None
    forme_affichee: str | None = None
    for mot in re.findall(r"[^\W\d_]+", reste):
        mot_normalise = normaliser(mot)
        canonique = _forme_canonique(mot_normalise)
        if canonique:
            if forme is None:
                forme, forme_affichee = canonique, mot.lower()
            continue
        if mot_normalise in MOTS_VIDES:
            continue
        nom.append(mot_normalise)
        nom_affiche.append(mot)

    if not nom:
        return None
    libelle = " ".join(nom_affiche + morceaux_dosage + ([forme_affichee] if forme_affichee else []))
    libelle = libelle[0].upper() + libelle[1:]
    return Medicament(libelle=libelle, nom=tuple(nom), dosage=tuple(dosage), forme=forme)


def correspond(demande: Medicament, produit: Medicament) -> bool:
    """Le produit du catalogue répond-il à la demande ? (D27, D28)"""
    if not set(demande.nom) <= set(produit.nom):
        return False  # autre nom commercial : jamais compté
    if demande.dosage and produit.dosage[: len(demande.dosage)] != demande.dosage:
        return False
    if demande.forme and produit.forme != demande.forme:
        return False
    return True


# --- Données d'entrée ---


@dataclass(frozen=True)
class ProduitCatalogue:
    libelle: str  # tel qu'affiché dans la fiche (« Doliprane 1000 mg comprimés »)
    en_rupture: bool = False


@dataclass(frozen=True)
class Pharmacie:
    id: int
    nom: str
    adresse: str
    telephone: str
    lien_itineraire: str
    catalogue: tuple[ProduitCatalogue, ...] = ()


# --- Résultat ---


@dataclass(frozen=True)
class ResultatPharmacie:
    pharmacie: Pharmacie
    # Pour chaque médicament demandé (même ordre que la recherche) : les produits disponibles.
    produits: tuple[tuple[str, ...], ...]

    @property
    def nombre(self) -> int:
        """Nombre de médicaments de la liste que la pharmacie a."""
        return sum(1 for trouves in self.produits if trouves)


@dataclass(frozen=True)
class ResultatRecherche:
    demandes: tuple[Medicament, ...]
    pharmacies: tuple[ResultatPharmacie, ...]  # déjà dans l'ordre D25
    introuvables: tuple[Medicament, ...] = field(default=())


def dedoublonner(demandes: list[Medicament]) -> list[Medicament]:
    vus: set[tuple] = set()
    uniques = []
    for demande in demandes:
        if demande.cle not in vus:
            vus.add(demande.cle)
            uniques.append(demande)
    return uniques


def rechercher(
    demandes: list[Medicament], pharmacies: list[Pharmacie], hasard: random.Random | None = None
) -> ResultatRecherche:
    """Cherche chaque médicament dans le catalogue de chaque pharmacie partenaire."""
    hasard = hasard or random.Random()
    demandes = dedoublonner(demandes)

    resultats: list[ResultatPharmacie] = []
    for pharmacie in pharmacies:
        produits_analyses = [
            (produit.libelle, analyser_medicament(produit.libelle))
            for produit in pharmacie.catalogue
            if not produit.en_rupture
        ]
        produits = tuple(
            tuple(libelle for libelle, analyse in produits_analyses if analyse and correspond(demande, analyse))
            for demande in demandes
        )
        resultat = ResultatPharmacie(pharmacie, produits)
        if resultat.nombre:
            resultats.append(resultat)

    # D25 : le plus de médicaments d'abord, puis le hasard entre ex æquo.
    tirage = {resultat.pharmacie.id: hasard.random() for resultat in resultats}
    resultats.sort(key=lambda r: (-r.nombre, tirage[r.pharmacie.id]))

    introuvables = tuple(
        demande for i, demande in enumerate(demandes) if not any(r.produits[i] for r in resultats)
    )
    return ResultatRecherche(tuple(demandes), tuple(resultats), introuvables)


def formater_fiche(resultat: ResultatRecherche) -> str | None:
    """Fiche résultat du parcours 1 (D7, D8). None si aucune pharmacie n'a rien."""
    if not resultat.pharmacies:
        return None
    total = len(resultat.demandes)
    lignes = ["Vos médicaments : " + ", ".join(d.libelle for d in resultat.demandes), ""]
    for rang, r in enumerate(resultat.pharmacies, start=1):
        lignes.append(f"{rang}. {r.pharmacie.nom} — {r.nombre} sur {total}")
        for trouves in r.produits:
            if trouves:
                lignes.append("   ✅ " + ", ".join(trouves))
        lignes.append(f"   📍 {r.pharmacie.adresse}")
        lignes.append(f"   📞 {r.pharmacie.telephone}")
        lignes.append(f"   🗺️ {r.pharmacie.lien_itineraire}")
        lignes.append("")
    lignes.append(RAPPEL_SECURITE)
    return "\n".join(lignes)


def decouper_texte(texte: str) -> list[Medicament]:
    """Découpage provisoire d'un texte libre, en attendant l'extraction par Claude.

    Coupe aux virgules, points-virgules, retours à la ligne et « et ».
    """
    morceaux = re.split(r"[,;\n+]|\bet\b", texte, flags=re.IGNORECASE)
    medicaments = [analyser_medicament(morceau) for morceau in morceaux]
    return [m for m in medicaments if m is not None]

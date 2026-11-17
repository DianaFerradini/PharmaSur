"""Compréhension des messages par Claude (parcours 1, puis 7 pour les transcriptions)
et lecture des photos d'ordonnance ou de boîte (parcours 6).

Un seul appel par message : la catégorie (salutation, recherche, hors sujet, urgence,
autre) et les médicaments demandés, tels que la personne les a écrits. Claude ne
remplace jamais un nom par un autre et n'ajoute aucun médicament (D11, D27, D28) :
la correspondance avec les catalogues reste faite par `recherche.py`.
"""

from __future__ import annotations

import base64
import json
import re
import logging
from dataclasses import dataclass
from enum import StrEnum

import anthropic

from .config import Config

log = logging.getLogger(__name__)


class Categorie(StrEnum):
    SALUTATION = "salutation"  # salutation seule, sans médicament
    RECHERCHE = "recherche"  # au moins un médicament cherché
    HORS_SUJET = "hors_sujet"  # question de santé, de prix, commande… (D9)
    URGENCE = "urgence"  # urgence médicale (D9)
    AUTRE = "autre"  # incompréhensible


@dataclass(frozen=True)
class AnalyseMessage:
    categorie: Categorie
    salue: bool  # la personne dit bonjour (D8 : on la salue en retour)
    medicaments: tuple[str, ...]  # tels qu'écrits, orthographe évidente corrigée


class EchecAnalyse(Exception):
    """Claude n'a pas pu analyser le message (réseau, refus, réponse inutilisable)."""


# Prompt système figé : aucune donnée variable, pour rester identique d'un appel à l'autre.
PROMPT_SYSTEME = """Tu analyses les messages WhatsApp reçus par PharmaSûr, un service sénégalais qui indique seulement dans quelles pharmacies partenaires un médicament est disponible. PharmaSûr ne vend rien, ne conseille rien et ne propose jamais un médicament à la place d'un autre.

Le message vient d'une personne qui cherche des médicaments. Il est écrit en français, parfois avec des mots en wolof, des fautes ou des abréviations. Il peut aussi être la transcription automatique d'un vocal, avec des erreurs de reconnaissance.

Réponds uniquement avec le JSON demandé :

1. "categorie", une seule valeur :
   - "urgence" : la personne décrit une urgence médicale en cours (malaise grave, perte de connaissance, difficulté à respirer, saignement important, convulsions, intoxication ou médicaments avalés par erreur, douleur très forte soudaine). En cas de doute sur une urgence, choisis "urgence".
   - "recherche" : la personne cherche au moins un médicament, même au milieu d'une salutation (« Bonjour, je cherche du Doliprane »). Un message court qui ne contient qu'un ou quelques noms de produits est une recherche, même si tu ne connais pas ces produits (« Mag 2 », « Richifer », « mag 2 svp ») : beaucoup de médicaments vendus au Sénégal te sont inconnus. Entre "autre" et "recherche", choisis "recherche".
   - "salutation" : seulement une salutation ou une prise de contact, sans médicament (« Bonjour », « Salam », « Na nga def »).
   - "hors_sujet" : toute autre demande que trouver un médicament : conseil de santé, posologie, prix, commande ou livraison, question sur un médecin, conversation.
   - "autre" : message incompréhensible ou vide de sens.

2. "salue" : true si le message contient une salutation, sinon false.

3. "medicaments" : la liste des médicaments cherchés, une entrée par médicament, dans l'ordre du message. Liste vide si la catégorie n'est pas "recherche".
   - Recopie chaque médicament tel que la personne l'a donné : nom commercial ou principe actif, puis le dosage et la forme seulement s'ils sont dits (« Doliprane 1000 comprimés », « amoxicilline sirop », « Smecta »).
   - Corrige seulement une faute d'orthographe évidente sur le même nom (« dolipran » devient « Doliprane », « amoxiciline » devient « amoxicilline »).
   - Ne remplace jamais un nom par un autre : pas de marque à la place d'un principe actif, pas de principe actif à la place d'une marque, pas d'équivalent.
   - N'ajoute jamais de médicament, de dosage ou de forme que la personne n'a pas dits.
   - Laisse de côté les mots qui ne sont pas des médicaments (« je cherche », « pour mon fils », « s'il vous plaît »).
   - Dans la transcription d'un vocal, souvent en wolof, les noms de médicaments sont déformés par la reconnaissance (« dolibaran », « amoksisilin sirob ») : rétablis le nom quand il est clairement reconnaissable, et laisse de côté un mot dont tu n'es pas sûr qu'il soit un médicament. La personne vérifie ensuite la liste."""

def _nom_seul(libelle: str) -> str:
    """Le nom d'un produit, sans dosage ni forme (« Mag 2 100 mg comprimés » donne « Mag 2 »),
    pour que la liste aide à reconnaître un nom sans pousser à ajouter un dosage (D27)."""
    nom = re.sub(r"\s+\d+([.,]\d+)?\s*(mg|g|ml|%|µg)(\W.*)?$", "", libelle, flags=re.IGNORECASE)
    return re.sub(r"(\s+(comprimés?|gélules?|sirop|effervescents?))+$", "", nom, flags=re.IGNORECASE).strip()


def _noms_connus() -> str:
    """Les produits des catalogues simulés, pour aider à reconnaître un nom mal écrit ou mal lu.

    Pris dans les données fixes (et non dans la base) pour que le prompt reste identique
    d'un appel à l'autre (cache).
    """
    from .db import PHARMACIES_SIMULEES

    # L'UPSA-C est la solution de Baobab pour la vitamine C de l'ordonnance de test : il ne
    # figure pas ici, pour que la lecture ne le substitue jamais au nom prescrit (D11).
    noms = sorted({_nom_seul(libelle) for p in PHARMACIES_SIMULEES for libelle in p["catalogue"] if not libelle.startswith("UPSA")})
    return chr(10).join(f"- {nom}" for nom in noms)


NOMS_CONNUS = """

Produits connus de PharmaSûr (catalogues des pharmacies partenaires) :
""" + _noms_connus() + """

Si un nom écrit, lu ou entendu ressemble clairement à l'un de ces produits (une ou deux lettres de différence, une espace ou un trait d'union en plus ou en moins, comme « Richifen » pour « Richifer » ou « Mag2 » pour « Mag 2 »), écris-le comme dans cette liste, sans y ajouter le dosage ni la forme s'ils n'ont pas été donnés. Ne choisis jamais dans cette liste un produit différent : un autre nom, même au même principe actif, reste un autre médicament. Un médicament absent de cette liste reste un médicament valide : recopie-le tel quel."""

PROMPT_SYSTEME = PROMPT_SYSTEME + NOMS_CONNUS


# Ajouté devant une transcription de vocal (parcours 7), dans le message et non dans le
# prompt système, pour garder celui-ci identique d'un appel à l'autre (cache).
INTRO_TRANSCRIPTION = "Transcription automatique d'un vocal (souvent en wolof, avec des erreurs de reconnaissance) :\n"

SCHEMA = {
    "type": "object",
    "properties": {
        "categorie": {"type": "string", "enum": [c.value for c in Categorie]},
        "salue": {"type": "boolean"},
        "medicaments": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["categorie", "salue", "medicaments"],
    "additionalProperties": False,
}

# Repli automatique en cas de refus, seulement pour les modèles qui le permettent.
MODELES_AVEC_REPLI = {"claude-opus-5-5", "claude-sonnet-5-5"}
BETA_REPLI = "server-side-fallback-2026-07-01"


def appeler_claude(
    client: anthropic.Anthropic,
    modele: str,
    effort: str,
    max_tokens: int,
    prompt_systeme: str,
    contenu: str | list,
    schema: dict,
) -> dict:
    """Un appel à Claude avec sortie structurée. Renvoie le JSON décodé.

    Lève `EchecAnalyse` en cas d'erreur réseau ou d'API, de refus, de réponse tronquée
    ou de réponse inutilisable : le bot répond alors le menu « non compris » (D8).
    """
    parametres = dict(
        model=modele,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": prompt_systeme, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": contenu}],
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
    )
    try:
        if modele in MODELES_AVEC_REPLI:
            reponse = client.beta.messages.create(betas=[BETA_REPLI], fallbacks="default", **parametres)
        else:
            reponse = client.messages.create(**parametres)
    except anthropic.RateLimitError as e:
        raise EchecAnalyse("limite de débit atteinte") from e
    except anthropic.APIStatusError as e:
        raise EchecAnalyse(f"erreur de l'API ({e.status_code})") from e
    except anthropic.APIConnectionError as e:
        raise EchecAnalyse("connexion impossible") from e

    if reponse.stop_reason == "refusal":
        raise EchecAnalyse("refus du modèle")
    if reponse.stop_reason == "max_tokens":
        raise EchecAnalyse("réponse tronquée")
    texte_json = next((b.text for b in reponse.content if b.type == "text"), None)
    if texte_json is None:
        raise EchecAnalyse("réponse sans texte")
    try:
        donnees = json.loads(texte_json)
    except ValueError as e:
        raise EchecAnalyse("réponse illisible") from e
    if not isinstance(donnees, dict):
        raise EchecAnalyse("réponse illisible")
    return donnees


class AnalyseurClaude:
    def __init__(self, client: anthropic.Anthropic, modele: str, effort: str = "low"):
        self.client = client
        self.modele = modele
        self.effort = effort

    def analyser(self, texte: str, transcription: bool = False) -> AnalyseMessage:
        contenu = INTRO_TRANSCRIPTION + texte if transcription else texte
        donnees = appeler_claude(self.client, self.modele, self.effort, 2048, PROMPT_SYSTEME, contenu, SCHEMA)
        try:
            categorie = Categorie(donnees["categorie"])
            medicaments = tuple(m.strip() for m in donnees["medicaments"] if m and m.strip())
            return AnalyseMessage(categorie, bool(donnees["salue"]), medicaments)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise EchecAnalyse("réponse illisible") from e


# --- Lecture des photos d'ordonnance ou de boîte (parcours 6, D12, D13, D21, D22) ---


class Lisibilite(StrEnum):
    LISIBLE = "lisible"  # tous les médicaments visibles sont lus
    PARTIELLE = "partielle"  # au moins un lu, au moins un illisible (D21)
    ILLISIBLE = "illisible"  # aucun médicament lu : floue, trop loin, pas une ordonnance ni une boîte


@dataclass(frozen=True)
class LecturePhoto:
    lisibilite: Lisibilite
    medicaments: tuple[str, ...]  # tels qu'écrits sur la photo
    non_lus: int  # médicaments présents mais illisibles


# Prompt système figé : la photo et la légende arrivent dans le message, jamais ici.
PROMPT_PHOTO = """Tu lis les photos envoyées à PharmaSûr, un service sénégalais qui indique seulement dans quelles pharmacies partenaires un médicament est disponible. PharmaSûr ne vend rien, ne conseille rien et ne propose jamais un médicament à la place d'un autre.

La photo montre une ordonnance (souvent écrite à la main, parfois mal cadrée ou peu éclairée) ou une boîte de médicament. Ton seul travail : relever les médicaments, pour que la personne vérifie la liste avant la recherche.

Réponds uniquement avec le JSON demandé :

1. "medicaments" : un élément par médicament, dans l'ordre de la photo.
   - Recopie le nom tel qu'il est écrit (nom commercial ou principe actif), puis le dosage et la forme seulement s'ils sont écrits (« Amoxicilline 250 mg/5 ml sirop », « Doliprane 1000 mg comprimés », « Smecta »).
   - Sur une boîte, relève le nom du médicament et son dosage, pas le laboratoire.
   - Corrige seulement une faute évidente d'écriture sur le même nom. Ne remplace jamais un nom par un autre : pas de marque à la place d'un principe actif, pas de principe actif à la place d'une marque, pas d'équivalent.
   - N'invente rien : si un nom n'est pas lisible avec certitude, ne le devine pas, compte-le dans "non_lus".
   - Ne recopie jamais rien d'autre : ni le nom du patient, ni celui du médecin, ni l'adresse, ni la date, ni un diagnostic ou une maladie, ni la posologie, la durée ou la quantité.

2. "non_lus" : le nombre de médicaments présents sur la photo mais illisibles. 0 si tout est lu.

3. "lisibilite" :
   - "lisible" : au moins un médicament lu et aucun illisible ;
   - "partielle" : au moins un médicament lu et au moins un illisible ;
   - "illisible" : aucun médicament lu (photo floue, trop sombre, trop loin, ou qui ne montre ni ordonnance ni boîte de médicament). La liste est alors vide.

Si la personne a écrit une légende avec la photo, elle est donnée après l'image. Ajoute à la liste les médicaments qu'elle y nomme, avec les mêmes règles, et ignore le reste de la légende."""

PROMPT_PHOTO = PROMPT_PHOTO + NOMS_CONNUS

SCHEMA_PHOTO = {
    "type": "object",
    "properties": {
        "lisibilite": {"type": "string", "enum": [l.value for l in Lisibilite]},
        "medicaments": {"type": "array", "items": {"type": "string"}},
        "non_lus": {"type": "integer"},
    },
    "required": ["lisibilite", "medicaments", "non_lus"],
    "additionalProperties": False,
}

TAILLE_IMAGE_MAX = 5 * 1024 * 1024  # limite de l'API pour une image


def type_image(contenu: bytes) -> str | None:
    """Type MIME d'après les premiers octets (WhatsApp envoie surtout du JPEG)."""
    if contenu.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if contenu.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if contenu[:4] == b"RIFF" and contenu[8:12] == b"WEBP":
        return "image/webp"
    if contenu[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    return None


class LecteurPhoto:
    def __init__(self, client: anthropic.Anthropic, modele: str, effort: str = "medium"):
        self.client = client
        self.modele = modele
        self.effort = effort

    def lire(self, image: bytes, legende: str | None = None) -> LecturePhoto:
        """Lit les médicaments sur la photo. L'image n'est ni écrite sur disque ni gardée (D22)."""
        media_type = type_image(image)
        if media_type is None:
            raise EchecAnalyse("format d'image inconnu")
        if len(image) > TAILLE_IMAGE_MAX:
            raise EchecAnalyse("image trop lourde")
        contenu: list[dict] = [
            {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": base64.b64encode(image).decode()},
            }
        ]
        if legende and legende.strip():
            contenu.append({"type": "text", "text": "Légende de la personne : " + legende.strip()})
        else:
            contenu.append({"type": "text", "text": "Pas de légende."})
        donnees = appeler_claude(self.client, self.modele, self.effort, 8000, PROMPT_PHOTO, contenu, SCHEMA_PHOTO)
        try:
            medicaments = tuple(m.strip() for m in donnees["medicaments"] if m and m.strip())
            non_lus = max(0, int(donnees["non_lus"]))
            lisibilite = Lisibilite(donnees["lisibilite"])
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            raise EchecAnalyse("réponse illisible") from e
        # La liste fait foi : sans aucun nom lu, la photo est illisible (D21).
        if not medicaments:
            lisibilite = Lisibilite.ILLISIBLE
        elif non_lus:
            lisibilite = Lisibilite.PARTIELLE
        elif lisibilite is Lisibilite.ILLISIBLE:
            lisibilite = Lisibilite.LISIBLE
        return LecturePhoto(lisibilite, medicaments, non_lus)


def creer_client(config: Config) -> anthropic.Anthropic | None:
    if not config.anthropic_api_key:
        return None
    return anthropic.Anthropic(api_key=config.anthropic_api_key, timeout=60.0, max_retries=2)


def creer_analyseur(config: Config, client: anthropic.Anthropic | None = None) -> AnalyseurClaude | None:
    """None sans clé Anthropic : le bot reprend alors le découpage provisoire."""
    client = client or creer_client(config)
    if client is None:
        return None
    return AnalyseurClaude(client, config.modeles.extraction)


def creer_lecteur(config: Config, client: anthropic.Anthropic | None = None) -> LecteurPhoto | None:
    """None sans clé Anthropic : une photo reçoit alors la réponse provisoire."""
    client = client or creer_client(config)
    if client is None:
        return None
    return LecteurPhoto(client, config.modeles.photo)

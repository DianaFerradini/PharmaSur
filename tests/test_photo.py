"""Parcours 6 : recherche par photo (D12, D13, D21, D22), sans appel réseau."""

import json
import sqlite3
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from pharmasur import db
from pharmasur.bot import CHOIX_LECTURE_CORRIGER, CHOIX_LECTURE_OUI, traiter_message
from pharmasur.ia import AnalyseurClaude, EchecAnalyse, LecteurPhoto, Lisibilite, type_image
from pharmasur.whatsapp import MessageRecu, TypeMessage

from test_app import NUMERO_BAOBAB, NUMERO_FATOU, FournisseurFactice

JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
REQUETE = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")

ORDONNANCE = ["Amoxicilline 250 mg/5 ml sirop", "Doliprane 2,4 % sirop", "Smekta"]


def lecture(medicaments, lisibilite="lisible", non_lus=0, stop_reason="end_turn"):
    texte = json.dumps({"lisibilite": lisibilite, "medicaments": list(medicaments), "non_lus": non_lus})
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=texte)])


def analyse(categorie, medicaments=(), salue=False):
    texte = json.dumps({"categorie": categorie, "salue": salue, "medicaments": list(medicaments)})
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=texte)])


class _Messages:
    def __init__(self, client):
        self.client = client

    def create(self, **parametres):
        self.client.appels.append(parametres)
        reponse = self.client.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


class ClientSequence:
    """Imite anthropic.Anthropic : renvoie les réponses prévues, dans l'ordre."""

    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.appels = []
        self.messages = _Messages(self)
        self.beta = SimpleNamespace(messages=_Messages(self))


class FournisseurPhoto(FournisseurFactice):
    def __init__(self, image=JPEG):
        super().__init__()
        self.image = image

    def telecharger_media(self, media_id):
        if isinstance(self.image, Exception):
            raise self.image
        return self.image


@pytest.fixture
def chemin_db(tmp_path):
    chemin = str(tmp_path / "test.db")
    db.initialiser(chemin, NUMERO_BAOBAB)
    return chemin


class Conversation:
    """Fatou parle au bot ; on garde ce que le bot répond."""

    def __init__(self, chemin_db, *reponses_claude, image=JPEG):
        self.chemin_db = chemin_db
        self.client = ClientSequence(*reponses_claude)
        self.analyseur = AnalyseurClaude(self.client, "claude-opus-5-5")
        self.lecteur = LecteurPhoto(self.client, "claude-opus-5-5")
        self.fournisseur = FournisseurPhoto(image)

    def _envoyer(self, message):
        self.fournisseur.envois.clear()
        traiter_message(message, self.fournisseur, self.chemin_db, self.analyseur, self.lecteur)
        return list(self.fournisseur.envois)

    def photo(self, legende=None):
        return self._envoyer(MessageRecu(NUMERO_FATOU, TypeMessage.IMAGE, texte=legende, media_id="MEDIA1"))

    def touche(self, choix_id):
        return self._envoyer(MessageRecu(NUMERO_FATOU, TypeMessage.CHOIX, choix_id=choix_id))

    def ecrit(self, texte):
        return self._envoyer(MessageRecu(NUMERO_FATOU, TypeMessage.TEXTE, texte=texte))


def lecture_en_attente(chemin_db):
    connexion = db.connecter(chemin_db)
    try:
        return db.lire_lecture(connexion, NUMERO_FATOU)
    finally:
        connexion.close()


def corrections(chemin_db):
    connexion = sqlite3.connect(chemin_db)
    try:
        return connexion.execute("SELECT lu, corrige FROM correction_lecture").fetchall()
    finally:
        connexion.close()


# --- Lecture ---


def test_parametres_de_la_lecture():
    client = ClientSequence(lecture(["Smecta"]))
    resultat = LecteurPhoto(client, "claude-opus-5-5").lire(JPEG, "pour mon fils")
    assert resultat.lisibilite is Lisibilite.LISIBLE and resultat.medicaments == ("Smecta",)
    appel = client.appels[0]
    assert appel["model"] == "claude-opus-5-5"
    assert appel["fallbacks"] == "default" and appel["betas"] == ["server-side-fallback-2026-07-01"]
    assert appel["output_config"]["effort"] == "medium"
    assert appel["output_config"]["format"]["type"] == "json_schema"
    image, legende = appel["messages"][0]["content"]
    assert image["type"] == "image" and image["source"]["media_type"] == "image/jpeg"
    assert legende["text"] == "Légende de la personne : pour mon fils"
    assert "temperature" not in appel and "thinking" not in appel


def test_type_image_et_format_inconnu():
    assert type_image(JPEG) == "image/jpeg"
    assert type_image(b"\x89PNG\r\n\x1a\n...") == "image/png"
    with pytest.raises(EchecAnalyse):
        LecteurPhoto(ClientSequence(), "claude-opus-5-5").lire(b"pas une image")


def test_la_liste_fait_foi_sur_la_lisibilite():
    lire = lambda reponse: LecteurPhoto(ClientSequence(reponse), "claude-haiku-5-5").lire(JPEG)
    assert lire(lecture([], "lisible")).lisibilite is Lisibilite.ILLISIBLE
    assert lire(lecture(["Smecta"], "lisible", non_lus=1)).lisibilite is Lisibilite.PARTIELLE


# --- Parcours 6 ---


def test_photo_lisible_confirmation_puis_resultats(chemin_db):
    conversation = Conversation(chemin_db, lecture(["Amoxicilline 250 mg/5 ml sirop", "Doliprane 2,4 % sirop", "Smecta"]))
    envois = conversation.photo()
    assert len(envois) == 1
    _, texte, options = envois[0]
    assert texte == (
        "J'ai lu sur votre photo :\n"
        "1. Amoxicilline 250 mg/5 ml sirop\n"
        "2. Doliprane 2,4 % sirop\n"
        "3. Smecta\n"
        "C'est bien ça ?"
    )
    assert [o.id for o in options] == [CHOIX_LECTURE_OUI, CHOIX_LECTURE_CORRIGER]
    assert lecture_en_attente(chemin_db) is not None

    textes = [envoi[1] for envoi in conversation.touche(CHOIX_LECTURE_OUI)]
    # Premier contact : accueil court avant les résultats (D8).
    assert textes[0].startswith("Bonjour 👋 PharmaSûr vous dit")
    assert "1. Pharmacie Baobab — 2 sur 3" in textes[1]
    assert "Pharmacie Liberté — 1 sur 3" in textes[1]
    assert "Teranga" not in textes[1]  # la forme « sirop » est précisée (D27)
    assert textes[2] == "🚫 Smecta : introuvable aujourd'hui dans les pharmacies partenaires."
    # D22 : le lien entre le numéro et les noms lus est effacé dès la confirmation.
    assert lecture_en_attente(chemin_db) is None
    assert corrections(chemin_db) == []


def test_correction_gardee_sans_numero(chemin_db):
    conversation = Conversation(chemin_db, lecture(ORDONNANCE), analyse("recherche", ["Smecta"]))
    conversation.photo()
    assert conversation.touche(CHOIX_LECTURE_CORRIGER) == [(NUMERO_FATOU, "Écrivez ou dites le bon nom.")]

    _, texte, _ = conversation.ecrit("Smecta")[0]
    assert texte == (
        "Voici votre liste corrigée :\n"
        "1. Amoxicilline 250 mg/5 ml sirop\n"
        "2. Doliprane 2,4 % sirop\n"
        "3. Smecta\n"
        "C'est bien ça ?"
    )
    assert corrections(chemin_db) == [("Smekta", "Smecta")]
    colonnes = [c[1] for c in sqlite3.connect(chemin_db).execute("PRAGMA table_info(correction_lecture)")]
    assert colonnes == ["id", "lu", "corrige", "date"]  # ni image ni numéro (D22)

    textes = [envoi[1] for envoi in conversation.touche(CHOIX_LECTURE_OUI)]
    assert any("Smecta : introuvable" in t for t in textes)
    assert lecture_en_attente(chemin_db) is None


def test_correction_d_un_nom_tres_different(chemin_db):
    # Sans médicament non lu, la correction remplace forcément un nom lu.
    conversation = Conversation(chemin_db, lecture(["Spasfon"]), analyse("recherche", ["Doliprane"]))
    conversation.photo()
    conversation.touche(CHOIX_LECTURE_CORRIGER)
    _, texte, _ = conversation.ecrit("non c'est du Doliprane")[0]
    assert "1. Doliprane\n" in texte and "Spasfon" not in texte
    assert corrections(chemin_db) == [("Spasfon", "Doliprane")]


def test_photo_illisible(chemin_db):
    conversation = Conversation(chemin_db, lecture([], "illisible"))
    assert conversation.photo() == [
        (
            NUMERO_FATOU,
            "Je n'arrive pas à lire la photo.\n"
            "📸 Reprenez-la avec plus de lumière, de plus près, bien à plat,\n"
            "✍️🎤 ou écrivez ou dites le nom du médicament.",
        )
    ]
    assert lecture_en_attente(chemin_db) is None


def test_lecture_partielle_puis_nom_ecrit(chemin_db):
    conversation = Conversation(
        chemin_db,
        lecture(["Doliprane 2,4 % sirop"], "partielle", non_lus=1),
        analyse("recherche", ["Smecta"]),
    )
    _, texte, _ = conversation.photo()[0]
    assert texte == (
        "J'ai lu sur votre photo :\n"
        "1. Doliprane 2,4 % sirop\n"
        "⚠️ Un médicament n'a pas pu être lu : reprenez la photo, ou écrivez ou dites son nom.\n"
        "C'est bien ça ?"
    )
    # La personne écrit directement le nom manquant, sans toucher ✏️.
    _, texte, _ = conversation.ecrit("Smecta")[0]
    assert texte == "Voici votre liste corrigée :\n1. Doliprane 2,4 % sirop\n2. Smecta\nC'est bien ça ?"
    assert corrections(chemin_db) == []  # un ajout, pas une correction


def test_echecs_donnent_non_compris(chemin_db):
    erreur = anthropic.APIConnectionError(request=REQUETE)
    for conversation in (
        Conversation(chemin_db, erreur),
        Conversation(chemin_db, lecture(["Smecta"], stop_reason="refusal")),
        Conversation(chemin_db, image=RuntimeError("Meta indisponible")),
    ):
        envois = conversation.photo()
        assert len(envois) == 1 and envois[0][1].startswith("Je n'ai pas compris 🙏")
        assert lecture_en_attente(chemin_db) is None


def test_bouton_sans_lecture_en_attente(chemin_db):
    envois = Conversation(chemin_db).touche(CHOIX_LECTURE_OUI)
    assert len(envois) == 1 and envois[0][1].startswith("Je n'ai pas compris 🙏")


def test_un_autre_message_abandonne_la_photo(chemin_db):
    conversation = Conversation(chemin_db, lecture(["Smecta"]), analyse("recherche", ["Doliprane"]))
    conversation.photo()
    textes = [envoi[1] for envoi in conversation.ecrit("Doliprane")]
    assert textes[0].startswith("Vos médicaments : Doliprane")
    assert lecture_en_attente(chemin_db) is None


def test_photo_sans_lecteur_reponse_provisoire(chemin_db):
    fournisseur = FournisseurPhoto()
    analyseur = AnalyseurClaude(ClientSequence(), "claude-opus-5-5")
    traiter_message(MessageRecu(NUMERO_FATOU, TypeMessage.IMAGE, media_id="M"), fournisseur, chemin_db, analyseur)
    assert fournisseur.envois[0][1].startswith("📸 Photo bien reçue")


def test_la_table_est_ajoutee_a_une_base_existante(chemin_db):
    connexion = sqlite3.connect(chemin_db)
    connexion.execute("DROP TABLE lecture_en_attente")
    connexion.commit()
    connexion.close()
    assert db.initialiser(chemin_db, NUMERO_BAOBAB) is False
    assert lecture_en_attente(chemin_db) is None  # la table existe à nouveau

"""Parcours 1 avec Claude : analyse des messages et réponses (D8, D9), sans appel réseau."""

import json
from types import SimpleNamespace

import anthropic
import httpx2
import pytest

from pharmasur import db
from pharmasur.bot import traiter_message
from pharmasur.config import Config
from pharmasur.ia import AnalyseurClaude, Categorie, EchecAnalyse, creer_analyseur
from pharmasur.whatsapp import MessageRecu, TypeMessage

from test_app import NUMERO_BAOBAB, NUMERO_FATOU, FournisseurFactice

REQUETE = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")


def reponse(categorie, medicaments=(), salue=False, stop_reason="end_turn"):
    texte = json.dumps({"categorie": categorie, "salue": salue, "medicaments": list(medicaments)})
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=texte)])


class _Messages:
    def __init__(self, client):
        self.client = client

    def create(self, **parametres):
        self.client.appels.append(parametres)
        if isinstance(self.client.reponse, Exception):
            raise self.client.reponse
        return self.client.reponse


class ClientFactice:
    """Imite anthropic.Anthropic : messages.create et beta.messages.create."""

    def __init__(self, reponse):
        self.reponse = reponse
        self.appels = []
        self.messages = _Messages(self)
        self.beta = SimpleNamespace(messages=_Messages(self))


@pytest.fixture
def chemin_db(tmp_path):
    chemin = str(tmp_path / "test.db")
    db.initialiser(chemin, NUMERO_BAOBAB)
    return chemin


def envoyer(chemin_db, texte, reponse_claude, modele="claude-opus-5-5"):
    fournisseur = FournisseurFactice()
    client = ClientFactice(reponse_claude)
    analyseur = AnalyseurClaude(client, modele)
    traiter_message(MessageRecu(NUMERO_FATOU, TypeMessage.TEXTE, texte=texte), fournisseur, chemin_db, analyseur)
    return [envoi[1] for envoi in fournisseur.envois], client


# --- Analyse ---


def test_parametres_de_l_appel_opus_avec_repli():
    client = ClientFactice(reponse("salutation", salue=True))
    analyse = AnalyseurClaude(client, "claude-opus-5-5").analyser("Bonjour")
    assert analyse.categorie is Categorie.SALUTATION and analyse.salue
    appel = client.appels[0]
    assert appel["model"] == "claude-opus-5-5"
    assert appel["fallbacks"] == "default"
    assert appel["betas"] == ["server-side-fallback-2026-07-01"]
    assert appel["output_config"]["effort"] == "low"
    assert appel["output_config"]["format"]["type"] == "json_schema"
    assert "temperature" not in appel and "thinking" not in appel


def test_haiku_sans_repli_serveur():
    client = ClientFactice(reponse("autre"))
    AnalyseurClaude(client, "claude-haiku-5-5").analyser("???")
    assert "fallbacks" not in client.appels[0] and "betas" not in client.appels[0]


def test_refus_et_reponse_tronquee_sont_des_echecs():
    for stop in ("refusal", "max_tokens"):
        with pytest.raises(EchecAnalyse):
            AnalyseurClaude(ClientFactice(reponse("recherche", ["Doliprane"], stop_reason=stop)), "claude-opus-5-5").analyser("x")


def test_reponse_illisible_est_un_echec():
    illisible = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="{pas du json")])
    with pytest.raises(EchecAnalyse):
        AnalyseurClaude(ClientFactice(illisible), "claude-opus-5-5").analyser("x")


def test_sans_cle_pas_d_analyseur(tmp_path):
    assert creer_analyseur(Config()) is None
    assert creer_analyseur(Config(anthropic_api_key="sk-test")) is not None


# --- Réponses du bot ---


def test_recherche_au_premier_contact_accueil_court_puis_resultats(chemin_db):
    textes, _ = envoyer(
        chemin_db,
        "Bonjour, je cherche amoxiciline sirop et dolipran",
        reponse("recherche", ["amoxicilline sirop", "Doliprane"], salue=True),
    )
    assert textes[0].startswith("Bonjour 👋 PharmaSûr vous dit")
    assert textes[1].startswith("Vos médicaments : Amoxicilline sirop, Doliprane")
    assert "1. Pharmacie Baobab — 2 sur 2" in textes[1]
    assert len(textes) == 2


def test_recherche_d_un_numero_deja_venu_salue_puis_resultats(chemin_db):
    envoyer(chemin_db, "Bonjour", reponse("salutation", salue=True))
    textes, _ = envoyer(chemin_db, "Salam, Doliprane svp", reponse("recherche", ["Doliprane"], salue=True))
    assert textes[0] == "Bonjour 👋"
    assert textes[1].startswith("Vos médicaments : Doliprane")
    textes, _ = envoyer(chemin_db, "Smecta", reponse("recherche", ["Smecta"]))
    assert textes == ["🚫 Smecta : introuvable aujourd'hui dans les pharmacies partenaires.\nVoulez-vous qu'on demande aux pharmacies si l'une d'elles a une solution ?"]


def test_salutation_seule(chemin_db):
    textes, _ = envoyer(chemin_db, "Bonjour", reponse("salutation", salue=True))
    assert textes == [
        "Bonjour 👋 Je suis PharmaSûr. Je vous dis quelles pharmacies ont vos médicaments.\n"
        "Envoyez-moi le nom de vos médicaments, une photo de l'ordonnance ou de la boîte, ou un vocal.\n"
        "Rien ne s'achète ici : vous achetez en pharmacie, avec votre ordonnance."
    ]
    textes, _ = envoyer(chemin_db, "Bonjour", reponse("salutation", salue=True))
    assert textes == ["Bonjour 👋 Envoyez-moi le nom de vos médicaments, une photo de l'ordonnance ou de la boîte, ou un vocal."]


def test_hors_sujet(chemin_db):
    envoyer(chemin_db, "Bonjour", reponse("salutation", salue=True))
    textes, _ = envoyer(chemin_db, "Combien de Doliprane par jour ?", reponse("hors_sujet"))
    assert textes == ["PharmaSûr indique seulement où trouver vos médicaments. Pour toute autre question, demandez à un pharmacien."]


def test_urgence_meme_au_premier_contact(chemin_db):
    textes, _ = envoyer(chemin_db, "mon fils a avalé des comprimés", reponse("urgence", ["comprimés"]))
    assert textes == ["🚨 Urgence : appelez le SAMU au 1515 ou les sapeurs-pompiers au 18."]


def test_incomprehensible(chemin_db):
    envoyer(chemin_db, "Bonjour", reponse("salutation", salue=True))
    textes, _ = envoyer(chemin_db, "zzkq", reponse("autre"))
    assert textes[0].startswith("Je n'ai pas compris 🙏")


def test_echec_de_l_api_donne_non_compris(chemin_db):
    for erreur in (
        anthropic.APIConnectionError(request=REQUETE),
        anthropic.RateLimitError("trop", response=httpx2.Response(429, request=REQUETE), body=None),
        anthropic.InternalServerError("panne", response=httpx2.Response(500, request=REQUETE), body=None),
    ):
        textes, _ = envoyer(chemin_db, "Doliprane", erreur)
        assert textes == [textes[0]] and textes[0].startswith("Je n'ai pas compris 🙏")


def test_refus_donne_non_compris(chemin_db):
    textes, _ = envoyer(chemin_db, "Doliprane", reponse("recherche", ["Doliprane"], stop_reason="refusal"))
    assert len(textes) == 1 and textes[0].startswith("Je n'ai pas compris 🙏")


def test_choix_du_menu_sans_appel_a_claude(chemin_db):
    textes, client = envoyer(chemin_db, "2", reponse("autre"))
    assert textes[0].startswith("Bonjour 👋 Je suis PharmaSûr")
    textes, client = envoyer(chemin_db, "1", reponse("autre"))
    assert textes == ["Envoyez-moi le nom de vos médicaments, une photo de l'ordonnance ou de la boîte, ou un vocal."]
    assert client.appels == []


def test_repli_sans_cle_decoupe_le_texte(chemin_db):
    fournisseur = FournisseurFactice()
    traiter_message(MessageRecu(NUMERO_FATOU, TypeMessage.TEXTE, texte="doliprane, smecta"), fournisseur, chemin_db)
    textes = [envoi[1] for envoi in fournisseur.envois]
    assert textes[0].startswith("Bonjour 👋 PharmaSûr vous dit")
    assert textes[1].startswith("Vos médicaments : Doliprane, Smecta")

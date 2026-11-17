"""Webhook (vérification, signature), base simulée et routage D4."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from pharmasur import db
from pharmasur.app import creer_app
from pharmasur.bot import traiter_message
from pharmasur.config import Config
from pharmasur.whatsapp import Fournisseur, MessageRecu, TypeMessage
from pharmasur.whatsapp.meta import FournisseurMeta, signature_attendue

NUMERO_BAOBAB = "+221 77 000 00 99"
NUMERO_FATOU = "221771234567"


@pytest.fixture
def config(tmp_path):
    return Config(
        whatsapp_verify_token="verif",
        whatsapp_app_secret="secret",
        numero_pharmacie_baobab=NUMERO_BAOBAB,
        db_path=str(tmp_path / "test.db"),
    )


class FournisseurFactice(Fournisseur):
    """Garde les messages envoyés au lieu de les envoyer."""

    def __init__(self):
        self.envois = []

    def verifier_abonnement(self, parametres):
        return None

    def verifier_requete(self, corps, entetes):
        return True

    def lire_messages(self, corps, entetes):
        return []

    def envoyer_texte(self, destinataire, texte):
        self.envois.append((destinataire, texte))

    def envoyer_choix(self, destinataire, texte, options):
        self.envois.append((destinataire, texte, options))

    def envoyer_image(self, destinataire, url, legende=None):
        self.envois.append((destinataire, url))

    def envoyer_audio(self, destinataire, chemin_fichier):
        self.envois.append((destinataire, chemin_fichier))

    def telecharger_media(self, media_id):
        return b""


# --- Webhook ---


@pytest.fixture
def client_et_recus(config):
    recus = []
    fournisseur = FournisseurMeta("jeton", "123", config.whatsapp_verify_token, config.whatsapp_app_secret)
    app = creer_app(config, fournisseur, traitement=lambda message, f, chemin: recus.append(message))
    with TestClient(app) as client:
        yield client, recus


def test_sante(client_et_recus):
    client, _ = client_et_recus
    assert client.get("/").json() == {"statut": "ok"}


def test_verification_du_webhook(client_et_recus):
    client, _ = client_et_recus
    ok = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verif", "hub.challenge": "1158201444"})
    assert ok.status_code == 200 and ok.text == "1158201444"
    refuse = client.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "faux", "hub.challenge": "1"})
    assert refuse.status_code == 403


def corps_texte(texte):
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "1",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "123"},
                                "messages": [
                                    {"from": NUMERO_FATOU, "id": "wamid.1", "timestamp": "1", "type": "text", "text": {"body": texte}}
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    ).encode()


def test_message_signe_accepte_et_traite(client_et_recus):
    client, recus = client_et_recus
    corps = corps_texte("doliprane")
    reponse = client.post(
        "/webhook", content=corps, headers={"X-Hub-Signature-256": signature_attendue("secret", corps)}
    )
    assert reponse.status_code == 200
    assert recus == [MessageRecu(NUMERO_FATOU, TypeMessage.TEXTE, texte="doliprane", id_message="wamid.1")]


def test_message_mal_signe_rejete(client_et_recus):
    client, recus = client_et_recus
    corps = corps_texte("doliprane")
    reponse = client.post("/webhook", content=corps, headers={"X-Hub-Signature-256": "sha256=faux"})
    assert reponse.status_code == 401
    assert recus == []


# --- Base simulée (D35, D15) ---


def test_base_creee_avec_les_donnees_simulees(config):
    assert db.initialiser(config.db_path, NUMERO_BAOBAB, graine=0)
    assert not db.initialiser(config.db_path, NUMERO_BAOBAB)  # déjà là : rien n'est refait
    connexion = db.connecter(config.db_path)
    noms = [p.nom for p in db.charger_pharmacies(connexion)]
    assert noms == ["Pharmacie Baobab", "Pharmacie Liberté", "Pharmacie Teranga", "Pharmacie Jamm"]
    assert db.pharmacie_par_numero(connexion, "221770000099")["nom"] == "Pharmacie Baobab"
    assert connexion.execute("SELECT COUNT(*) FROM recherche").fetchone()[0] == 40
    smecta = connexion.execute(
        "SELECT COUNT(*) FROM recherche_medicament WHERE medicament = 'Smecta' AND introuvable = 1"
    ).fetchone()[0]
    assert smecta == 12


def colonnes(connexion: sqlite3.Connection, table: str) -> set[str]:
    return {ligne["name"] for ligne in connexion.execute(f"PRAGMA table_info({table})")}


def test_recherches_sans_lien_avec_le_numero(config):
    db.initialiser(config.db_path, NUMERO_BAOBAB)
    connexion = db.connecter(config.db_path)
    for table in ("recherche", "recherche_medicament", "recherche_pharmacie", "correction_lecture"):
        assert "numero" not in colonnes(connexion, table)


def test_remise_a_zero(config):
    db.initialiser(config.db_path, NUMERO_BAOBAB)
    connexion = db.connecter(config.db_path)
    db.enregistrer_premier_contact(connexion, NUMERO_FATOU)
    connexion.close()
    db.remettre_a_zero(config.db_path, NUMERO_BAOBAB)
    connexion = db.connecter(config.db_path)
    assert connexion.execute("SELECT COUNT(*) FROM premier_contact").fetchone()[0] == 0
    connexion.close()


# --- Routage D4 ---


def test_routage_personne_premier_contact_puis_resultats(config):
    db.initialiser(config.db_path, NUMERO_BAOBAB)
    fournisseur = FournisseurFactice()
    message = MessageRecu(NUMERO_FATOU, TypeMessage.TEXTE, texte="Bonjour, je cherche amoxicilline sirop et doliprane")
    traiter_message(message, fournisseur, config.db_path)
    textes = [envoi[1] for envoi in fournisseur.envois]
    assert textes[0].startswith("Bonjour 👋 PharmaSûr vous dit")  # accueil court
    assert textes[1].startswith("Vos médicaments : Amoxicilline sirop, Doliprane")
    assert "1. Pharmacie Baobab — 2 sur 2" in textes[1]

    # Deuxième message : plus d'accueil.
    fournisseur.envois.clear()
    traiter_message(MessageRecu(NUMERO_FATOU, TypeMessage.TEXTE, texte="smecta"), fournisseur, config.db_path)
    # D10 : la ligne 🚫 et la proposition de demande d'équivalent, avec ✅ / ❌.
    ((destinataire, texte, options),) = fournisseur.envois
    assert texte == "🚫 Smecta : introuvable aujourd'hui dans les pharmacies partenaires.\nVoulez-vous qu'on demande aux pharmacies si l'une d'elles a une solution ?"
    assert [o.libelle for o in options] == ["✅", "❌"]


def test_routage_pharmacie_reconnue_a_son_numero(config):
    db.initialiser(config.db_path, NUMERO_BAOBAB)
    fournisseur = FournisseurFactice()
    traiter_message(MessageRecu("221770000099", TypeMessage.TEXTE, texte="plus de doliprane 1000"), fournisseur, config.db_path)
    assert fournisseur.envois == [
        ("221770000099", "✅ Message reçu, Pharmacie Baobab. Les signalements de rupture arrivent très bientôt.")
    ]

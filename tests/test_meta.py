"""Fournisseur Meta : lecture des webhooks, signature, envoi (D29)."""

import json

import httpx

from pharmasur.whatsapp import Option, TypeMessage
from pharmasur.whatsapp.meta import FournisseurMeta, signature_attendue

SECRET = "secret-de-test"


def enveloppe(*messages, statuts=None):
    """Corps réaliste d'un webhook WhatsApp Cloud API."""
    valeur = {
        "messaging_product": "whatsapp",
        "metadata": {"display_phone_number": "15551234567", "phone_number_id": "123456789"},
        "contacts": [{"profile": {"name": "Fatou"}, "wa_id": "221771234567"}],
    }
    if messages:
        valeur["messages"] = list(messages)
    if statuts:
        valeur["statuses"] = statuts
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "987654321", "changes": [{"value": valeur, "field": "messages"}]}],
    }


def base(type_, **contenu):
    return {"from": "221771234567", "id": "wamid.ABC", "timestamp": "1763300000", "type": type_, **contenu}


def fournisseur(transport=None):
    client = httpx.Client(transport=transport) if transport else None
    return FournisseurMeta("jeton", "123456789", "verif", SECRET, client=client)


def lire(*messages, statuts=None):
    corps = json.dumps(enveloppe(*messages, statuts=statuts)).encode()
    return fournisseur().lire_messages(corps, {})


def test_message_texte():
    [m] = lire(base("text", text={"body": "amoxicilline sirop et doliprane"}))
    assert m.type is TypeMessage.TEXTE
    assert m.expediteur == "221771234567"
    assert m.texte == "amoxicilline sirop et doliprane"
    assert m.id_message == "wamid.ABC"


def test_message_image_avec_legende():
    [m] = lire(base("image", image={"id": "MEDIA1", "mime_type": "image/jpeg", "sha256": "x", "caption": "ordonnance"}))
    assert m.type is TypeMessage.IMAGE
    assert m.media_id == "MEDIA1"
    assert m.texte == "ordonnance"


def test_message_vocal():
    [m] = lire(base("audio", audio={"id": "MEDIA2", "mime_type": "audio/ogg; codecs=opus", "voice": True}))
    assert m.type is TypeMessage.AUDIO
    assert m.media_id == "MEDIA2"


def test_reponse_a_un_bouton():
    [m] = lire(base("interactive", interactive={"type": "button_reply", "button_reply": {"id": "oui", "title": "Oui"}}))
    assert m.type is TypeMessage.CHOIX
    assert m.choix_id == "oui"
    assert m.texte == "Oui"


def test_bouton_de_modele():
    [m] = lire(base("button", button={"payload": "solution", "text": "Oui, j'ai une solution"}))
    assert m.type is TypeMessage.CHOIX
    assert m.choix_id == "solution"


def test_type_non_gere():
    [m] = lire(base("sticker", sticker={"id": "S1"}))
    assert m.type is TypeMessage.AUTRE


def test_accuses_de_lecture_ignores():
    assert lire(statuts=[{"id": "wamid.X", "status": "read", "recipient_id": "221771234567"}]) == []


def test_corps_illisible():
    assert fournisseur().lire_messages(b"pas du json", {}) == []


# --- Signature et vérification du webhook ---


def test_signature_valide():
    corps = b'{"object":"whatsapp_business_account"}'
    assert fournisseur().verifier_requete(corps, {"x-hub-signature-256": signature_attendue(SECRET, corps)})


def test_signature_invalide_ou_absente():
    corps = b'{"object":"whatsapp_business_account"}'
    f = fournisseur()
    assert not f.verifier_requete(corps, {"x-hub-signature-256": signature_attendue("autre", corps)})
    assert not f.verifier_requete(corps, {})
    assert not f.verifier_requete(corps + b" ", {"x-hub-signature-256": signature_attendue(SECRET, corps)})


def test_verification_abonnement():
    f = fournisseur()
    assert f.verifier_abonnement({"hub.mode": "subscribe", "hub.verify_token": "verif", "hub.challenge": "42"}) == "42"
    assert f.verifier_abonnement({"hub.mode": "subscribe", "hub.verify_token": "faux", "hub.challenge": "42"}) is None


# --- Envoi ---


def capturer():
    requetes = []

    def gerer(requete: httpx.Request) -> httpx.Response:
        requetes.append(requete)
        return httpx.Response(200, json={"messages": [{"id": "wamid.OUT"}]})

    return requetes, httpx.MockTransport(gerer)


def test_envoi_texte():
    requetes, transport = capturer()
    fournisseur(transport).envoyer_texte("221771234567", "Bonjour")
    corps = json.loads(requetes[0].content)
    assert requetes[0].url == "https://graph.facebook.com/v25.0/123456789/messages"
    assert requetes[0].headers["authorization"] == "Bearer jeton"
    assert corps["to"] == "221771234567"
    assert corps["text"]["body"] == "Bonjour"


def test_envoi_choix_en_boutons():
    requetes, transport = capturer()
    fournisseur(transport).envoyer_choix(
        "221771234567", "Voulez-vous qu'on demande aux pharmacies ?", [Option("oui", "Oui"), Option("non", "Non")]
    )
    interactif = json.loads(requetes[0].content)["interactive"]
    assert interactif["type"] == "button"
    assert [b["reply"] for b in interactif["action"]["buttons"]] == [
        {"id": "oui", "title": "Oui"},
        {"id": "non", "title": "Non"},
    ]


def test_choix_limite_a_trois_options():
    _, transport = capturer()
    options = [Option(str(i), str(i)) for i in range(4)]
    try:
        fournisseur(transport).envoyer_choix("221771234567", "?", options)
    except ValueError:
        pass
    else:
        raise AssertionError("4 options auraient dû être refusées")


def test_telechargement_media():
    def gerer(requete: httpx.Request) -> httpx.Response:
        if requete.url.host == "graph.facebook.com":
            assert requete.url.path == "/v25.0/MEDIA1"
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?mid=MEDIA1"})
        return httpx.Response(200, content=b"octets-image")

    assert fournisseur(httpx.MockTransport(gerer)).telecharger_media("MEDIA1") == b"octets-image"

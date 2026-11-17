"""Parcours 7 : recherche par vocal en wolof (D13, D23, D24, D32, D37), sans appel réseau."""

import json
import logging
import os
from datetime import timedelta

import httpx
import pytest

from pharmasur import db, equivalent, textes
from pharmasur.bot import CHOIX_LECTURE_OUI, traiter_message
from pharmasur.ia import INTRO_TRANSCRIPTION, AnalyseurClaude
from pharmasur.transcription import EchecTranscription, TranscripteurElevenLabs
from pharmasur.vocaux import FICHIERS, AvecVocaux, BanqueVocaux, Vocal, vocal_pour
from pharmasur.whatsapp import MessageRecu, TypeMessage
from pharmasur.whatsapp.meta import FournisseurMeta

from test_app import NUMERO_BAOBAB, NUMERO_FATOU, FournisseurFactice
from test_photo import ClientSequence, analyse

BAOBAB = db.normaliser_numero(NUMERO_BAOBAB)
VOCAL_RECU = b"OggS" + b"\x00" * 32


@pytest.fixture
def chemin_db(tmp_path):
    chemin = str(tmp_path / "test.db")
    db.initialiser(chemin, NUMERO_BAOBAB)
    return chemin


@pytest.fixture
def dossier_vocaux(tmp_path):
    """Les 12 vocaux enregistrés (contenu factice)."""
    dossier = tmp_path / "vocaux"
    dossier.mkdir()
    for nom in FICHIERS.values():
        (dossier / nom).write_bytes(b"OggS-vocal")
    return dossier


class TranscripteurFactice:
    def __init__(self, *reponses):
        self.reponses = list(reponses)
        self.audios = []

    def transcrire(self, audio):
        self.audios.append(audio)
        reponse = self.reponses.pop(0)
        if isinstance(reponse, Exception):
            raise reponse
        return reponse


class FournisseurVocal(FournisseurFactice):
    def __init__(self, audio=VOCAL_RECU):
        super().__init__()
        self.audio = audio

    def telecharger_media(self, media_id):
        if isinstance(self.audio, Exception):
            raise self.audio
        return self.audio


class Scene:
    """Fatou parle au bot en vocal ; on garde tout ce que le bot envoie."""

    def __init__(self, chemin_db, dossier, *reponses_claude, transcriptions=(), transcripteur=True):
        self.chemin_db = chemin_db
        self.client = ClientSequence(*reponses_claude)
        self.analyseur = AnalyseurClaude(self.client, "claude-haiku-5-5")
        self.transcripteur = TranscripteurFactice(*transcriptions) if transcripteur else None
        self.banque = BanqueVocaux(dossier)
        self.fournisseur = FournisseurVocal()

    def _envoyer(self, message):
        self.fournisseur.envois.clear()
        traiter_message(
            message,
            self.fournisseur,
            self.chemin_db,
            self.analyseur,
            transcripteur=self.transcripteur,
            banque=self.banque,
        )
        return list(self.fournisseur.envois)

    def fatou_parle(self):
        return self._envoyer(MessageRecu(NUMERO_FATOU, TypeMessage.AUDIO, media_id="AUDIO1"))

    def fatou_ecrit(self, texte):
        return self._envoyer(MessageRecu(NUMERO_FATOU, TypeMessage.TEXTE, texte=texte))

    def fatou_touche(self, choix_id):
        return self._envoyer(MessageRecu(NUMERO_FATOU, TypeMessage.CHOIX, choix_id=choix_id))

    def baobab_touche(self, choix_id):
        return self._envoyer(MessageRecu(BAOBAB, TypeMessage.CHOIX, choix_id=choix_id))


def resume(envois):
    """Chaque envoi en une étiquette lisible : « 🔊 3 », « texte : … », « choix : … »."""
    lignes = []
    for envoi in envois:
        if len(envoi) == 3:
            lignes.append("choix : " + envoi[1].split("\n")[0])
        elif envoi[1].endswith(".ogg") or envoi[1].endswith(".mp3"):
            lignes.append("🔊 " + str(int(os.path.basename(envoi[1])[:2])))
        else:
            lignes.append("texte : " + envoi[1].split("\n")[0])
    return lignes


# --- Correspondance situation → vocal (D24, VOCAUX.md) ---


def test_chaque_texte_a_son_vocal():
    assert vocal_pour(textes.ACCUEIL_COMPLET) is Vocal.ACCUEIL_COMPLET
    assert vocal_pour(textes.SALUTATION_RETOUR) is Vocal.ACCUEIL_COMPLET
    assert vocal_pour(textes.ACCUEIL_COURT) is Vocal.ACCUEIL_COURT
    assert vocal_pour(textes.LECTURE_INTRO_VOCAL + "\n1. Richifer") is Vocal.CONFIRMATION_LECTURE
    assert vocal_pour(textes.LECTURE_INTRO + "\n1. Richifer") is Vocal.CONFIRMATION_LECTURE
    assert vocal_pour(textes.PHOTO_ILLISIBLE) is Vocal.PHOTO_ILLISIBLE
    assert vocal_pour("Vos médicaments : Richifer\n\n…\n" + textes.RAPPEL_SECURITE) is Vocal.RESULTATS
    assert vocal_pour("🚫 Adnovit C : introuvable…\n" + textes.PROPOSITION_EQUIVALENT) is Vocal.INTROUVABLE
    assert vocal_pour(textes.EQUIVALENT_ENVOYE) is Vocal.DEMANDE_ENVOYEE
    assert vocal_pour(textes.SOLUTION_TROUVEE.format(pharmacie="Pharmacie Baobab", medicament="x", adresse="a", telephone="t", lien="l")) is Vocal.SOLUTION_TROUVEE
    assert vocal_pour(textes.AUCUNE_SOLUTION.format(medicament="x")) is Vocal.AUCUNE_SOLUTION
    assert vocal_pour(textes.HORS_SUJET) is Vocal.HORS_SUJET
    assert vocal_pour(textes.URGENCE) is Vocal.URGENCE
    assert vocal_pour(textes.NON_COMPRIS) is Vocal.NON_COMPRIS
    # Sans vocal : la salutation seule avant des résultats, la demande de correction.
    assert vocal_pour(textes.SALUTATION) is None
    assert vocal_pour(textes.DEMANDE_CORRECTION) is None


# --- Parcours 7 (PARCOURS.md) ---


def test_vocal_confirmation_orale_puis_resultats(chemin_db, dossier_vocaux):
    scene = Scene(
        chemin_db,
        dossier_vocaux,
        analyse("recherche", ["Richifer", "Mag 2"]),
        transcriptions=["dama bëgg richifer ak mag deux"],
    )

    envois = scene.fatou_parle()
    assert resume(envois) == ["🔊 3", "choix : " + textes.LECTURE_INTRO_VOCAL]
    _, texte, options = envois[1]
    assert texte == f"{textes.LECTURE_INTRO_VOCAL}\n1. Richifer\n2. Mag 2\n{textes.LECTURE_QUESTION}"
    assert [o.libelle for o in options] == ["✅", "✏️"]
    # Le vocal reçu va au transcripteur, sa transcription à Claude, signalée comme telle.
    assert scene.transcripteur.audios == [VOCAL_RECU]
    assert scene.client.appels[0]["messages"][0]["content"] == INTRO_TRANSCRIPTION + "dama bëgg richifer ak mag deux"
    assert scene.client.appels[0]["model"] == "claude-haiku-5-5"

    envois = scene.fatou_touche(CHOIX_LECTURE_OUI)
    # 🔊 2 (accueil court, premier contact), puis 🔊 5 avec la fiche écrite (D23).
    assert resume(envois) == ["🔊 2", "texte : " + textes.ACCUEIL_COURT, "🔊 5", "texte : Vos médicaments : Richifer, Mag 2"]
    assert "Pharmacie Baobab" in envois[3][1]


def test_vocal_introuvable_puis_demande_et_solution(chemin_db, dossier_vocaux):
    scene = Scene(
        chemin_db,
        dossier_vocaux,
        analyse("recherche", ["Richifer", "Adnovit C"]),
        transcriptions=["richifer ak adnovit"],
    )
    scene.fatou_parle()
    envois = scene.fatou_touche(CHOIX_LECTURE_OUI)
    assert resume(envois)[-2:] == ["🔊 6", "choix : 🚫 Adnovit C : introuvable aujourd'hui dans les pharmacies partenaires."]
    options = envois[-1][2]

    envois = scene.fatou_touche(options[0].id)  # ✅ : on demande aux pharmacies
    a_fatou = [e for e in envois if e[0] == NUMERO_FATOU]
    a_baobab = [e for e in envois if e[0] == BAOBAB]
    assert resume(a_fatou) == ["🔊 7", "texte : " + textes.EQUIVALENT_ENVOYE]
    assert len(a_baobab) == 1 and len(a_baobab[0]) == 3  # la pharmacie reçoit du texte, jamais de vocal
    demande_oui = a_baobab[0][2][0].id

    envois = scene.baobab_touche(demande_oui)
    a_fatou = [e for e in envois if e[0] == NUMERO_FATOU]
    assert resume(a_fatou) == ["🔊 8", "texte : 💡 La Pharmacie Baobab a peut-être une solution pour Adnovit C."]
    assert all(not str(e[1]).endswith(".ogg") for e in envois if e[0] == BAOBAB)


def test_fin_de_delai_en_vocal(chemin_db, dossier_vocaux):
    scene = Scene(
        chemin_db, dossier_vocaux, analyse("recherche", ["Adnovit C"]), transcriptions=["adnovit"]
    )
    scene.fatou_parle()
    envois = scene.fatou_touche(CHOIX_LECTURE_OUI)
    scene.fatou_touche(envois[-1][2][0].id)

    fournisseur = FournisseurFactice()

    def est_vocal(numero):
        connexion = db.connecter(chemin_db)
        try:
            return db.est_vocal(connexion, numero)
        finally:
            connexion.close()

    plus_tard = db.maintenant() + timedelta(hours=23, minutes=1)
    assert equivalent.traiter_echeances(chemin_db, AvecVocaux(fournisseur, scene.banque, est_vocal), plus_tard) == 1
    assert resume(fournisseur.envois) == ["🔊 9", "texte : Aucune pharmacie partenaire n'a de solution pour Adnovit C. Demandez conseil à un pharmacien."]


def test_urgence_dite_en_vocal(chemin_db, dossier_vocaux):
    scene = Scene(chemin_db, dossier_vocaux, analyse("urgence"), transcriptions=["sama doom dafa dee"])
    assert resume(scene.fatou_parle()) == ["🔊 11", "texte : " + textes.URGENCE]


def test_salutation_en_vocal_au_premier_contact(chemin_db, dossier_vocaux):
    scene = Scene(chemin_db, dossier_vocaux, analyse("salutation", salue=True), transcriptions=["salamaalekum"])
    assert resume(scene.fatou_parle()) == ["🔊 1", "texte : " + textes.ACCUEIL_COMPLET.split("\n")[0]]


def test_hors_sujet_en_vocal(chemin_db, dossier_vocaux):
    scene = Scene(
        chemin_db, dossier_vocaux, analyse("salutation"), analyse("hors_sujet"), transcriptions=["salam", "ñaata la ?"]
    )
    scene.fatou_parle()
    assert resume(scene.fatou_parle()) == ["🔊 10", "texte : " + textes.HORS_SUJET]


def test_echec_de_transcription(chemin_db, dossier_vocaux):
    scene = Scene(chemin_db, dossier_vocaux, transcriptions=[EchecTranscription("erreur d'ElevenLabs (500)")])
    assert resume(scene.fatou_parle()) == ["🔊 12", "texte : " + textes.NON_COMPRIS.split("\n")[0]]
    assert scene.client.appels == []  # Claude n'est pas appelé


def test_transcription_vide(chemin_db, dossier_vocaux):
    scene = Scene(chemin_db, dossier_vocaux, transcriptions=[""])
    assert resume(scene.fatou_parle()) == ["🔊 12", "texte : " + textes.NON_COMPRIS.split("\n")[0]]


def test_telechargement_impossible(chemin_db, dossier_vocaux):
    scene = Scene(chemin_db, dossier_vocaux, transcriptions=[])
    scene.fournisseur.audio = RuntimeError("Meta indisponible")
    assert resume(scene.fatou_parle()) == ["🔊 12", "texte : " + textes.NON_COMPRIS.split("\n")[0]]


def test_vocal_absent_le_texte_part_seul(chemin_db, tmp_path, caplog):
    vide = tmp_path / "vide"
    vide.mkdir()
    scene = Scene(chemin_db, vide, analyse("recherche", ["Richifer"]), transcriptions=["richifer"])
    with caplog.at_level(logging.WARNING, logger="pharmasur.vocaux"):
        envois = scene.fatou_parle()
    assert resume(envois) == ["choix : " + textes.LECTURE_INTRO_VOCAL]
    assert "Vocal 3 absent" in caplog.text


def test_vocal_dans_un_autre_format(chemin_db, tmp_path, caplog):
    dossier = tmp_path / "vocaux"
    dossier.mkdir()
    (dossier / "11-urgence.mp3").write_bytes(b"ID3")
    scene = Scene(chemin_db, dossier, analyse("urgence"), transcriptions=["urgence"])
    with caplog.at_level(logging.WARNING, logger="pharmasur.vocaux"):
        envois = scene.fatou_parle()
    assert resume(envois) == ["🔊 11", "texte : " + textes.URGENCE]
    assert ".mp3" in caplog.text


def test_texte_apres_vocal_sans_vocal(chemin_db, dossier_vocaux):
    scene = Scene(
        chemin_db,
        dossier_vocaux,
        analyse("urgence"),
        analyse("recherche", ["Richifer"]),
        transcriptions=["urgence"],
    )
    scene.fatou_parle()
    envois = scene.fatou_ecrit("Richifer svp")
    # Fatou écrit : le bot répond par écrit seulement, avec les résultats directs (parcours 1).
    assert resume(envois) == ["texte : Vos médicaments : Richifer"]


def test_sans_transcripteur_reponse_provisoire(chemin_db, dossier_vocaux):
    scene = Scene(chemin_db, dossier_vocaux, transcripteur=False)
    assert resume(scene.fatou_parle()) == ["texte : " + textes.PROVISOIRE_VOCAL]


def test_correction_dite_en_vocal(chemin_db, dossier_vocaux):
    scene = Scene(
        chemin_db,
        dossier_vocaux,
        analyse("recherche", ["Richifer", "Mag"]),
        analyse("recherche", ["Mag 2"]),
        transcriptions=["richifer ak mag", "mag deux"],
    )
    scene.fatou_parle()
    scene.fatou_touche("lecture_corriger")
    envois = scene.fatou_parle()
    assert resume(envois) == ["🔊 3", "choix : " + textes.LECTURE_INTRO_CORRIGEE]
    assert "2. Mag 2" in envois[1][1]
    assert scene.client.appels[1]["messages"][0]["content"].startswith(INTRO_TRANSCRIPTION)


def test_forme_retenue_sans_historique(chemin_db):
    connexion = db.connecter(chemin_db)
    try:
        db.definir_forme(connexion, NUMERO_FATOU, vocal=True)
        assert db.est_vocal(connexion, NUMERO_FATOU)
        db.definir_forme(connexion, NUMERO_FATOU, vocal=False)
        assert not db.est_vocal(connexion, NUMERO_FATOU)
        assert connexion.execute("SELECT COUNT(*) FROM forme_conversation").fetchone()[0] == 1
    finally:
        connexion.close()


# --- Transcription ElevenLabs (D32) ---


def test_transcripteur_elevenlabs():
    requetes = []

    def gerer(requete):
        requetes.append(requete)
        return httpx.Response(200, json={"language_code": "wo", "text": " dama bëgg doliprane "})

    transcripteur = TranscripteurElevenLabs("cle", client=httpx.Client(transport=httpx.MockTransport(gerer)))
    assert transcripteur.transcrire(VOCAL_RECU) == "dama bëgg doliprane"
    corps = requetes[0].content
    assert requetes[0].headers["xi-api-key"] == "cle"
    assert b'name="model_id"\r\n\r\nscribe_v2' in corps
    assert b'name="language_code"\r\n\r\nwol' in corps


@pytest.mark.parametrize(
    "reponse",
    [
        httpx.Response(401, json={"detail": "clé invalide"}),
        httpx.Response(200, text="pas du json"),
    ],
)
def test_transcripteur_echecs(reponse):
    transcripteur = TranscripteurElevenLabs("cle", client=httpx.Client(transport=httpx.MockTransport(lambda r: reponse)))
    with pytest.raises(EchecTranscription):
        transcripteur.transcrire(VOCAL_RECU)


def test_transcripteur_connexion_impossible():
    def gerer(requete):
        raise httpx.ConnectError("hors ligne")

    transcripteur = TranscripteurElevenLabs("cle", client=httpx.Client(transport=httpx.MockTransport(gerer)))
    with pytest.raises(EchecTranscription):
        transcripteur.transcrire(VOCAL_RECU)


# --- Cache des identifiants média chez Meta ---


def _meta(gerer):
    return FournisseurMeta("jeton", "123", "verif", "secret", client=httpx.Client(transport=httpx.MockTransport(gerer)))


def test_vocal_televerse_une_seule_fois(tmp_path):
    fichier = tmp_path / "05-resultats.ogg"
    fichier.write_bytes(b"OggS-1")
    requetes = []

    def gerer(requete):
        requetes.append(requete)
        if requete.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": f"MEDIA{len(requetes)}"})
        return httpx.Response(200, json={"messages": [{"id": "wamid"}]})

    meta = _meta(gerer)
    meta.envoyer_audio(NUMERO_FATOU, str(fichier))
    meta.envoyer_audio(NUMERO_FATOU, str(fichier))
    chemins = [r.url.path.rsplit("/", 1)[-1] for r in requetes]
    assert chemins == ["media", "messages", "messages"]
    assert json.loads(requetes[2].content)["audio"] == {"id": "MEDIA1"}

    # Vocal réenregistré : nouveau téléversement.
    fichier.write_bytes(b"OggS-deuxieme-version")
    meta.envoyer_audio(NUMERO_FATOU, str(fichier))
    assert [r.url.path.rsplit("/", 1)[-1] for r in requetes][3:] == ["media", "messages"]


def test_identifiant_expire_nouveau_televersement(tmp_path):
    fichier = tmp_path / "05-resultats.ogg"
    fichier.write_bytes(b"OggS")
    requetes = []
    refuser = {"actif": False}

    def gerer(requete):
        requetes.append(requete)
        if requete.url.path.endswith("/media"):
            return httpx.Response(200, json={"id": f"MEDIA{len(requetes)}"})
        if refuser["actif"]:
            refuser["actif"] = False
            return httpx.Response(400, json={"error": {"message": "media id expiré"}})
        return httpx.Response(200, json={"messages": [{"id": "wamid"}]})

    meta = _meta(gerer)
    meta.envoyer_audio(NUMERO_FATOU, str(fichier))
    refuser["actif"] = True
    meta.envoyer_audio(NUMERO_FATOU, str(fichier))
    assert [r.url.path.rsplit("/", 1)[-1] for r in requetes] == ["media", "messages", "messages", "media", "messages"]
    assert json.loads(requetes[-1].content)["audio"] == {"id": "MEDIA4"}

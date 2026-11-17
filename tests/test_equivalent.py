"""Parcours 2 : demande d'équivalent (D10, D11, D15, D16, D17, D36, D40, D41), sans appel réseau."""

import sqlite3
from datetime import timedelta

import pytest

from pharmasur import db, equivalent
from pharmasur.bot import traiter_message
from pharmasur.ia import AnalyseurClaude
from pharmasur.whatsapp import MessageRecu, TypeMessage

from test_app import NUMERO_BAOBAB, NUMERO_FATOU, FournisseurFactice
from test_photo import ClientSequence, analyse

BAOBAB = db.normaliser_numero(NUMERO_BAOBAB)
QUESTION = "Voulez-vous qu'on demande aux pharmacies si l'une d'elles a une solution ?"


@pytest.fixture
def chemin_db(tmp_path):
    chemin = str(tmp_path / "test.db")
    db.initialiser(chemin, NUMERO_BAOBAB)
    return chemin


class Scene:
    """Fatou et Baobab parlent au bot ; on garde tout ce que le bot envoie."""

    def __init__(self, chemin_db, *reponses_claude):
        self.chemin_db = chemin_db
        self.analyseur = AnalyseurClaude(ClientSequence(*reponses_claude), "claude-haiku-5-5")
        self.fournisseur = FournisseurFactice()

    def _envoyer(self, message):
        self.fournisseur.envois.clear()
        traiter_message(message, self.fournisseur, self.chemin_db, self.analyseur)
        return list(self.fournisseur.envois)

    def fatou_ecrit(self, texte):
        return self._envoyer(MessageRecu(NUMERO_FATOU, TypeMessage.TEXTE, texte=texte))

    def fatou_touche(self, choix_id):
        return self._envoyer(MessageRecu(NUMERO_FATOU, TypeMessage.CHOIX, choix_id=choix_id))

    def baobab_touche(self, choix_id):
        return self._envoyer(MessageRecu(BAOBAB, TypeMessage.CHOIX, choix_id=choix_id))


def proposition(envois):
    """Le message de proposition (D10) parmi les envois : (texte, options)."""
    choix = [e for e in envois if len(e) == 3]
    assert len(choix) == 1
    _, texte, options = choix[0]
    return texte, options


def demandes(chemin_db):
    connexion = db.connecter(chemin_db)
    try:
        return [dict(l) for l in connexion.execute("SELECT * FROM demande_equivalent ORDER BY id")]
    finally:
        connexion.close()


def accepter(scene, medicament="Smecta"):
    """Fatou cherche un médicament introuvable, puis touche ✅. Renvoie les envois du ✅."""
    _, options = proposition(scene.fatou_ecrit(medicament))
    return scene.fatou_touche(options[0].id)


# --- Proposition (D10) ---


def test_proposition_apres_un_introuvable(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Doliprane", "Smecta"]))
    envois = scene.fatou_ecrit("Doliprane et Smecta")
    assert envois[1][1].startswith("Vos médicaments : Doliprane, Smecta")  # fiche des trouvés d'abord
    texte, options = proposition(envois)
    assert texte == "🚫 Smecta : introuvable aujourd'hui dans les pharmacies partenaires.\n" + QUESTION
    assert [o.libelle for o in options] == ["✅", "❌"]  # des icônes, sans mot
    assert demandes(chemin_db) == []  # rien n'est envoyé sans l'accord de la personne


def test_un_seul_message_pour_plusieurs_introuvables(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta", "Spasfon"]))
    texte, _ = proposition(scene.fatou_ecrit("Smecta et Spasfon"))
    assert texte.count("🚫") == 2
    scene.fatou_touche(proposition(scene.fournisseur.envois)[1][0].id)
    assert [d["medicament"] for d in demandes(chemin_db)] == ["Smecta", "Spasfon"]


# --- ✅ et ❌ ---


def test_oui_cree_la_demande_et_l_envoie_seulement_a_baobab(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    envois = accepter(scene)

    (demande,) = demandes(chemin_db)
    assert demande["medicament"] == "Smecta" and demande["numero"] == NUMERO_FATOU and not demande["close"]
    duree = db.datetime.fromisoformat(demande["fin_le"]) - db.datetime.fromisoformat(demande["cree_le"])
    assert duree == timedelta(hours=23)  # D17

    aux_pharmacies = [e for e in envois if e[0] != NUMERO_FATOU]
    assert len(aux_pharmacies) == 1  # Liberté, Teranga et Jamm ont des numéros fictifs
    destinataire, texte, options = aux_pharmacies[0]
    assert destinataire == BAOBAB
    assert texte == (
        "🔎 Une personne cherche : Smecta.\n"
        "Introuvable aujourd'hui dans le réseau. Avez-vous une solution ?"
    )
    assert NUMERO_FATOU not in texte  # rien sur la personne (D15)
    assert [o.libelle for o in options] == ["J'ai une solution", "Non"]
    assert all(len(o.libelle) <= 20 for o in options)  # limite Meta
    assert envois[-1] == (NUMERO_FATOU, "C'est envoyé ✅ Je vous préviens dès qu'une pharmacie a une solution.")


def test_non_n_envoie_rien(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    _, options = proposition(scene.fatou_ecrit("Smecta"))
    assert scene.fatou_touche(options[1].id) == [(NUMERO_FATOU, "D'accord 👍 Rien n'est envoyé aux pharmacies.")]
    assert demandes(chemin_db) == []
    # La proposition est effacée : retoucher un bouton ne renvoie rien aux pharmacies.
    scene.fatou_touche(options[0].id)
    assert demandes(chemin_db) == []


def test_sans_numero_de_baobab_aucune_pharmacie_n_est_jointe(tmp_path):
    chemin = str(tmp_path / "sans_baobab.db")
    db.initialiser(chemin, "")
    scene = Scene(chemin, analyse("recherche", ["Smecta"]))
    envois = accepter(scene)
    assert [e[0] for e in envois] == [NUMERO_FATOU]  # aucun envoi vers un numéro fictif
    assert len(demandes(chemin)) == 1


def test_un_echec_d_envoi_a_une_pharmacie_ne_bloque_pas(chemin_db):
    class FournisseurCapricieux(FournisseurFactice):
        def envoyer_choix(self, destinataire, texte, options):
            if destinataire == BAOBAB:
                raise RuntimeError("hors de la fenêtre de 24 h")
            super().envoyer_choix(destinataire, texte, options)

    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    scene.fournisseur = FournisseurCapricieux()
    envois = accepter(scene)
    assert envois[-1][1].startswith("C'est envoyé ✅")


# --- Réponse de la pharmacie (D11, D16) ---


def test_oui_de_baobab_previent_fatou_sans_nom_de_produit(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    envois = accepter(scene)
    oui = [e for e in envois if e[0] == BAOBAB][0][2][0].id

    envois = scene.baobab_touche(oui)
    assert envois[0] == (BAOBAB, "Merci ✅ La personne va être prévenue.")
    destinataire, texte = envois[1]
    assert destinataire == NUMERO_FATOU
    assert texte.startswith(
        "💡 La Pharmacie Baobab a peut-être une solution pour Smecta.\nAllez demander conseil au pharmacien.\n"
    )
    assert "📍 Rue 10, Grand Yoff" in texte and "📞 +221 33 000 00 01" in texte and "🗺️ https://" in texte
    assert "UPSA" not in texte  # D11 : jamais le produit proposé

    # Un deuxième « Oui » de la même pharmacie ne prévient pas Fatou une seconde fois.
    assert scene.baobab_touche(oui) == [(BAOBAB, "Merci ✅ La personne va être prévenue.")]


def test_non_de_baobab_ne_previent_personne(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    envois = accepter(scene)
    non = [e for e in envois if e[0] == BAOBAB][0][2][1].id
    assert scene.baobab_touche(non) == [(BAOBAB, "Merci, c'est noté.")]


def test_deux_demandes_ouvertes_en_parallele(chemin_db):
    # D40 : une nouvelle recherche ne ferme pas la demande en cours.
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]), analyse("recherche", ["Spasfon"]))
    envois_smecta = accepter(scene, "Smecta")
    envois_spasfon = accepter(scene, "Spasfon")
    assert [d["medicament"] for d in demandes(chemin_db)] == ["Smecta", "Spasfon"]
    assert not any(d["close"] for d in demandes(chemin_db))

    oui_smecta = [e for e in envois_smecta if e[0] == BAOBAB][0][2][0].id
    oui_spasfon = [e for e in envois_spasfon if e[0] == BAOBAB][0][2][0].id
    assert oui_smecta != oui_spasfon  # chaque demande a ses propres boutons
    assert "pour Spasfon" in scene.baobab_touche(oui_spasfon)[1][1]
    assert "pour Smecta" in scene.baobab_touche(oui_smecta)[1][1]


def test_message_ordinaire_d_une_pharmacie_inchange(chemin_db):
    scene = Scene(chemin_db)
    envois = scene._envoyer(MessageRecu(BAOBAB, TypeMessage.TEXTE, texte="plus de doliprane"))
    assert envois[0][1].startswith("✅ Message reçu, Pharmacie Baobab.")


# --- Fin de délai (D17, D36) et demande close (D41) ---


def test_echeance_sans_oui_previent_fatou_et_efface_le_lien(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    accepter(scene)
    fournisseur = FournisseurFactice()

    # Avant les 23 heures : rien ne se passe.
    assert equivalent.traiter_echeances(chemin_db, fournisseur, db.maintenant() + timedelta(hours=22)) == 0
    assert fournisseur.envois == []

    apres = db.maintenant() + timedelta(hours=23, minutes=1)
    assert equivalent.traiter_echeances(chemin_db, fournisseur, apres) == 1
    assert fournisseur.envois == [
        (NUMERO_FATOU, "Aucune pharmacie partenaire n'a de solution pour Smecta. Demandez conseil à un pharmacien.")
    ]
    (demande,) = demandes(chemin_db)
    assert demande["close"] == 1 and demande["numero"] is None  # D15

    # Un second passage (ou un redémarrage) ne renvoie rien.
    fournisseur.envois.clear()
    assert equivalent.traiter_echeances(chemin_db, fournisseur, apres) == 0
    assert fournisseur.envois == []


def test_echeance_apres_un_oui_clot_sans_message(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    envois = accepter(scene)
    scene.baobab_touche([e for e in envois if e[0] == BAOBAB][0][2][0].id)

    fournisseur = FournisseurFactice()
    assert equivalent.traiter_echeances(chemin_db, fournisseur, db.maintenant() + timedelta(hours=24)) == 1
    assert fournisseur.envois == []
    assert demandes(chemin_db)[0]["numero"] is None


def test_oui_apres_cloture(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    envois = accepter(scene)
    oui = [e for e in envois if e[0] == BAOBAB][0][2][0].id
    equivalent.traiter_echeances(chemin_db, FournisseurFactice(), db.maintenant() + timedelta(hours=24))

    # D41 : seulement une réponse à la pharmacie ; Fatou n'est pas prévenue.
    assert scene.baobab_touche(oui) == [
        (BAOBAB, "Merci, cette demande est close. La personne a été orientée vers un pharmacien.")
    ]


def test_oui_apres_23_heures_avant_le_passage_de_la_boucle(chemin_db):
    scene = Scene(chemin_db, analyse("recherche", ["Smecta"]))
    envois = accepter(scene)
    oui = equivalent.lire_identifiant([e for e in envois if e[0] == BAOBAB][0][2][0].id)[1]
    connexion = db.connecter(chemin_db)
    try:
        pharmacie = db.pharmacie_par_numero(connexion, BAOBAB)
        fournisseur = FournisseurFactice()
        message = MessageRecu(BAOBAB, TypeMessage.CHOIX, choix_id=equivalent.identifiant(equivalent.PHARMACIE_OUI, oui))
        equivalent.repondre_pharmacie(message, pharmacie, fournisseur, connexion, db.maintenant() + timedelta(hours=23, seconds=1))
    finally:
        connexion.close()
    assert fournisseur.envois == [
        (BAOBAB, "Merci, cette demande est close. La personne a été orientée vers un pharmacien.")
    ]


def test_tables_creees_dans_une_base_existante(tmp_path):
    chemin = str(tmp_path / "ancienne.db")
    db.initialiser(chemin, NUMERO_BAOBAB)
    connexion = sqlite3.connect(chemin)
    connexion.execute("DROP TABLE proposition_equivalent")
    connexion.commit()
    connexion.close()
    db.initialiser(chemin, NUMERO_BAOBAB)
    tables = [r[0] for r in sqlite3.connect(chemin).execute("SELECT name FROM sqlite_master WHERE type='table'")]
    assert "proposition_equivalent" in tables

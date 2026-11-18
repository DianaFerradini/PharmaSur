"""Parcours 3 : côté pharmacie (D2, D14, D18, D19, D20), sans appel réseau."""

import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from pharmasur import db, equivalent, textes
from pharmasur.bot import traiter_message
from pharmasur.pharmacie import STOCK_NON, STOCK_OUI, AnalyseurPharmacie, formater_resume
from pharmasur.recherche import analyser_medicament, rechercher
from pharmasur.whatsapp import MessageRecu, TypeMessage

from test_app import NUMERO_BAOBAB, NUMERO_FATOU, FournisseurFactice
from test_photo import ClientSequence

BAOBAB = db.normaliser_numero(NUMERO_BAOBAB)


def reponse(intention, *medicaments):
    """Réponse factice de Haiku : medicaments = (cite, produit, certain)."""
    texte = json.dumps(
        {
            "intention": intention,
            "medicaments": [{"cite": c, "produit": p, "certain": s} for c, p, s in medicaments],
        }
    )
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=texte)])


@pytest.fixture
def chemin_db(tmp_path):
    chemin = str(tmp_path / "test.db")
    db.initialiser(chemin, NUMERO_BAOBAB, graine=1)
    return chemin


class Baobab:
    def __init__(self, chemin_db, *reponses):
        self.chemin_db = chemin_db
        self.client = ClientSequence(*reponses)
        self.analyseur = AnalyseurPharmacie(self.client, "claude-haiku-5-5")
        self.fournisseur = FournisseurFactice()

    def _envoyer(self, message):
        self.fournisseur.envois.clear()
        traiter_message(message, self.fournisseur, self.chemin_db, analyseur_pharmacie=self.analyseur)
        return list(self.fournisseur.envois)

    def ecrit(self, texte):
        return self._envoyer(MessageRecu(BAOBAB, TypeMessage.TEXTE, texte=texte))

    def touche(self, choix_id):
        return self._envoyer(MessageRecu(BAOBAB, TypeMessage.CHOIX, choix_id=choix_id))


def etat(chemin_db, libelle, pharmacie="Pharmacie Baobab"):
    """None si le produit n'est pas au catalogue, sinon True s'il est en rupture."""
    connexion = db.connecter(chemin_db)
    try:
        ligne = connexion.execute(
            "SELECT c.en_rupture FROM catalogue c JOIN pharmacie p ON p.id = c.pharmacie_id"
            " WHERE p.nom = ? AND c.libelle = ?",
            (pharmacie, libelle),
        ).fetchone()
        return None if ligne is None else bool(ligne["en_rupture"])
    finally:
        connexion.close()


def pharmacies_pour(chemin_db, texte):
    connexion = db.connecter(chemin_db)
    try:
        resultat = rechercher([analyser_medicament(texte)], db.charger_pharmacies(connexion))
        return {r.pharmacie.nom for r in resultat.pharmacies}
    finally:
        connexion.close()


# --- Rupture et retour en stock (D2, D18, D19) ---


def test_rupture_sure_appliquee_tout_de_suite(chemin_db):
    baobab = Baobab(chemin_db, reponse("rupture", ("doliprane 1000", "Doliprane 1000 mg comprimés", True)))
    envois = baobab.ecrit("plus de doliprane 1000")
    assert envois == [(BAOBAB, "✅ Doliprane 1000 mg comprimés noté en rupture.")]
    assert etat(chemin_db, "Doliprane 1000 mg comprimés") is True
    # Le catalogue arrive dans le message, pas dans le prompt système (cache).
    appel = baobab.client.appels[0]
    assert "Doliprane 1000 mg comprimés" in appel["messages"][0]["content"]
    assert "Doliprane 1000 mg comprimés" not in appel["system"][0]["text"]
    assert appel["output_config"]["effort"] == "high"


def test_la_rupture_retire_la_pharmacie_des_resultats_puis_le_retour_la_remet(chemin_db):
    assert pharmacies_pour(chemin_db, "Mag 2") == {"Pharmacie Baobab", "Pharmacie Liberté"}
    baobab = Baobab(
        chemin_db,
        reponse("rupture", ("mag 2", "Mag 2 100 mg comprimés", True)),
        reponse("retour", ("Mag 2", "Mag 2 100 mg comprimés", True)),
    )
    assert baobab.ecrit("Le mag 2 est en rupture de stock") == [(BAOBAB, "✅ Mag 2 100 mg comprimés noté en rupture.")]
    assert pharmacies_pour(chemin_db, "Mag 2") == {"Pharmacie Liberté"}
    assert baobab.ecrit("Mag 2 est revenu en stock") == [(BAOBAB, "✅ Mag 2 100 mg comprimés de nouveau disponible.")]
    assert pharmacies_pour(chemin_db, "Mag 2") == {"Pharmacie Baobab", "Pharmacie Liberté"}


def test_nom_approximatif_demande_confirmation_puis_oui(chemin_db):
    baobab = Baobab(chemin_db, reponse("rupture", ("dolipran sirop", "Doliprane 2,4 % sirop", False)))
    envois = baobab.ecrit("dolipran sirop fini")
    assert len(envois) == 1
    _, texte, options = envois[0]
    assert texte == "Vous voulez dire : Doliprane 2,4 % sirop en rupture ?"
    assert [o.libelle for o in options] == ["Oui", "Non"]
    assert etat(chemin_db, "Doliprane 2,4 % sirop") is False  # rien n'est appliqué avant le Oui
    assert baobab.touche(options[0].id) == [(BAOBAB, "✅ Doliprane 2,4 % sirop noté en rupture.")]
    assert etat(chemin_db, "Doliprane 2,4 % sirop") is True
    # Le même bouton touché une seconde fois ne fait plus rien.
    assert baobab.touche(options[0].id) == [(BAOBAB, textes.SIGNALEMENT_EXPIRE)]


def test_nom_approximatif_puis_non(chemin_db):
    baobab = Baobab(chemin_db, reponse("rupture", ("dolipran sirop", "Doliprane 2,4 % sirop", False)))
    _, _, options = baobab.ecrit("dolipran sirop fini")[0]
    assert baobab.touche(options[1].id) == [(BAOBAB, textes.SIGNALEMENT_ANNULE)]
    assert etat(chemin_db, "Doliprane 2,4 % sirop") is False


def test_haiku_sur_mais_nom_different_demande_confirmation(chemin_db):
    # D19 : le contrôle de la recherche voit que « dolipran » n'est pas exactement le nom.
    baobab = Baobab(chemin_db, reponse("rupture", ("dolipran 1000", "Doliprane 1000 mg comprimés", True)))
    _, texte, _ = baobab.ecrit("dolipran 1000 fini")[0]
    assert texte == "Vous voulez dire : Doliprane 1000 mg comprimés en rupture ?"


def test_plusieurs_produits_possibles_une_confirmation_par_produit(chemin_db):
    baobab = Baobab(
        chemin_db,
        reponse(
            "rupture",
            ("Doliprane", "Doliprane 2,4 % sirop", False),
            ("Doliprane", "Doliprane 1000 mg comprimés", False),
        ),
    )
    envois = baobab.ecrit("plus de Doliprane")
    assert [e[1] for e in envois] == [
        "Vous voulez dire : Doliprane 2,4 % sirop en rupture ?",
        "Vous voulez dire : Doliprane 1000 mg comprimés en rupture ?",
    ]
    assert envois[0][2][0].id != envois[1][2][0].id


def test_produit_invente_par_haiku_traite_comme_hors_catalogue(chemin_db):
    baobab = Baobab(chemin_db, reponse("retour", ("Smecta", "Smecta 3 g sachets", True)))
    _, texte, _ = baobab.ecrit("on a reçu le Smecta")[0]
    assert texte == "Smecta n'est pas dans votre catalogue.\nL'ajouter comme disponible ?"


# --- Hors catalogue (D20) ---


def test_hors_catalogue_toujours_confirme_puis_ajoute(chemin_db):
    assert pharmacies_pour(chemin_db, "Ventoline") == set()
    baobab = Baobab(chemin_db, reponse("retour", ("Ventoline", "", True)))
    envois = baobab.ecrit("Ventoline de nouveau disponible")
    _, texte, options = envois[0]
    assert texte == "Ventoline n'est pas dans votre catalogue.\nL'ajouter comme disponible ?"
    assert etat(chemin_db, "Ventoline") is None
    assert baobab.touche(options[0].id) == [(BAOBAB, "✅ Ventoline ajouté à votre catalogue, disponible.")]
    assert etat(chemin_db, "Ventoline") is False
    assert pharmacies_pour(chemin_db, "Ventoline") == {"Pharmacie Baobab"}


def test_hors_catalogue_en_rupture_ajoute_en_rupture(chemin_db):
    baobab = Baobab(chemin_db, reponse("rupture", ("ventoline", "", False)))
    _, texte, options = baobab.ecrit("plus de ventoline")[0]
    assert texte == "Ventoline n'est pas dans votre catalogue.\nL'ajouter comme en rupture ?"
    assert baobab.touche(options[0].id) == [(BAOBAB, "✅ Ventoline ajouté à votre catalogue, en rupture.")]
    assert etat(chemin_db, "Ventoline") is True
    assert pharmacies_pour(chemin_db, "Ventoline") == set()


def test_signalement_expire_apres_24_heures(chemin_db):
    from datetime import timedelta

    connexion = db.connecter(chemin_db)
    try:
        pharmacie = db.pharmacie_par_numero(connexion, BAOBAB)
        ancien = db.maintenant() - timedelta(hours=25)
        signalement_id = db.creer_signalement(connexion, pharmacie["id"], "Ventoline", False, True, ancien)
    finally:
        connexion.close()
    baobab = Baobab(chemin_db)
    assert baobab.touche(f"{STOCK_OUI}:{signalement_id}") == [(BAOBAB, textes.SIGNALEMENT_EXPIRE)]
    assert etat(chemin_db, "Ventoline") is None


# --- Résumé (D14) ---


def test_resume_avec_les_chiffres_des_recherches_simulees(chemin_db):
    baobab = Baobab(chemin_db, reponse("resume"))
    envois = baobab.ecrit("résumé")
    assert envois == [
        (
            BAOBAB,
            "📊 Votre semaine avec PharmaSûr\n"
            "• Vous êtes apparu dans 16 résultats de recherche.\n"
            "• Demande manquée :\n"
            "  – Smecta : 12 recherches\n"
            "  – Spasfon : 8 recherches\n"
            "  – Amoxicilline 500 mg : 4 recherches\n"
            "  – Efferalgan 500 mg : 3 recherches\n"
            "  – Ventoline : 3 recherches",
        )
    ]


def test_resume_singulier_et_sans_demande_manquee():
    assert formater_resume(1, []) == (
        "📊 Votre semaine avec PharmaSûr\n"
        "• Vous êtes apparu dans 1 résultat de recherche.\n"
        "• Demande manquée : aucune cette semaine."
    )
    assert formater_resume(0, [("Smecta", 1)]).endswith("  – Smecta : 1 recherche")


# --- Messages non compris ---


def test_message_incompris_recoit_l_aide_des_pharmacies(chemin_db):
    baobab = Baobab(chemin_db, reponse("autre"))
    assert baobab.ecrit("bonjour, ça va ?") == [(BAOBAB, textes.AIDE_PHARMACIE)]


def test_echec_de_l_api_recoit_l_aide_des_pharmacies(chemin_db):
    erreur = anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    baobab = Baobab(chemin_db, erreur)
    assert baobab.ecrit("plus de doliprane") == [(BAOBAB, textes.AIDE_PHARMACIE)]


def test_sans_cle_anthropic_reponse_provisoire(chemin_db):
    fournisseur = FournisseurFactice()
    traiter_message(MessageRecu(BAOBAB, TypeMessage.TEXTE, texte="plus de doliprane"), fournisseur, chemin_db)
    assert fournisseur.envois == [(BAOBAB, textes.PROVISOIRE_PHARMACIE.format(pharmacie="Pharmacie Baobab"))]


# --- Non-régression : les boutons des demandes d'équivalent (parcours 2) ---


def test_boutons_equivalent_inchanges_sans_appel_a_claude(chemin_db):
    connexion = db.connecter(chemin_db)
    try:
        demande_id = db.creer_demande(connexion, "Smecta", NUMERO_FATOU)
    finally:
        connexion.close()
    baobab = Baobab(chemin_db)  # aucune réponse prévue : un appel à Claude échouerait
    envois = baobab.touche(equivalent.identifiant(equivalent.PHARMACIE_OUI, demande_id))
    assert envois[0] == (BAOBAB, textes.MERCI_PHARMACIE_OUI)
    assert envois[1][0] == db.normaliser_numero(NUMERO_FATOU)
    assert "Pharmacie Baobab a peut-être une solution pour Smecta" in envois[1][1]
    assert baobab.client.appels == []

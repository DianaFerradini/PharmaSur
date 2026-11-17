"""Recherche : correspondance des médicaments (D27, D28), ruptures, introuvables (D5),
ordre des pharmacies (D25) et fiche résultat (D7, D8), sur les données de PARCOURS.md."""

import random
from dataclasses import replace

import pytest

from pharmasur.db import PHARMACIES_SIMULEES, lien_itineraire
from pharmasur.recherche import (
    Pharmacie,
    ProduitCatalogue,
    analyser_medicament,
    decouper_texte,
    formater_fiche,
    rechercher,
)
from pharmasur.textes import RAPPEL_SECURITE


@pytest.fixture
def pharmacies() -> list[Pharmacie]:
    return [
        Pharmacie(
            id=i,
            nom=p["nom"],
            adresse=p["adresse"],
            telephone=p["telephone"],
            lien_itineraire=lien_itineraire(p["adresse"]),
            catalogue=tuple(ProduitCatalogue(libelle) for libelle in p["catalogue"]),
        )
        for i, p in enumerate(PHARMACIES_SIMULEES, start=1)
    ]


def demandes(*textes):
    return [analyser_medicament(t) for t in textes]


def par_nom(resultat):
    return {r.pharmacie.nom: r for r in resultat.pharmacies}


# --- Découpage d'un médicament ---


def test_analyse_nom_dosage_forme():
    m = analyser_medicament("Doliprane 1000 comprimés")
    assert m.nom == ("doliprane",)
    assert m.dosage == (1000.0,)
    assert m.forme == "comprime"
    assert m.libelle == "Doliprane 1000 comprimés"


def test_analyse_dosage_compose_et_pourcentage():
    assert analyser_medicament("Amoxicilline 250 mg/5 ml sirop").dosage == (250.0, 5.0)
    assert analyser_medicament("Doliprane 2,4 % sirop").dosage == (2.4,)


def test_analyse_grammes_convertis_en_mg():
    assert analyser_medicament("doliprane 1g").dosage == (1000.0,)


def test_analyse_salutation_sans_medicament():
    assert analyser_medicament("Bonjour") is None


def test_decoupage_provisoire_du_texte_libre():
    libelles = [m.libelle for m in decouper_texte("Bonjour, je cherche amoxicilline sirop et doliprane")]
    assert libelles == ["Amoxicilline sirop", "Doliprane"]


# --- Parcours 1 ---


def test_parcours_1_baobab_en_tete_avec_tous_les_doliprane(pharmacies):
    resultat = rechercher(demandes("amoxicilline sirop", "doliprane"), pharmacies, random.Random(1))
    premiere = resultat.pharmacies[0]
    assert premiere.pharmacie.nom == "Pharmacie Baobab"
    assert premiere.nombre == 2
    assert premiere.produits == (
        ("Amoxicilline 250 mg/5 ml sirop",),
        ("Doliprane 2,4 % sirop", "Doliprane 1000 mg comprimés"),
    )
    assert [r.pharmacie.nom for r in resultat.pharmacies[1:]] in (
        ["Pharmacie Liberté", "Pharmacie Teranga"],
        ["Pharmacie Teranga", "Pharmacie Liberté"],
    )
    assert resultat.introuvables == ()


def test_efferalgan_non_compte_pour_doliprane(pharmacies):
    teranga = par_nom(rechercher(demandes("doliprane"), pharmacies))["Pharmacie Teranga"]
    assert teranga.produits == (("Doliprane 1000 mg comprimés",),)


def test_jamm_absente_sans_clamoxyl(pharmacies):
    resultat = rechercher(demandes("amoxicilline sirop", "doliprane"), pharmacies)
    assert "Pharmacie Jamm" not in par_nom(resultat)


def test_ex_aequo_liberte_teranga_ordre_tire_au_hasard(pharmacies):
    ordres = set()
    for graine in range(30):
        resultat = rechercher(demandes("amoxicilline sirop", "doliprane"), pharmacies, random.Random(graine))
        ordres.add(tuple(r.pharmacie.nom for r in resultat.pharmacies[1:]))
    assert ordres == {
        ("Pharmacie Liberté", "Pharmacie Teranga"),
        ("Pharmacie Teranga", "Pharmacie Liberté"),
    }


# --- Principe actif (D28) ---


def test_principe_actif_trouve_liberte_mais_pas_clamoxyl(pharmacies):
    resultat = rechercher(demandes("amoxicilline 500 mg"), pharmacies)
    assert [r.pharmacie.nom for r in resultat.pharmacies] == ["Pharmacie Liberté"]
    assert resultat.pharmacies[0].produits == (("Amoxicilline 500 mg gélules",),)


def test_clamoxyl_reste_trouvable_par_son_nom(pharmacies):
    resultat = rechercher(demandes("Clamoxyl"), pharmacies)
    assert [r.pharmacie.nom for r in resultat.pharmacies] == ["Pharmacie Jamm"]


# --- Introuvable (D5, parcours 2) ---


def test_smecta_introuvable_medicament_par_medicament(pharmacies):
    resultat = rechercher(demandes("amoxicilline sirop", "doliprane", "smecta"), pharmacies)
    assert [m.libelle for m in resultat.introuvables] == ["Smecta"]
    assert par_nom(resultat)["Pharmacie Baobab"].nombre == 2


def test_tout_introuvable_pas_de_fiche(pharmacies):
    resultat = rechercher(demandes("smecta"), pharmacies)
    assert resultat.pharmacies == ()
    assert formater_fiche(resultat) is None


# --- Rupture (D2, parcours 3) ---


def test_rupture_retire_le_produit_des_resultats(pharmacies):
    baobab = pharmacies[0]
    pharmacies[0] = replace(
        baobab,
        catalogue=tuple(
            replace(p, en_rupture=p.libelle == "Doliprane 1000 mg comprimés") for p in baobab.catalogue
        ),
    )
    resultat = par_nom(rechercher(demandes("doliprane"), pharmacies))
    assert resultat["Pharmacie Baobab"].produits == (("Doliprane 2,4 % sirop",),)


# --- Parcours 6 : noms complets lus sur l'ordonnance ---


def test_parcours_6_forme_precisee_ecarte_teranga(pharmacies):
    resultat = rechercher(
        demandes("Amoxicilline 250 mg/5 ml sirop", "Doliprane 2,4 % sirop", "Smecta"), pharmacies
    )
    noms = par_nom(resultat)
    assert noms["Pharmacie Baobab"].nombre == 2
    assert noms["Pharmacie Liberté"].nombre == 1
    assert "Pharmacie Teranga" not in noms
    assert [m.libelle for m in resultat.introuvables] == ["Smecta"]


def test_dosage_precise_doit_correspondre(pharmacies):
    resultat = rechercher(demandes("Doliprane 1000 comprimés"), pharmacies)
    assert {r.pharmacie.nom for r in resultat.pharmacies} == {"Pharmacie Baobab", "Pharmacie Teranga"}
    for r in resultat.pharmacies:
        assert r.produits == (("Doliprane 1000 mg comprimés",),)


# --- Fiche résultat (D7, D8) ---


def test_fiche_du_parcours_1(pharmacies):
    resultat = rechercher(demandes("amoxicilline sirop", "doliprane"), pharmacies, random.Random(1))
    fiche = formater_fiche(resultat)
    lignes = fiche.splitlines()
    assert lignes[0] == "Vos médicaments : Amoxicilline sirop, Doliprane"
    assert lignes[2] == "1. Pharmacie Baobab — 2 sur 2"
    assert lignes[3] == "   ✅ Amoxicilline 250 mg/5 ml sirop"
    assert lignes[4] == "   ✅ Doliprane 2,4 % sirop, Doliprane 1000 mg comprimés"
    assert lignes[5] == "   📍 Rue 10, Grand Yoff"
    assert lignes[6] == "   📞 +221 33 000 00 01"
    assert lignes[7].startswith("   🗺️ https://maps.google.com/?q=")
    assert "2. Pharmacie" in fiche and "— 1 sur 2" in fiche
    assert lignes[-1] == RAPPEL_SECURITE


def test_fiche_compte_les_introuvables_dans_le_total(pharmacies):
    resultat = rechercher(demandes("amoxicilline sirop", "doliprane", "smecta"), pharmacies)
    assert "Pharmacie Baobab — 2 sur 3" in formater_fiche(resultat)

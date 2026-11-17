# Catalogues simulés — PharmaSûr (démo)

Les médicaments disponibles dans les 4 pharmacies partenaires simulées, tels que le bot les charge au démarrage (`pharmasur/db.py`, `PHARMACIES_SIMULEES`). Vocabulaire : voir [GLOSSARY.md](GLOSSARY.md). Rôle de chaque pharmacie dans la démo : voir [PARCOURS.md](PARCOURS.md), « Données simulées ».

Au départ, aucun médicament n'est en rupture : tout ce qui figure dans un catalogue est disponible (D3). Une rupture signalée par la pharmacie (parcours 3) changerait cet état jusqu'au prochain redémarrage sur Railway ou à la prochaine remise à zéro (D35).

## Par médicament

| Médicament | Baobab | Liberté | Teranga | Jamm |
|---|:-:|:-:|:-:|:-:|
| Amoxicilline 250 mg/5 ml sirop | ✅ | ✅ | | |
| Amoxicilline 500 mg gélules | | ✅ | | |
| Clamoxyl 500 mg | | | | ✅ |
| Doliprane 1000 mg comprimés | ✅ | | ✅ | |
| Doliprane 2,4 % sirop | ✅ | | | |
| Efferalgan 500 mg | | | ✅ | |
| Mag 2 100 mg comprimés | ✅ | ✅ | | |
| Richifer gélules | ✅ | | ✅ | |
| UPSA-C 1000 mg comprimés effervescents | ✅ | | | |

## Par pharmacie

| Pharmacie | Adresse (fictive) | Catalogue |
|---|---|---|
| Pharmacie Baobab (jouée en direct) | Rue 10, Grand Yoff | Amoxicilline 250 mg/5 ml sirop, Doliprane 2,4 % sirop, Doliprane 1000 mg comprimés, Richifer gélules, Mag 2 100 mg comprimés, UPSA-C 1000 mg comprimés effervescents |
| Pharmacie Liberté | Liberté 6, Dakar | Amoxicilline 250 mg/5 ml sirop, Amoxicilline 500 mg gélules, Mag 2 100 mg comprimés |
| Pharmacie Teranga | Avenue Cheikh Anta Diop, Fann | Doliprane 1000 mg comprimés, Efferalgan 500 mg, Richifer gélules |
| Pharmacie Jamm | Sicap Amitié 2, Dakar | Clamoxyl 500 mg |

## Introuvables (dans aucun catalogue)

- **Vitamine C** de l'ordonnance de test (lue « Adnovit C » ou « Adna vit C ») : elle lance la demande d'équivalent. Baobab a l'UPSA-C, mais le bot ne le compte jamais pour la vitamine C et ne le nomme jamais (D11, D27).
- **Smecta** : l'introuvable des exemples de PARCOURS.md (parcours 2).
- **Ventoline** : le cas hors catalogue du parcours 3.

## Ce qu'il faut savoir pour les tests

- **Ordonnance de test** (Richifer, vitamine C, Mag 2) : Baobab arrive en tête avec 2 sur 3, puis Liberté et Teranga avec 1 sur 3, dans un ordre tiré au hasard (D25).
- **Un autre nom commercial n'est jamais compté** : l'Efferalgan n'apparaît pas pour « Doliprane », ni le Clamoxyl pour « amoxicilline » (D27, D28).
- **Un principe actif se cherche comme un nom** : « amoxicilline 500 mg » trouve Liberté seulement (D28).
- **Dosage et forme comptent seulement s'ils sont donnés** : « Doliprane » trouve Baobab (sirop et comprimés) et Teranga ; « Doliprane sirop » trouve seulement Baobab (D27).

---
status: accepted
---

# PharmaSûr lit les noms sur l'ordonnance, sans la garder ni la transmettre

Le dossier excluait toute réception d'ordonnance (sections 2.5, 4.4, 8.4 et 9), pour éviter d'être soupçonné d'exercice illégal de la pharmacie ou de contournement de la prescription. Mais sans photo d'ordonnance, une personne qui ne sait pas lire et qui n'a pas la boîte ne peut pas donner le nom de son médicament, et le vocal en wolof perd son sens. Nous acceptons donc la photo de l'ordonnance, uniquement pour y lire les noms des médicaments :

- la personne confirme ou corrige ce qui a été lu ;
- l'image est supprimée aussitôt après ;
- elle n'est jamais transmise aux pharmacies ;
- seul le pharmacien vérifie l'ordonnance, au comptoir.

PharmaSûr ne garde que les corrections de lecture (« smekta → Smecta »), sans image ni numéro.

## Options considérées

- **Refuser les ordonnances**, comme dans le dossier : aucun risque, mais les personnes qui ne lisent pas sont exclues.
- **Transmettre l'ordonnance aux pharmacies**, comme Sen Pharmacie : lors du test, une ordonnance mal lue a été envoyée quand même aux pharmacies. C'est aussi une fuite de données de santé.
- **Conserver les images pour améliorer la lecture** : il faudrait un consentement explicite, des extraits découpés, un masquage, du chiffrement et une démarche auprès de la CDP. Rien de cela n'est réalisable en deux jours, et une fuite serait grave. L'option pourra être reprise plus tard avec ces protections.

## Conséquences

- La décision est à faire valider par le pharmacien conseil et les juristes du groupe : les données de santé sont des données sensibles au regard de la loi sénégalaise sur les données personnelles.
- Le service de lecture d'image choisi ne doit ni conserver les images, ni s'en servir pour entraîner ses modèles.
- Les sections 2.5, 4.4, 8.4 et 9 du dossier sont à réécrire.
- Décisions liées dans [DECISIONS.md](../../DECISIONS.md) : D12, D13, D21, D22.

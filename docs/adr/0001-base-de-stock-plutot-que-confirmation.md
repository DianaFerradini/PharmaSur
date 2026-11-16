---
status: accepted
---

# Une base de stock plutôt qu'une confirmation par la pharmacie à chaque recherche

Le dossier (section 4.3) prévoyait de transmettre chaque recherche aux pharmacies, qui répondraient « oui » ou « non ». C'était même l'argument central du pitch : « personne n'a encore fait répondre les pharmacies ». Nous avons choisi l'inverse : le bot consulte une base de stock et répond tout de suite. Chaque pharmacie déclare un catalogue à son inscription, puis signale ses ruptures et ses retours en stock en texte libre. Elle n'est sollicitée que pour une demande d'équivalent, et seulement si la personne qui cherche est d'accord. La raison : faire confirmer chaque recherche ajoute du travail et de la charge mentale à un pharmacien occupé au comptoir, et fait attendre la personne.

## Options considérées

- **Une confirmation à chaque recherche**, comme dans le dossier : le stock est vérifié sur le moment, mais tout dépend de la réactivité des pharmaciens, qu'on sollicite sans cesse.
- **Une connexion aux logiciels de gestion des officines** (SenPharmacie, Stockspharma, sur le modèle de Sana) : la donnée la plus fiable, sans effort pour la pharmacie. Elle reste la cible, mais elle est impossible sans partenariats.
- **Une mise à jour par formulaire web** : trop de travail, les pharmacies ne le feraient pas.

## Conséquences

- La fiabilité des résultats dépend des signalements de rupture : un oubli de la pharmacie donne un faux « disponible ». Le résumé (D14) sert d'incitation à tenir le stock à jour.
- Plusieurs éléments du dossier sont à réécrire : les sections 4.3, 6.3 et 8.1, l'indicateur « demandes confirmées en moins de 10 minutes » (section 8.3) et la phrase de pitch du benchmark.
- Décisions liées dans [DECISIONS.md](../../DECISIONS.md) : D1, D2, D3, D10, D18.

# Vocaux en wolof — fiche d'enregistrement

Cette fiche est pour la personne de l'équipe qui parle wolof. Elle enregistre les **12 vocaux** que le bot envoie quand quelqu'un lui parle en wolof (D24 dans [DECISIONS.md](DECISIONS.md)). Comptez environ une heure.

Le bot ne sait pas parler wolof : il choisit l'un de ces enregistrements selon la situation. Chaque vocal part avec un **message écrit** qui contient les noms des médicaments et des pharmacies, les adresses et les numéros (D23). Le vocal n'a donc pas besoin de les dire, et il ne doit pas les dire.

**À faire en premier : les vocaux 3, 2 et 5.** Ce sont les seuls que le jury entendra (parcours 7 de [PARCOURS.md](PARCOURS.md)), et ils doivent être prêts pour le quart de finale du 18/11 au matin (D33).

## Les règles

1. **Aucun nom** : pas de nom de médicament ni de pharmacie, pas d'adresse, pas de prix. Vous pouvez dire « PharmaSûr », le nom du service.
2. **Rien de plus que le texte** : pas de conseil de santé, jamais de médicament proposé, et jamais l'idée qu'on peut acheter par PharmaSûr.
3. **Le sens, pas le mot à mot** : dites chaque texte en wolof de tous les jours, comme vous le diriez à une voisine. Les mots que tout le monde dit en français (pharmacie, ordonnance, SAMU) peuvent rester en français.
4. **Court** : une vingtaine de secondes par vocal, 30 au plus.
5. **Ton calme et poli** : la personne cherche souvent un médicament pour un proche malade.

## Comment enregistrer

Les vocaux s'enregistrent directement dans WhatsApp (D37).

- **Lieu** : une pièce calme, sans télé, sans ventilateur, sans bruit de rue. Gardez le téléphone à environ 20 cm de la bouche.
- **Même voix, même endroit** pour les 12 vocaux, pour que le bot ait toujours la même voix.

1. Ouvrez la conversation WhatsApp avec le membre de l'équipe qui récupère les vocaux.
2. Écrivez d'abord le numéro du vocal, en texte : par exemple `Vocal 3`.
3. Maintenez le bouton micro et dites le texte en wolof. Relâchez pour envoyer.
4. Raté ? Recommencez : réécrivez `Vocal 3`, puis renvoyez le vocal. C'est toujours le dernier envoyé qui compte.

Ne dites pas le numéro dans le vocal lui-même : la personne qui recevra le vocal l'entendrait.

## Partie 1 — Pour la démo (à faire en premier)

### 🔊 3 — Confirmation de lecture

- **Quand le bot l'envoie** : quand il a compris des noms de médicaments dans un vocal ou sur une photo. Le message écrit montre la liste des noms, avec deux boutons : ✅ pour valider et ✏️ pour corriger (D13).
- **À dire en wolof** :

  > Voici les médicaments que j'ai compris. Vérifiez-les dans le message écrit. Si c'est juste, touchez la coche verte. Sinon, touchez le crayon pour corriger.

### 🔊 2 — Accueil court

- **Quand** : la première fois qu'une personne parle au bot, si elle cherche déjà un médicament. Le vocal 5 suit aussitôt (D8).
- **À dire en wolof** :

  > Bonjour, PharmaSûr vous dit quelles pharmacies ont vos médicaments. Rien ne s'achète ici.

### 🔊 5 — Résultats

- **Quand** : le bot a trouvé des pharmacies. Le message écrit donne, pour chacune, son nom, son adresse, son téléphone et un lien d'itinéraire (D7).
- **À dire en wolof** :

  > Des pharmacies ont vos médicaments. Tous les détails sont dans le message écrit. Touchez le numéro pour appeler la pharmacie, ou le lien pour voir le chemin. Achetez uniquement en pharmacie, avec votre ordonnance.

## Partie 2 — Les autres vocaux

### 🔊 1 — Accueil complet

- **Quand** : la première fois qu'une personne parle au bot sans chercher de médicament, par exemple si elle dit seulement bonjour (D8).
- **À dire en wolof** :

  > Bonjour, je suis PharmaSûr. Je vous dis quelles pharmacies ont vos médicaments. Envoyez-moi le nom de vos médicaments, une photo de l'ordonnance ou de la boîte, ou un vocal. Rien ne s'achète ici : vous achetez en pharmacie, avec votre ordonnance.

### 🔊 4 — Photo illisible

- **Quand** : le bot n'arrive pas à lire une photo, parce qu'elle est floue ou que l'écriture est illisible (D21).
- **À dire en wolof** :

  > Je n'arrive pas à lire la photo. Reprenez-la avec plus de lumière, de plus près. Ou bien dites-moi le nom du médicament.

### 🔊 6 — Médicament introuvable

- **Quand** : un médicament n'est dans aucune pharmacie partenaire. Le message écrit donne son nom, avec deux boutons, Oui et Non (D10).
- **À dire en wolof** :

  > Ce médicament n'est disponible aujourd'hui dans aucune pharmacie partenaire. Son nom est dans le message écrit. Voulez-vous qu'on demande aux pharmacies si l'une d'elles a une solution ?

### 🔊 7 — Demande envoyée

- **Quand** : la personne a accepté qu'on interroge les pharmacies (D10, D17).
- **À dire en wolof** :

  > C'est envoyé. On a demandé aux pharmacies. Je vous préviens dès qu'une pharmacie a une solution.

### 🔊 8 — Une pharmacie a une solution

- **Quand** : une pharmacie a répondu qu'elle a une solution. Le message écrit donne son nom, son adresse et son téléphone (D11).
- **À dire en wolof** :

  > Une pharmacie a peut-être une solution. Son nom est dans le message écrit. Allez demander conseil au pharmacien.

- **Attention** : ne jamais dire quel produit la pharmacie propose. C'est le pharmacien qui le dit, au comptoir.

### 🔊 9 — Aucune solution

- **Quand** : 23 heures après la demande, aucune pharmacie n'a de solution (D17). Ce vocal n'est pas joué devant le jury.
- **À dire en wolof** :

  > Aucune pharmacie partenaire n'a de solution pour ce médicament. Demandez conseil à un pharmacien.

### 🔊 10 — Hors sujet

- **Quand** : la personne demande autre chose que l'endroit où trouver un médicament, par exemple un prix, un conseil de santé ou une commande (D9).
- **À dire en wolof** :

  > PharmaSûr indique seulement où trouver vos médicaments. Pour toute autre question, demandez à un pharmacien.

### 🔊 11 — Urgence

- **Quand** : la personne décrit une urgence (D9).
- **À dire en wolof** :

  > Urgence : appelez le SAMU au 1515, ou les sapeurs-pompiers au 18.

- **Conseil** : dites les numéros lentement, comme on les dit d'habitude, puis répétez-les une fois.

### 🔊 12 — Message non compris

- **Quand** : le bot n'a pas compris le message. Le message écrit montre un petit menu numéroté (D8).
- **À dire en wolof** :

  > Je n'ai pas compris. Choisissez une option dans le menu écrit.

## Les boutons à relire

Le bot affiche aussi des boutons sous certains messages. Dites à l'équipe si une personne qui ne lit pas le français les comprendra :

- **✅ et ✏️** : valider ou corriger la liste des médicaments compris (vocal 3). Ce sont les mêmes boutons pour tout le monde, à l'écrit comme à l'oral (D13).
- **Oui et Non** : accepter ou refuser qu'on interroge les pharmacies (vocal 6).

Si un mot wolof serait plus clair, proposez-le. Le vocal 3 parle de la coche et du crayon : si vous pensez qu'ils ne seront pas compris, dites-le avant d'enregistrer ce vocal.

## Pour la personne qui récupère les vocaux

1. Ouvrez WhatsApp Web sur l'ordinateur, puis la conversation.
2. Pour chaque numéro, prenez le **dernier** vocal envoyé après `Vocal n`. Passez la souris dessus, ouvrez le menu (la petite flèche), puis choisissez **Télécharger**. Le fichier arrive au format `.ogg`, il n'y a rien à convertir (D37).
3. Renommez-le comme dans le tableau ci-dessous, et rangez-le dans le dossier `pharmasur/vocaux/` du projet (à créer s'il n'existe pas).
4. Écoutez chaque vocal et vérifiez :
   - qu'on l'entend bien, sans bruit derrière ;
   - qu'il ne contient aucun nom de médicament ou de pharmacie, aucune adresse, aucun prix ;
   - qu'il dure 30 secondes au plus ;
   - que le sens correspond au texte de la fiche.
5. Ajoutez les fichiers au dépôt GitHub, ou passez-les à la personne qui code le bot.

| # | Situation | Nom du fichier |
|---|---|---|
| 1 | Accueil complet | `01-accueil-complet.ogg` |
| 2 | Accueil court | `02-accueil-court.ogg` |
| 3 | Confirmation de lecture | `03-confirmation-lecture.ogg` |
| 4 | Photo illisible | `04-photo-illisible.ogg` |
| 5 | Résultats | `05-resultats.ogg` |
| 6 | Médicament introuvable | `06-introuvable.ogg` |
| 7 | Demande envoyée | `07-demande-envoyee.ogg` |
| 8 | Une pharmacie a une solution | `08-solution-trouvee.ogg` |
| 9 | Aucune solution | `09-aucune-solution.ogg` |
| 10 | Hors sujet | `10-hors-sujet.ogg` |
| 11 | Urgence | `11-urgence.ogg` |
| 12 | Message non compris | `12-non-compris.ogg` |

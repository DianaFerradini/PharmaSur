# Parcours utilisateurs — PharmaSûr (démo du 17/11)

Ce document décrit les cinq parcours montrés au jury, étape par étape, avec des exemples de messages. Chaque étape renvoie à la décision qui la fonde dans [DECISIONS.md](DECISIONS.md). Le vocabulaire suit [GLOSSARY.md](GLOSSARY.md).

Les textes des messages sont des propositions. On peut les retoucher pendant la construction du bot, mais pas changer les règles qu'ils appliquent.

## Mise en scène

- **Deux téléphones** :
  - 👤 **Fatou**, la personne qui cherche. Son numéro n'est pas inscrit comme pharmacie.
  - 💊 **Pharmacie Baobab**, jouée en direct par un membre de l'équipe. Son numéro est inscrit comme pharmacie partenaire (D4).
- 🤖 **PharmaSûr** : un seul numéro WhatsApp pour tout le monde (D4).
- 🔊 **n** : le vocal préenregistré n° n de la liste D24, envoyé quand la personne parle en vocal.
- `[Oui]  [Non]` : des boutons de réponse WhatsApp. Ceux de la personne qui cherche sont des icônes : `[✅]  [✏️]` pour la confirmation de lecture (D13), `[✅]  [❌]` pour accepter ou refuser la demande d'équivalent (D10).

### Données simulées à préparer

| Pharmacie partenaire | Catalogue de départ | Rôle dans la démo |
|---|---|---|
| Pharmacie Baobab (jouée en direct) | Amoxicilline 250 mg/5 ml sirop, Doliprane 2,4 % sirop, Doliprane 1000 mg comprimés, Richifer gélules, Mag 2 100 mg comprimés, UPSA-C 1000 mg comprimés effervescents | Rupture, retour en stock, demande d'équivalent, résumé |
| Pharmacie Liberté | Amoxicilline 250 mg/5 ml sirop, Amoxicilline 500 mg gélules, Mag 2 100 mg comprimés | Ex æquo avec Teranga (D25) ; trouvée par principe actif (D28) |
| Pharmacie Teranga | Doliprane 1000 mg comprimés, Efferalgan 500 mg, Richifer gélules | L'Efferalgan n'est pas compté pour « Doliprane » (D27) |
| Pharmacie Jamm | Clamoxyl 500 mg | Le Clamoxyl n'est pas compté pour « amoxicilline » (D28) |

- Le **Smecta** n'est dans aucun catalogue : il est introuvable (parcours 2).
- **Ordonnance de test** (une vraie ordonnance manuscrite, dont la photo sert pour toute la démo) : Richifer, une vitamine C, Mag 2.
  - Richifer gélules : Baobab et Teranga. Mag 2 100 mg comprimés : Baobab et Liberté. Baobab arrive donc en tête avec 2 sur 3 (D25).
  - La vitamine C prescrite (lue « Adnovit C ») n'est dans aucun catalogue : elle est introuvable et lance la demande d'équivalent (parcours 2).
  - Baobab a l'UPSA-C 1000 mg : c'est sa solution, qu'il touche « Oui » ; le bot ne la nomme jamais (D11).
  - À la lecture de la photo, le bot lit Richifer et Adnovit C mais pas Mag 2 : la démo montre alors la lecture partielle (D21), où Fatou écrit « Mag 2 ». Une photo plus nette peut suffire à tout lire.
- La **Ventoline** n'est pas dans le catalogue de Baobab : elle sert pour le cas hors catalogue (parcours 3).
- Quelques dizaines de **recherches simulées** sont à préremplir, pour avoir des chiffres crédibles dans le résumé (D14) et le tableau de bord (D26).
- Les **12 vocaux** de D24 sont à faire enregistrer par la personne de l'équipe qui parle wolof, avec la fiche [VOCAUX.md](VOCAUX.md).
- Les noms, adresses et numéros sont fictifs, à remplacer.
- Le téléphone de Baobab doit écrire au bot peu avant la démo, pour rester dans la fenêtre WhatsApp de 24 h (D16).

---

## Parcours 1 — Recherche avec résultat

**Situation** : Fatou a l'ordonnance de son fils. Elle écrit au service pour la première fois.

1. 👤 Fatou écrit :

   ```text
   Bonjour, je cherche amoxicilline sirop et doliprane
   ```

2. 🤖 C'est un premier contact qui contient une recherche, donc le bot envoie l'**accueil court** (D8) :

   ```text
   Bonjour 👋 PharmaSûr vous dit quelles pharmacies ont vos médicaments. Rien ne s'achète ici.
   ```

3. 🤖 Il envoie ensuite les **résultats**, triés par nombre de médicaments, puis au hasard en cas d'égalité (D5, D7, D25, D27) :

   ```text
   Vos médicaments : Amoxicilline sirop, Doliprane

   1. Pharmacie Baobab — 2 sur 2
      ✅ Amoxicilline 250 mg/5 ml sirop
      ✅ Doliprane 2,4 % sirop, Doliprane 1000 mg comprimés
      📍 Rue 10, Grand Yoff
      📞 +221 33 000 00 01
      🗺️ https://maps.google.com/?q=...

   2. Pharmacie Liberté — 1 sur 2
      ✅ Amoxicilline 250 mg/5 ml sirop
      📍 …  📞 …  🗺️ …

   3. Pharmacie Teranga — 1 sur 2
      ✅ Doliprane 1000 mg comprimés
      📍 …  📞 …  🗺️ …

   ⚠️ Achetez uniquement en pharmacie, avec votre ordonnance.
   ```

**Règles appliquées** :

- « Doliprane » est donné sans dosage, donc tous les dosages et toutes les formes de Doliprane comptent, et la fiche indique lesquels chaque pharmacie a (D27). L'Efferalgan de Teranga n'est pas compté.
- Liberté et Teranga sont ex æquo : leur ordre change d'une recherche à l'autre (D25).
- Le bot ne demande pas la position : toutes les pharmacies qui ont au moins un des médicaments apparaissent (D6).

**Variantes** :

- Si Fatou n'envoie que « Bonjour », elle reçoit l'**accueil complet** (D8, ou 🔊 1 si elle parle en vocal) :

  ```text
  Bonjour 👋 Je suis PharmaSûr. Je vous dis quelles pharmacies ont vos médicaments.
  Envoyez-moi le nom de vos médicaments, une photo de l'ordonnance ou de la boîte, ou un vocal.
  Rien ne s'achète ici : vous achetez en pharmacie, avec votre ordonnance.
  ```

- Si Fatou est déjà venue, le bot la salue puis donne les résultats, sans accueil (D8).
- Pour une recherche par principe actif, « amoxicilline 500 mg » trouve les « Amoxicilline 500 mg gélules » de Liberté. Le Clamoxyl de Jamm n'est pas compté (D28).

---

## Parcours 2 — Médicament introuvable et demande d'équivalent

**Situation** : la même ordonnance contient aussi du Smecta, qu'aucune pharmacie partenaire n'a.

1. 👤 Fatou écrit :

   ```text
   amoxicilline sirop, doliprane, smecta
   ```

2. 🤖 Le bot envoie les résultats pour les deux médicaments trouvés, comme au parcours 1.
3. 🤖 Puis il envoie un second message (D10, 🔊 6) :

   ```text
   🚫 Smecta : introuvable aujourd'hui dans les pharmacies partenaires.
   Voulez-vous qu'on demande aux pharmacies si l'une d'elles a une solution ?
   [✅]  [❌]
   ```

4. 👤 Fatou touche ✅.
5. 🤖 Le bot confirme l'envoi (🔊 7) :

   ```text
   C'est envoyé ✅ Je vous préviens dès qu'une pharmacie a une solution.
   ```

6. 💊 Toutes les pharmacies partenaires reçoivent la **demande d'équivalent**. Elle ne contient rien sur la personne (D15, D16, D17) :

   ```text
   🔎 Une personne cherche : Smecta.
   Introuvable aujourd'hui dans le réseau. Avez-vous une solution ?
   [Oui, j'ai une solution]  [Non]
   ```

7. 💊 Baobab touche **Oui, j'ai une solution**. 🤖 Le bot lui répond :

   ```text
   Merci ✅ La personne va être prévenue.
   ```

8. 🤖 Fatou est prévenue aussitôt (D11, D17, 🔊 8) :

   ```text
   💡 La Pharmacie Baobab a peut-être une solution pour le Smecta.
   Allez demander conseil au pharmacien.
   📍 Rue 10, Grand Yoff
   📞 +221 33 000 00 01
   🗺️ https://maps.google.com/?q=...
   ```

   Le nom du produit proposé n'est jamais donné : c'est le pharmacien qui le propose, au comptoir.

**Suite et variantes** :

- Chaque « Oui » suivant est transmis à Fatou dès qu'il arrive, pendant 23 heures (D17).
- Une pharmacie qui ne touche rien compte comme un « non » (D16).
- Si personne n'a dit « Oui » au bout de 23 heures, Fatou reçoit ce message (🔊 9, non montré au jury) :

  ```text
  Aucune pharmacie partenaire n'a de solution pour le Smecta. Demandez conseil à un pharmacien.
  ```

- Si Fatou touche ❌, rien n'est envoyé aux pharmacies.
- Quand la demande est close, le lien entre le numéro de Fatou et la demande est effacé (D15).

---

## Parcours 3 — Côté pharmacie : rupture, retour en stock, résumé

Tout se passe sur le téléphone de la Pharmacie Baobab, en texte libre (D18).

### Rupture

1. 💊 Le pharmacien écrit :

   ```text
   plus de doliprane 1000
   ```

2. 🤖 Le bot est sûr d'avoir compris : il applique le changement et accuse réception (D19).

   ```text
   ✅ Doliprane 1000 mg comprimés noté en rupture.
   ```

3. Effet visible : si Fatou relance une recherche de Doliprane, Baobab n'affiche plus que le Doliprane 2,4 % sirop.

### Message ambigu

1. 💊 Le pharmacien écrit :

   ```text
   dolipran sirop fini
   ```

2. 🤖 Le nom est approximatif, donc le bot demande confirmation (D19) :

   ```text
   Vous voulez dire : Doliprane 2,4 % sirop en rupture ?
   [Oui]  [Non]
   ```

### Médicament hors catalogue

1. 💊 Le pharmacien écrit :

   ```text
   Ventoline de nouveau disponible
   ```

2. 🤖 Le médicament est hors catalogue, donc le bot demande toujours confirmation (D20) :

   ```text
   La Ventoline n'est pas dans votre catalogue.
   L'ajouter comme disponible ?
   [Oui]  [Non]
   ```

3. 💊 Le pharmacien touche **Oui**. 🤖 Le bot répond :

   ```text
   ✅ Ventoline ajoutée à votre catalogue, disponible.
   ```

### Retour en stock

1. 💊 Le pharmacien écrit :

   ```text
   le doliprane 1000 est revenu
   ```

2. 🤖 Le bot répond :

   ```text
   ✅ Doliprane 1000 mg comprimés de nouveau disponible.
   ```

### Résumé

1. 💊 Le pharmacien écrit :

   ```text
   résumé
   ```

2. 🤖 Le bot envoie le résumé, seulement parce qu'il l'a demandé (D14) :

   ```text
   📊 Votre semaine avec PharmaSûr
   • Vous êtes apparu dans 37 résultats de recherche.
   • Demande manquée :
     – Smecta : 12 recherches
     – Spasfon : 8 recherches
   ```

L'option qui ajouterait une ligne « introuvables chez toutes les pharmacies partenaires » sera tranchée pendant la construction (voir [DECISIONS.md](DECISIONS.md)).

---

## Parcours 6 — Recherche par photo

**Situation** : Fatou photographie l'ordonnance de son fils.

1. 👤 Fatou envoie la photo de l'ordonnance.
2. 🤖 Le bot envoie la **confirmation de lecture** (D12, D13) :

   ```text
   J'ai lu sur votre photo :
   1. Amoxicilline 250 mg/5 ml sirop
   2. Doliprane 2,4 % sirop
   3. Smecta
   C'est bien ça ?
   [✅]  [✏️]
   ```

3. 👤 Fatou touche ✅. L'image est supprimée (D22), puis la recherche continue :
   - Baobab a 2 médicaments sur 3 et Liberté 1 sur 3.
   - Teranga n'apparaît pas : la forme « sirop » est précisée, et elle n'a que des comprimés (D27).
   - Le Smecta est introuvable, donc la suite est celle du parcours 2.

**Variantes** :

- **Corriger** (✏️) : le bot demande le bon nom.

  ```text
  Écrivez ou dites le bon nom.
  ```

  Fatou répond « Smecta ». Seule la **correction de lecture** « smekta → Smecta » est gardée, sans image ni numéro (D22).

- **Photo illisible** (D21, 🔊 4) :

  ```text
  Je n'arrive pas à lire la photo.
  📸 Reprenez-la avec plus de lumière, de plus près, bien à plat,
  ✍️🎤 ou écrivez ou dites le nom du médicament.
  ```

- **Lecture partielle** (D21) : la confirmation montre les noms lus, puis ajoute :

  ```text
  ⚠️ Un médicament n'a pas pu être lu : reprenez la photo, ou écrivez ou dites son nom.
  ```

---

## Parcours 7 — Recherche par vocal en wolof

**Situation** : Fatou envoie un vocal en wolof. Pour la démo, ce vocal est répété à l'avance, parce que la transcription du wolof se trompe sur environ 40 % des mots.

1. 👤 Fatou envoie un vocal en wolof, où elle cite l'amoxicilline en sirop et le Doliprane.
2. 🤖 Le bot répond par le 🔊 3 (« vérifiez les noms écrits »), accompagné de la **confirmation de lecture** écrite (D13, D23, D24) :

   ```text
   1. Amoxicilline sirop
   2. Doliprane
   [✅]  [✏️]
   ```

3. 👤 Fatou touche ✅.
4. 🤖 Le bot envoie le 🔊 2 (accueil court, puisque c'est un premier contact), puis le 🔊 5 (résultats), accompagnés de la **fiche écrite** du parcours 1 (D23).

Le vocal ne prononce jamais de nom de pharmacie ni de médicament : ces noms sont dans la fiche écrite (D23). Les libellés des boutons sont des icônes et des mots simples, à faire relire par la personne de l'équipe qui parle wolof.

---

## Messages communs à tous les parcours

- **Hors sujet** (D9, 🔊 10) :

  ```text
  PharmaSûr indique seulement où trouver vos médicaments. Pour toute autre question, demandez à un pharmacien.
  ```

- **Urgence** (D9, 🔊 11) :

  ```text
  🚨 Urgence : appelez le SAMU au 1515 ou les sapeurs-pompiers au 18.
  ```

- **Message non compris** (D8, 🔊 12). Le contenu du menu reste à ajuster :

  ```text
  Je n'ai pas compris 🙏 Répondez avec un chiffre :
  1. Chercher un médicament
  2. Comment ça marche
  ```

---

## Enchaînement proposé pour le jury

Une proposition, à répéter avant le passage :

1. 💊 **Baobab signale une rupture en une phrase** (parcours 3). Le jury voit que le pharmacien n'a presque rien à faire.
2. 👤 **Fatou envoie la photo de l'ordonnance**. Le bot confirme la lecture, puis donne les résultats (parcours 6 et 1).
3. **Le Smecta est introuvable**. Fatou accepte la demande d'équivalent, 💊 Baobab touche « Oui », et Fatou est prévenue (parcours 2). C'est le moment fort, avec les deux téléphones.
4. 👤 **Recherche par vocal en wolof** : le bot répond par un vocal, accompagné de la fiche écrite (parcours 7).
5. 💊 **Baobab écrit « résumé »**. Phrase de pitch : « On ne vous vend pas de la visibilité, on vous montre les clients que vous ratez. » (D14)
6. Si elle est prête : **la page de présentation avec son QR code**, puis le tableau de bord (D26).

Si le parcours 3 n'est pas prêt (D33), on saute les étapes 1 et 5 : l'enchaînement va de la photo de l'ordonnance au vocal en wolof.

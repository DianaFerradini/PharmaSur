# Décisions — PharmaSûr

Journal des décisions prises pendant la conception des parcours utilisateurs. Mis à jour après chaque décision.
Vocabulaire : voir [GLOSSARY.md](GLOSSARY.md).

_Dernière mise à jour : 16 novembre 2026_

## Contexte

- **Objectif** : présenter une démo à un jury de concours. Le build se fait en deux jours, les 16 et 17 novembre 2026.
- **Priorité** : le bot WhatsApp.
- **Pharmacies** : il n'y aura sans doute pas de vraies pharmacies partenaires. Le stock et les pharmacies sont simulés, et un membre de l'équipe joue le pharmacien sur son téléphone.
- **Page web** : le 17 novembre, s'il reste du temps. **Pas d'USSD.**
- **Sources** : [presentation_projet.pdf](presentation_projet.pdf) (le dossier) et [Benchmark concurrentiel — PharmaSûr.pdf](<Benchmark concurrentiel — PharmaSûr.pdf>).
- **Lecture** : chaque décision précise la **version démo** et, quand elle diffère, la **cible** (le service réel).

## Principes

- PharmaSûr **informe seulement**. Il ne vend pas, ne conseille pas, et ne propose ni ne nomme jamais un médicament à la place d'un autre.
- Le bot **reste dans son périmètre**. Il ne propose rien que la personne n'a pas demandé (par exemple, pas de « refaire la même recherche que le mois dernier »).
- **Ne pas charger les pharmaciens**. Ils sont au travail : on les sollicite seulement dans des cas précis, et chaque action de leur part doit tenir en quelques gestes.

## Parcours retenus pour la démo

| # | Parcours | Qui |
|---|---|---|
| 1 | Recherche avec résultat | Personne qui cherche |
| 2 | Recherche introuvable, puis demande d'équivalent | Personne qui cherche et pharmacie |
| 3 | Rupture et retour en stock, plus le résumé | Pharmacie |
| 6 | Recherche par photo (boîte ou ordonnance) | Personne qui cherche |
| 7 | Recherche par vocal en wolof | Personne qui cherche |

Ne sont pas dans la démo : l'inscription d'une pharmacie (le catalogue est simulé) et la recherche hors zone. La page web est prévue le 17/11 s'il reste du temps.

## Stock et pharmacies

### D1 — Le bot consulte une base de stock

- **Décision** : le bot consulte une base de stock et répond tout de suite. La pharmacie n'est sollicitée que pour une demande d'équivalent.
- **Pourquoi** : faire confirmer chaque recherche par un pharmacien lui ajoute du travail et de la charge mentale pendant qu'il sert ses clients.
- **Changement par rapport au dossier** : le dossier (section 4.3) prévoyait que chaque recherche soit confirmée par la pharmacie.

### D2 — Le stock est un oui/non mis à jour par message

- **Démo** : le stock est un oui/non par médicament, sans quantité. La pharmacie écrit au bot « [médicament] pas disponible » (rupture), puis « [médicament] de nouveau disponible » (retour en stock).
- **Cible** : connexion aux logiciels de gestion des officines (SenPharmacie, Stockspharma, sur le modèle de Sana). Pas de partenaires possibles en deux jours.
- **Écarté** : un formulaire web de mise à jour du stock, trop de travail pour les pharmacies.

### D3 — Chaque pharmacie déclare un catalogue

- **Décision** : à son inscription, la pharmacie déclare les médicaments qu'elle tient habituellement. Un médicament du catalogue est disponible, sauf rupture signalée. Hors catalogue, la disponibilité est inconnue.
- **Démo** : les catalogues sont simulés.

### D4 — Un seul numéro WhatsApp

- **Décision** : un seul numéro pour tout le monde. Le bot reconnaît les pharmacies inscrites à leur numéro de téléphone ; tout autre numéro est traité comme une personne qui cherche.
- **Pourquoi** : un seul bot à brancher et à tester, une identification fiable (WhatsApp garantit le numéro de l'expéditeur) et une démo plus simple à raconter.
- **Limite acceptée** : depuis le téléphone d'une pharmacie, on ne peut pas faire de recherche.

## Recherche (parcours 1)

### D5 — Une recherche peut porter sur plusieurs médicaments

- **Décision** : une recherche peut contenir plusieurs médicaments, souvent ceux d'une même ordonnance. Le bot indique, pharmacie par pharmacie, lesquels elle a. « Introuvable » se juge médicament par médicament.

### D6 — Position de la personne

- **Démo** : le bot ne demande pas la position. Il montre toutes les pharmacies inscrites qui ont les médicaments, et la personne choisit.
- **Cible** : la personne donne son quartier ou partage sa position WhatsApp, au choix.

### D7 — Ce que contient un résultat

- **Démo** : pour chaque pharmacie, son nom, son adresse, son téléphone, un lien d'itinéraire et les médicaments de la liste qu'elle a.
- **Cible** : en plus, les horaires (ouverte ou fermée) et l'indication « de garde ».
- **Pourquoi** : stocker et tenir à jour les horaires et les gardes sort du périmètre de la démo.

### D8 — Premier message et accueil

- **Décision** :
  - Si une personne écrit pour la première fois sans faire de recherche (par exemple « Bonjour »), elle reçoit l'**accueil complet** : ce que fait PharmaSûr, comment envoyer sa recherche, et le fait que rien ne s'achète ici.
  - Si elle écrit pour la première fois avec une recherche, elle reçoit un **accueil court** (une ou deux lignes), puis les résultats.
  - Si le numéro est déjà venu, elle reçoit une salutation et la réponse directe.
- **Pour toutes les réponses** :
  - un **rappel de sécurité** en bas de chaque réponse : « Achetez uniquement en pharmacie, avec votre ordonnance » ;
  - un **menu numéroté** seulement en filet de sécurité, quand le bot ne comprend pas le message.
- **Écarté** : un menu au premier contact, peu naturel et mal adapté au vocal.

### D9 — Messages hors sujet

- **Démo** : une réponse unique qui renvoie vers un pharmacien, sauf pour une **urgence**, à laquelle le bot répond par un numéro d'urgence (à vérifier).
- **Cible** : une réponse adaptée à chaque cas. Une question de santé renvoie vers le pharmacien ou le médecin, une question de prix vers la pharmacie, une demande de commande reçoit un non clair, et une urgence reçoit un numéro d'urgence.

## Médicament introuvable (parcours 2)

### D10 — Demande d'équivalent avec l'accord de la personne

- **Décision** : le bot répond tout de suite pour les médicaments trouvés et signale ceux qui sont introuvables. Il propose ensuite d'interroger les pharmacies pour un équivalent, et n'envoie la demande d'équivalent que si la personne est d'accord.

### D11 — Le bot ne nomme jamais l'équivalent

- **Décision** : quand une pharmacie a une solution, le bot transmet seulement le nom de la pharmacie : « La pharmacie X a peut-être une solution pour [médicament] : allez demander conseil au pharmacien. » Il ne donne jamais le nom du produit.
- **Pourquoi** : c'est plus sûr, et ça s'éloigne de l'exercice de la pharmacie, que PharmaSûr ne pratique pas.

### D16 — La pharmacie répond d'un geste, son silence vaut non

- **Décision** : la demande d'équivalent arrive avec des boutons de réponse (par exemple « Oui, j'ai une solution » et « Non »). Le pharmacien touche un bouton ; tant qu'il ne touche rien, sa réponse compte comme un non.
- **Pourquoi** : un seul geste quand il a une solution, et aucune action exigée sinon. Ça respecte le principe de ne pas charger les pharmaciens.

### D17 — Les « oui » sont transmis au fil de l'eau, pendant 23 heures

- **Décision** : la demande d'équivalent reste ouverte 23 heures. Chaque fois qu'une pharmacie touche « Oui », la personne est prévenue tout de suite. Si aucune pharmacie n'a dit oui au bout de 23 heures, le bot lui dit qu'aucune pharmacie partenaire n'a de solution et l'oriente vers un pharmacien.
- **Démo** : toutes les pharmacies partenaires reçoivent la demande, puisque le bot ne demande pas la position (D6). Le message de fin de délai ne sera pas montré.
- **Pourquoi 23 heures** : un délai court laisserait trop peu de temps aux pharmaciens pour répondre. Et WhatsApp n'autorise un message libre que dans les 24 heures qui suivent le dernier message de la personne : 23 heures garantit que le message de fin de délai passe.
- **Écarté** : un seul message à la fin du délai (trop lent si la personne est pressée) et un récapitulatif des « oui » suivants (l'information arriverait parfois 20 heures après).

## Photo (parcours 6)

### D12 — La photo d'ordonnance est acceptée

- **Décision** : la recherche par photo accepte l'ordonnance aussi bien que la boîte. Le bot y lit les noms des médicaments ; seul le pharmacien vérifie l'ordonnance.
- **Pourquoi** : sans ça, les personnes qui ne savent pas lire et n'ont pas de boîte sont exclues, et le vocal wolof perd son sens.
- **Changement par rapport au dossier** : les sections 2.5, 4.4, 8.4 et 9 disent que le service ne reçoit pas d'ordonnance.

### D13 — Confirmation de lecture

- **Décision** : avant la recherche, la personne valide ou corrige les noms lus sur sa photo. La confirmation se fait à l'écrit si elle écrit, à l'oral si elle parle.
- **Réserve** : la confirmation à l'oral n'est peut-être pas faisable en deux jours.

## Pharmacie (parcours 3)

### D14 — Le résumé de la pharmacie

- **Décision** : la pharmacie écrit « résumé » et reçoit deux chiffres : le nombre de résultats où elle est apparue, et sa **demande manquée** (les médicaments recherchés qu'elle n'avait pas, avec le nombre de recherches pour chacun). Le résumé n'est envoyé que sur demande, sans notification.
- **Démo** : des recherches simulées sont préremplies pour avoir des chiffres crédibles.
- **Cible** : un envoi automatique chaque semaine, en option.
- **Pourquoi** : c'est l'argument de vente auprès des pharmacies. Phrase de pitch : « On ne vous vend pas de la visibilité, on vous montre les clients que vous ratez. »

## Données

### D15 — Ce que PharmaSûr conserve

- **Décision** :
  - Du numéro de la personne, PharmaSûr garde seulement **le numéro et la date du premier contact**, pour savoir s'il doit envoyer l'accueil.
  - Les recherches sont conservées **sans lien avec le numéro** : médicaments cherchés, introuvables, date, et pharmacies qui avaient chaque médicament.
  - Le lien entre le numéro et une demande d'équivalent en cours est effacé dès que la demande est close, au plus tard après 23 heures (D17).
- **Écarté** : un historique des recherches par personne, qui lierait des données de santé à quelqu'un.

## Options en suspens

- **« Introuvables partout » dans le résumé** : une ligne comme « Introuvables chez toutes les pharmacies partenaires : Smecta (12 recherches) ». L'option est valable et sera tranchée pendant l'implémentation. Condition : une formulation neutre, jamais d'incitation à s'approvisionner, et une vérification par les juristes du groupe.

## Éléments techniques

- **Vocal wolof** : la transcription est possible avec Google Cloud Speech-to-Text (wo-SN) ou ElevenLabs Scribe, mais elle se trompe sur environ 40 % des mots. Aucune API hébergée ne fait parler le bot en wolof : il existe seulement des modèles ouverts à installer, de qualité inconnue. Solution de repli pour la démo : des vocaux préenregistrés.
- **Boutons et fenêtre de 24 h** : WhatsApp n'autorise un message libre (avec boutons) envoyé à l'initiative du bot que dans les 24 h qui suivent le dernier message de la personne. Au-delà, il faut un modèle de message validé à l'avance par Meta, qui peut aussi contenir des boutons. Pour la démo, le téléphone qui joue la pharmacie aura écrit au bot peu avant, donc aucun modèle n'est nécessaire. À vérifier selon l'outil utilisé.

## Questions ouvertes

- Parcours 3 : quel format exact pour les messages de rupture et de retour en stock ? Que se passe-t-il pour le retour en stock d'un médicament hors catalogue ?
- Parcours 6 : que faire si la photo est illisible ou si un nom est mal lu ? L'image de l'ordonnance est-elle conservée ou transmise ?
- Parcours 7 : pour la démo, la voix du bot vient-elle d'un modèle ouvert ou de vocaux préenregistrés ?
- Dans quelle langue répond le bot : la même que la personne, en français ou en wolof ?
- Dans quel ordre présenter les pharmacies dans les résultats ?
- Page web : pour qui, et pour quoi faire ?
- Quels numéros d'urgence donner au Sénégal ?

## À reprendre dans le dossier

- **Sections 4.3, 6.3 et 8.1, et phrase de pitch du benchmark** : l'argument « la pharmacie confirme » est remplacé par la base de stock (D1).
- **Section 8.3** : l'indicateur « demandes confirmées en moins de 10 minutes » ne s'applique plus.
- **Sections 2.5, 4.4, 8.4 et 9** : l'ordonnance est acceptée pour lire les noms des médicaments (D12).
- **Modèle économique** : ajouter le résumé comme argument de vente auprès des pharmacies (D14).

## ADR à rédiger en fin de session

- La base de stock à la place d'une confirmation par la pharmacie à chaque recherche (D1).
- L'acceptation de l'ordonnance (D12).

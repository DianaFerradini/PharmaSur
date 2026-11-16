# PharmaSûr

Service WhatsApp qui indique à une personne quelle pharmacie partenaire proche a son médicament en stock. Il informe seulement : il ne vend pas, ne conseille pas et ne propose jamais un médicament à la place d'un autre.

## Langage

### Recherche

**Recherche** :
La question posée au service : « quelles pharmacies proches ont ces médicaments ? ». Elle porte sur un ou plusieurs médicaments, souvent ceux d'une même ordonnance.
_À éviter_ : Demande, requête, commande

**Ordonnance** :
Prescription écrite qui liste les médicaments du patient. PharmaSûr peut y lire les noms des médicaments pour lancer une recherche ; seul le pharmacien la vérifie.
_À éviter_ : Prescription, papier du médecin

**Confirmation de lecture** :
Étape où la personne valide ou corrige les noms de médicaments que PharmaSûr a lus sur sa photo, avant la recherche, à l'écrit ou à l'oral selon la façon dont elle écrit au service.
_À éviter_ : Confirmation (seul), validation

**Correction de lecture** :
Couple formé par un nom de médicament mal lu par PharmaSûr et le nom corrigé par la personne pendant la confirmation de lecture (par exemple « smekta → Smecta »). C'est la seule trace qui reste d'une photo.
_À éviter_ : Erreur de lecture, feedback

**Introuvable** :
Se dit d'un médicament d'une recherche qu'aucune pharmacie partenaire n'a en stock.
_À éviter_ : Rupture générale, indisponible partout

### Conversation

**Accueil** :
Présentation de PharmaSûr envoyée au premier message d'un numéro jamais vu : ce que fait le service, comment l'utiliser et le fait que rien ne s'achète ici. Courte si ce premier message contient déjà une recherche.
_À éviter_ : Bienvenue, onboarding, introduction

**Rappel de sécurité** :
Ligne présente dans chaque réponse à une recherche, qui rappelle d'acheter uniquement en pharmacie, avec son ordonnance.
_À éviter_ : Avertissement, disclaimer, mention légale

**Hors sujet** :
Message qui n'est ni une salutation, ni une recherche, ni un échange avec une pharmacie : question de santé, de prix, de commande ou sans rapport. PharmaSûr y répond sans jamais donner de conseil et renvoie vers un pharmacien.
_À éviter_ : Question annexe, demande non gérée

**Urgence** :
Message hors sujet qui décrit une situation médicale grave et immédiate. PharmaSûr y répond à part, en donnant un numéro d'urgence.
_À éviter_ : Alerte, cas grave

### Pharmacies

**Pharmacie partenaire** :
Pharmacie agréée qui fait partie du réseau PharmaSûr et dont le stock est consulté lors des recherches.
_À éviter_ : Officine, pharmacie inscrite

**Catalogue** :
Les médicaments qu'une pharmacie partenaire tient habituellement. Ils sont déclarés à son inscription, puis complétés chaque fois qu'elle signale un médicament qui n'y figurait pas. Hors catalogue, PharmaSûr ne sait pas si la pharmacie a le médicament.
_À éviter_ : Liste de départ, assortiment, référentiel

**Stock** :
Pour chaque médicament du catalogue, le fait qu'une pharmacie partenaire l'ait ou non au moment d'une recherche : disponible, sauf rupture signalée. C'est un oui ou un non, jamais une quantité.
_À éviter_ : Disponibilité, inventaire, quantité

**Rupture** :
État d'un médicament qu'une pharmacie partenaire a signalé comme non disponible chez elle.
_À éviter_ : Manque, épuisé

**Retour en stock** :
Signalement par lequel une pharmacie partenaire indique qu'un médicament en rupture est de nouveau disponible.
_À éviter_ : Réapprovisionnement, réassort

**Équivalent** :
Médicament qui a le même principe actif que celui recherché. Seul un pharmacien peut le proposer, au comptoir ; PharmaSûr ne le suggère ni ne le nomme jamais.
_À éviter_ : Générique, substitut, alternative

**Résumé** :
Bilan qu'une pharmacie partenaire obtient sur demande : combien de fois elle est apparue dans les résultats, et sa demande manquée. Il ne contient que des chiffres, jamais l'identité d'une personne.
_À éviter_ : Rapport, tableau de bord, statistiques

**Demande manquée** :
Pour une pharmacie partenaire, les médicaments recherchés qu'elle n'avait pas au moment de la recherche, hors catalogue ou en rupture, avec le nombre de recherches pour chacun.
_À éviter_ : Ventes perdues, demande non satisfaite

**Demande d'équivalent** :
Message que PharmaSûr envoie aux pharmacies partenaires, avec l'accord de la personne qui cherche, quand un médicament recherché est introuvable, pour savoir si l'une d'elles a un équivalent.
_À éviter_ : Notification, alerte pharmacie

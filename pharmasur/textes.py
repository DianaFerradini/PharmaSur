"""Textes envoyés par le bot, repris de PARCOURS.md.

On peut retoucher les formulations ici sans toucher au reste du code, mais pas
changer les règles qu'elles appliquent (voir DECISIONS.md).
"""

# D8 : rappel de sécurité en bas de chaque réponse à une recherche.
RAPPEL_SECURITE = "⚠️ Achetez uniquement en pharmacie, avec votre ordonnance."

# D8 : accueil court (premier message qui contient une recherche).
ACCUEIL_COURT = "Bonjour 👋 PharmaSûr vous dit quelles pharmacies ont vos médicaments. Rien ne s'achète ici."

# D8 : accueil complet (premier message sans recherche).
ACCUEIL_COMPLET = (
    "Bonjour 👋 Je suis PharmaSûr. Je vous dis quelles pharmacies ont vos médicaments.\n"
    "Envoyez-moi le nom de vos médicaments, une photo de l'ordonnance ou de la boîte, ou un vocal.\n"
    "Rien ne s'achète ici : vous achetez en pharmacie, avec votre ordonnance."
)

# D8 : menu de secours quand le bot ne comprend pas (contenu encore à ajuster).
NON_COMPRIS = "Je n'ai pas compris 🙏 Répondez avec un chiffre :\n1. Chercher un médicament\n2. Comment ça marche"

# D8 : salutation d'un numéro déjà venu, sans médicament, ou choix 1 du menu.
INVITATION = "Envoyez-moi le nom de vos médicaments, une photo de l'ordonnance ou de la boîte, ou un vocal."
SALUTATION_RETOUR = "Bonjour 👋 " + INVITATION

# D8 : salutation avant les résultats d'un numéro déjà venu.
SALUTATION = "Bonjour 👋"

# D9 : message hors sujet (🔊 10).
HORS_SUJET = "PharmaSûr indique seulement où trouver vos médicaments. Pour toute autre question, demandez à un pharmacien."

# D9 : urgence (🔊 11).
URGENCE = "🚨 Urgence : appelez le SAMU au 1515 ou les sapeurs-pompiers au 18."

# D5, D10 : première ligne du message sur un médicament introuvable (parcours 2).
INTROUVABLE = "🚫 {medicament} : introuvable aujourd'hui dans les pharmacies partenaires."

# --- Parcours 6 : recherche par photo ---

# D13 : confirmation de lecture.
LECTURE_INTRO = "J'ai lu sur votre photo :"
LECTURE_INTRO_CORRIGEE = "Voici votre liste corrigée :"
LECTURE_QUESTION = "C'est bien ça ?"
BOUTON_LECTURE_OUI = "✅ Oui"
BOUTON_LECTURE_CORRIGER = "✏️ Corriger"

# D21 : lecture partielle, ajoutée sous les noms lus.
LECTURE_PARTIELLE_UN = "⚠️ Un médicament n'a pas pu être lu : reprenez la photo, ou écrivez ou dites son nom."
LECTURE_PARTIELLE_PLUSIEURS = (
    "⚠️ {nombre} médicaments n'ont pas pu être lus : reprenez la photo, ou écrivez ou dites leur nom."
)

# D13 : après « Corriger ».
DEMANDE_CORRECTION = "Écrivez ou dites le bon nom."

# D21 : photo illisible (🔊 4).
PHOTO_ILLISIBLE = (
    "Je n'arrive pas à lire la photo.\n"
    "📸 Reprenez-la avec plus de lumière, de plus près, bien à plat,\n"
    "✍️🎤 ou écrivez ou dites le nom du médicament."
)

# --- Provisoires, en attendant la construction des parcours ---
PROVISOIRE_PHOTO = "📸 Photo bien reçue. La recherche par photo arrive très bientôt."
PROVISOIRE_VOCAL = "🎤 Vocal bien reçu. La recherche par vocal arrive très bientôt."
PROVISOIRE_PHARMACIE = "✅ Message reçu, {pharmacie}. Les signalements de rupture arrivent très bientôt."

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

# D5, D10 : première ligne du message sur un médicament introuvable (parcours 2).
INTROUVABLE = "🚫 {medicament} : introuvable aujourd'hui dans les pharmacies partenaires."

# --- Provisoires, en attendant la construction des parcours ---
PROVISOIRE_PHOTO = "📸 Photo bien reçue. La recherche par photo arrive très bientôt."
PROVISOIRE_VOCAL = "🎤 Vocal bien reçu. La recherche par vocal arrive très bientôt."
PROVISOIRE_PHARMACIE = "✅ Message reçu, {pharmacie}. Les signalements de rupture arrivent très bientôt."

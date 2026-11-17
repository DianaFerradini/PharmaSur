"""Serveur web du bot (D34).

Lancer en local : uvicorn pharmasur.app:app --reload --port 8000
"""

from __future__ import annotations

import asyncio
import functools
import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import BackgroundTasks, FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from . import db
from .bot import traiter_message
from .equivalent import traiter_echeances
from .config import Config, charger_config
from .ia import creer_analyseur, creer_client, creer_lecteur
from .whatsapp import Fournisseur, MessageRecu
from .whatsapp.meta import FournisseurMeta

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s : %(message)s")
log = logging.getLogger(__name__)

Traitement = Callable[[MessageRecu, Fournisseur, str], None]

INTERVALLE_ECHEANCES = 60  # secondes (D36)


def creer_fournisseur(config: Config) -> Fournisseur:
    return FournisseurMeta(
        token=config.whatsapp_token,
        phone_number_id=config.whatsapp_phone_number_id,
        verify_token=config.whatsapp_verify_token,
        app_secret=config.whatsapp_app_secret,
        api_version=config.whatsapp_api_version,
    )


def creer_app(
    config: Config | None = None,
    fournisseur: Fournisseur | None = None,
    traitement: Traitement = traiter_message,
) -> FastAPI:
    config = config or charger_config()
    fournisseur = fournisseur or creer_fournisseur(config)
    if traitement is traiter_message:
        # Claude comprend les messages et lit les photos si une clé Anthropic est fournie ;
        # sinon, repli provisoire.
        client = creer_client(config)
        analyseur = creer_analyseur(config, client)
        lecteur = creer_lecteur(config, client)
        if analyseur is None:
            log.warning("ANTHROPIC_API_KEY est vide : le bot découpe les messages sans IA.")
        traitement = functools.partial(traiter_message, analyseur=analyseur, lecteur=lecteur)

    @asynccontextmanager
    async def cycle_de_vie(_: FastAPI):
        # D35 : la base est créée avec les données simulées si elle n'existe pas.
        db.initialiser(config.db_path, config.numero_pharmacie_baobab)
        # D36 : les demandes d'équivalent échues sont closes, vérification chaque minute.
        boucle = asyncio.create_task(verifier_echeances())
        try:
            yield
        finally:
            boucle.cancel()

    async def verifier_echeances() -> None:
        while True:
            try:
                await asyncio.to_thread(traiter_echeances, config.db_path, fournisseur)
            except Exception:
                log.exception("Vérification des demandes d'équivalent échues impossible")
            await asyncio.sleep(INTERVALLE_ECHEANCES)

    app = FastAPI(title="PharmaSûr", lifespan=cycle_de_vie)

    @app.get("/")
    def sante() -> dict[str, str]:
        return {"statut": "ok"}

    @app.get("/webhook")
    def verifier_webhook(request: Request) -> Response:
        reponse = fournisseur.verifier_abonnement(dict(request.query_params))
        if reponse is None:
            return PlainTextResponse("Jeton de vérification invalide", status_code=403)
        return PlainTextResponse(reponse)

    @app.post("/webhook")
    async def recevoir_webhook(request: Request, taches: BackgroundTasks) -> Response:
        corps = await request.body()
        entetes = dict(request.headers)
        if not fournisseur.verifier_requete(corps, entetes):
            log.warning("Requête rejetée : signature absente ou invalide")
            return PlainTextResponse("Signature invalide", status_code=401)
        # Réponse immédiate ; chaque message est traité après l'envoi de la réponse.
        for message in fournisseur.lire_messages(corps, entetes):
            taches.add_task(traitement, message, fournisseur, config.db_path)
        return PlainTextResponse("ok")

    return app


app = creer_app()

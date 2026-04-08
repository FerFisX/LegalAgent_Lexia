"""
Scheduler: registra el pipeline en Prefect con ejecución automática cada 24h.
Correr una sola vez para activar el trigger automático.
"""

from prefect.client.schemas.schedules import CronSchedule
from prefect.deployments import Deployment

from data_engineering.pipeline.flows import gaceta_pipeline


def deploy_pipeline() -> None:
    """
    Registra el pipeline en Prefect con schedule diario a las 2:00 AM.
    """
    deployment = Deployment.build_from_flow(
        flow=gaceta_pipeline,
        name="lexia-daily-scrape",
        schedule=CronSchedule(cron="0 2 * * *", timezone="America/La_Paz"),
        parameters={
            "sections": None,   # todas las secciones
            "max_pages": 10,
            "force_all": False,
        },
        tags=["lexia", "gaceta", "daily"],
        description="Ingesta diaria automática de la Gaceta Oficial de Bolivia",
        version="1.0.0",
    )
    deployment.apply()
    print("Deployment registrado. El pipeline correrá diariamente a las 02:00 AM (La Paz).")
    print("Visualizar en: http://localhost:4200")


if __name__ == "__main__":
    deploy_pipeline()

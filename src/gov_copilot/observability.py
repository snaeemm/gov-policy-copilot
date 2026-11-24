"""OpenTelemetry setup. Exports to Application Insights when a connection string is set."""

import logging

from fastapi import FastAPI

from gov_copilot.config import get_settings

_configured = False


def setup_telemetry(app: FastAPI) -> None:
    global _configured
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    s = get_settings()
    if _configured or not s.applicationinsights_connection_string:
        return
    from azure.monitor.opentelemetry import configure_azure_monitor
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    configure_azure_monitor(
        connection_string=s.applicationinsights_connection_string,
        logger_name="gov_copilot",
    )
    FastAPIInstrumentor.instrument_app(app, excluded_urls="healthz")
    _configured = True

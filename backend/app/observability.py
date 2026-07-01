"""Optional OpenTelemetry + Prometheus instrumentation.

Kept dependency-light: if the optional ``otel`` extras aren't installed (or
``OTEL_ENABLED`` is false) this is a no-op, so the core app runs without them.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def setup_observability(app) -> None:
    # Prometheus metrics at /metrics (best-effort).
    try:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(app, endpoint="/metrics")
    except Exception as exc:  # noqa: BLE001
        logger.info("prometheus_instrumentation_skipped", reason=str(exc))

    if not settings.OTEL_ENABLED:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": settings.OTEL_SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT, insecure=True)
            )
        )
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        logger.info("otel_enabled", endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    except Exception as exc:  # noqa: BLE001
        logger.warning("otel_setup_failed", reason=str(exc))

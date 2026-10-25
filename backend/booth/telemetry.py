"""Optional tracing: Azure Monitor (Application Insights) or any OTLP collector.

Nothing is configured unless an environment variable asks for it, so local runs and tests stay quiet.

* ``APPLICATIONINSIGHTS_CONNECTION_STRING`` -> Azure Monitor (needs ``pip install ".[azure]"``)
* ``OTEL_EXPORTER_OTLP_ENDPOINT``           -> OTLP exporter via Microsoft Agent Framework

Agent Framework then emits a span for every agent run, model call and tool call, and the crew adds a
``booth.job`` span per director job with each hand-off recorded as a span event.
"""

from __future__ import annotations

import logging
import os

from opentelemetry import trace

log = logging.getLogger("booth.telemetry")
tracer = trace.get_tracer("booth")


def configure() -> str:
    """Set up exporters once at start-up. Returns the backend in use: 'azure-monitor', 'otlp' or 'none'."""
    if os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"):
        try:
            from agent_framework.observability import enable_instrumentation
            from azure.monitor.opentelemetry import configure_azure_monitor
        except ImportError:
            log.warning(
                "APPLICATIONINSIGHTS_CONNECTION_STRING set but azure-monitor-opentelemetry is missing"
            )
            return "none"
        configure_azure_monitor()
        enable_instrumentation()
        log.info("telemetry: Azure Monitor")
        return "azure-monitor"
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from agent_framework.observability import configure_otel_providers

        configure_otel_providers(service_name="the-booth")
        log.info("telemetry: OTLP")
        return "otlp"
    return "none"

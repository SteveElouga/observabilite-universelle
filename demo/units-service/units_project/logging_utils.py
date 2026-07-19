"""Filtre de log qui injecte trace_id/span_id du span courant dans chaque enregistrement (§10.1)."""
import logging

from opentelemetry import trace


class TraceContextFilter(logging.Filter):
    """Injecte trace_id/span_id du span courant dans chaque log, pour la corrélation log -> trace."""

    def filter(self, record):
        ctx = trace.get_current_span().get_span_context()
        record.trace_id = format(ctx.trace_id, "032x") if ctx.is_valid else ""
        record.span_id = format(ctx.span_id, "016x") if ctx.is_valid else ""
        return True

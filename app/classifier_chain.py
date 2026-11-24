"""Auto-switching classifier (2026-11-24): two vendors, one interface.

Both vendors are configured once in .env -- primary (PROJECT0_LLM_*)
and secondary (PROJECT0_LLM2_*) -- and this module tries them in
order. If the primary fails (401, timeout, 5xx, bad JSON), the same
request is retried against the secondary automatically; the response's
`model` field shows which vendor actually answered, so a switch is
never silent. A vendor whose key is empty is skipped. If every vendor
fails, RuntimeError is raised and main.py falls back to the local
heuristic, exactly as before.

This is the seed of the Week 2 multi-model gateway: provider list,
ordered failover, per-response attribution.
"""
import logging

import httpx

from .classifier_llm import classify_with_llm
from .config import settings

logger = logging.getLogger("project0")


def configured_providers(cfg=settings) -> list[dict]:
    """Ordered vendor list from config; unconfigured vendors are skipped."""
    providers = []
    if cfg.llm_api_key:
        providers.append(
            {
                "name": "primary",
                "api_key": cfg.llm_api_key,
                "base_url": cfg.llm_base_url,
                "model": cfg.llm_model,
            }
        )
    if cfg.llm2_api_key:
        providers.append(
            {
                "name": "secondary",
                "api_key": cfg.llm2_api_key,
                "base_url": cfg.llm2_base_url,
                "model": cfg.llm2_model,
            }
        )
    return providers


def classify_auto(
    text: str,
    *,
    providers: list[dict] | None = None,
    timeout: float | None = None,
    client: httpx.Client | None = None,
) -> tuple[str, float, str, dict | None]:
    """Classify via the first vendor that answers.

    Returns (label, confidence, model, usage) from the winning vendor.
    Raises RuntimeError if no vendor is configured or all of them fail.
    """
    if providers is None:
        providers = configured_providers()
    if timeout is None:
        timeout = settings.llm_timeout
    if not providers:
        raise RuntimeError("no LLM provider configured (both keys empty)")

    errors: list[str] = []
    for index, provider in enumerate(providers):
        try:
            label, confidence, model, usage = classify_with_llm(
                text,
                api_key=provider["api_key"],
                base_url=provider["base_url"],
                model=provider["model"],
                timeout=timeout,
                client=client,
            )
        except Exception as exc:  # any vendor failure -> try the next one
            logger.warning(
                "provider %s (model=%s) failed: %r; trying next",
                provider["name"],
                provider["model"],
                exc,
            )
            errors.append(f"{provider['name']}: {exc!r}")
            continue
        if index > 0:
            logger.warning(
                "auto-switch: answered by provider %s (model=%s)",
                provider["name"],
                model,
            )
        return label, confidence, model, usage
    raise RuntimeError("all LLM providers failed: " + "; ".join(errors))

"""Optional Sentry initialization."""

import os


def init_sentry(*, with_flask: bool = True) -> None:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk

        integrations = []
        if with_flask:
            try:
                from sentry_sdk.integrations.flask import FlaskIntegration

                integrations.append(FlaskIntegration())
            except Exception:
                pass
        sentry_sdk.init(
            dsn=dsn,
            integrations=integrations,
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            environment=os.getenv("FLASK_ENV", "development"),
        )
    except Exception:
        pass

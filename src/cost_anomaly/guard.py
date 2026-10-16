ALLOWED_OPERATIONS = frozenset({"GetCostAndUsage"})


class ForbiddenOperation(RuntimeError):
    pass


def install_guard(client, allowed: frozenset[str] = ALLOWED_OPERATIONS):
    """Refuse any API operation outside `allowed`, even if the credentials would permit it.

    Hooks provide-client-params, the first event botocore emits for a call, so it runs
    before any request is built, signed or sent.
    """

    def _guard(model, **kwargs):
        if model.name not in allowed:
            raise ForbiddenOperation(f"Operation {model.name} is not allowed by cost-anomaly")

    client.meta.events.register_first("provide-client-params", _guard)
    return client

"""Доменные ошибки сервисного слоя (транслируются в HTTP в app/api)."""


class NotFoundError(Exception):
    pass


class ValidationError(Exception):
    pass

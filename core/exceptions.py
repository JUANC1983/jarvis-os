class JarvisError(Exception):
    pass


class ValidationAppError(JarvisError):
    pass


class ExternalServiceError(JarvisError):
    pass

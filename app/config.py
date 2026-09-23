import os


def get_secret_key() -> str:
    secret = os.getenv("SECRET_KEY")
    if secret:
        return secret

    if os.getenv("TESTING") == "1":
        return "test-secret"

    if os.getenv("VERCEL_ENV") == "production" or os.getenv("ENVIRONMENT") == "production":
        raise RuntimeError("SECRET_KEY must be set in production environments.")

    return "development-secret-change-me"

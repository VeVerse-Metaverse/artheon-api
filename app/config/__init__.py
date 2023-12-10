import os

from pydantic import BaseSettings


class DBSettings:
    name: str = "development"
    user: str = "developer"
    password: str = ""
    host: str = "127.0.0.1"
    port: int = 5432

    def __init__(self, name: str, user: str, password: str, host: str, port: int):
        self.name = name
        self.user = user
        self.password = password
        self.host = host
        self.port = port


class ExperienceParams:
    exponent = 1.5
    base = 10.0


class ExperienceRewards:
    login: int = 1
    verify_signed_msg: int = 1
    invite_sent: int = 1
    invite_join: int = 3
    view: int = 1
    like: int = 1
    create: int = 2
    update: int = 1
    download: int = 1
    join_online_game: int = 1
    place_object: int = 1
    add_collectable: int = 1
    remove_object: int = 0
    remove_collectable: int = 0
    feedback: int = 1
    share: int = 1
    follow: int = 2
    unfollow: int = 0
    upload_avatar: int = 1
    upload_file: int = 1
    add_file: int = 1
    delete: int = 0
    delete_comment: int = 0
    add_comment: int = 1
    add_persona: int = 1
    edit_persona: int = 1
    tag: int = 1
    remove_tag: int = 0
    add_platform: int = 0
    remove_platform: int = 0
    add_link: int = 0
    remove_link: int = 0
    action: int = 1


class ExperienceSettings:
    rewards = ExperienceRewards()
    params = ExperienceParams()
    max_level = 100


class Settings(BaseSettings):
    version = "api-v1"
    internal_user_id = "XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX"
    env = os.getenv("ENVIRONMENT", "dev")
    db = DBSettings(name=os.getenv("DB_NAME", "test"),
                    user=os.getenv("DB_USER", "test"),
                    password=os.getenv("DB_PASS", "test"),
                    host=os.getenv("DB_HOST", "127.0.0.1"),
                    port=os.getenv("DB_PORT", 5432))
    experience = ExperienceSettings()
    use_cache = os.getenv("USE_CACHE", False)


settings = Settings()

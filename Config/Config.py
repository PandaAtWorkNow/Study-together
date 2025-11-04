from dataclasses import dataclass
from environs import Env


@dataclass
class LogConfig:
    format: str
    level: str


@dataclass
class TgBot:
    token: str  # Список id администраторов бота


@dataclass
class Config:
    bot: TgBot
    log: LogConfig


def load_config(path: str | None = None) -> Config:

    env: Env = Env()
    env.read_env(path)

    return Config(
        bot=TgBot(
            token=env('BOT_TOKEN')
        ),
        log=LogConfig(
            format=env('LOG_FORMAT'),
            level=env('LOG_LEVEL')
        )
    )
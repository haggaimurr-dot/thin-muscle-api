from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "thin-muscle-api"
    debug: bool = True
    database_url: str = "sqlite:///./thin_muscle.db"
    # 市场：标价=买家实付，平台从中抽 15%
    market_fee_rate: float = 0.15
    # 对象存储（密钥私聊后注入）
    oss_endpoint: str = ""
    oss_bucket: str = ""
    oss_access_key: str = ""
    oss_secret_key: str = ""
    # 微信小程序 / 支付（密钥私聊后注入）
    wx_app_id: str = ""
    wx_app_secret: str = ""
    wx_mch_id: str = ""
    wx_pay_key: str = ""

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

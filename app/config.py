from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Environment
    environment: str = "development"

    # Database
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "education_db"

    # Migration
    app_for: str = "jee-mains"

    # JWT Settings
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # OTP Settings
    otp_expire_minutes: int = 10

    # Gmail SMTP Settings
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_from_name: str = "MockTest"

    # WhatsApp API Settings (loaded from .env)
    whatsapp_api_token: str = ""
    whatsapp_phone_number_id: str = ""
    notification_mode: str = "development"
    whatsapp_app_name: str = ""
    whatsapp_contact_number: str = ""
    whatsapp_template_name: str = ""
    whatsapp_template_language: str = ""

    # Test Settings
    test_num_questions: int = 30
    test_negative_marking: bool = True
    test_negative_marks: float = 0.25
    test_correct_marks: float = 1.0

    class Config:
        env_file = ".env"


settings = Settings()

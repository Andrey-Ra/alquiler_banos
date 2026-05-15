import os
from dotenv import load_dotenv

load_dotenv()


class Config:

    # Base de datos SQL
    SQLALCHEMY_DATABASE_URI = 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Flask
    SECRET_KEY = 'clave-secreta-banos-2026'

    # MongoDB
    MONGO_URI = os.getenv('MONGO_URI')

    # JWT
    JWT_SECRET_KEY = 'jwt-clave-super-segura-2026'
    JWT_TOKEN_LOCATION = ['cookies']
    JWT_ACCESS_COOKIE_PATH = '/'
    JWT_COOKIE_SECURE = False
    JWT_COOKIE_CSRF_PROTECT = False
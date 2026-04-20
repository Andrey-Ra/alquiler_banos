import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI        = 'sqlite:///database.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY                     = 'clave-secreta-banos-2026'
    MONGO_URI                      = os.getenv('MONGO_URI')
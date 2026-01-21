import os
from flask import Flask
from web.routes import bp as game_bp

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-change-in-production')

app.register_blueprint(game_bp)

if __name__ == '__main__':
    app.run(debug=True)
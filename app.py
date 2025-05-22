from flask import Flask
from config import DevelopmentConfig
from models import db
from blueprints.parameters import parameters_bp
from blueprints.groups import groups_bp
from blueprints.profiles import profiles_bp

app = Flask(__name__)
app.config.from_object(DevelopmentConfig)
db.init_app(app)

# Регистрация blueprints
app.register_blueprint(parameters_bp)
app.register_blueprint(groups_bp)
app.register_blueprint(profiles_bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)

import os
from flask import Flask
from dotenv import load_dotenv

from .extensions import db, login_manager
from .utils import formatar_moeda, formatar_data


def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/ordem_servico",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    app.config["EMPRESA_NOME"] = os.getenv("EMPRESA_NOME", "Minha Assistência Técnica")
    app.config["EMPRESA_CNPJ"] = os.getenv("EMPRESA_CNPJ", "")
    app.config["EMPRESA_ENDERECO"] = os.getenv("EMPRESA_ENDERECO", "")
    app.config["EMPRESA_TELEFONE"] = os.getenv("EMPRESA_TELEFONE", "")
    app.config["EMPRESA_PIX_CHAVE"] = os.getenv("EMPRESA_PIX_CHAVE", "")
    app.config["EMPRESA_PIX_NOME"] = os.getenv("EMPRESA_PIX_NOME", "")
    app.config["EMPRESA_PIX_CIDADE"] = os.getenv("EMPRESA_PIX_CIDADE", "")

    db.init_app(app)
    login_manager.init_app(app)

    # Filtros customizados usados nos templates
    app.jinja_env.filters["moeda"] = formatar_moeda
    app.jinja_env.filters["data"] = formatar_data

    from .models import Usuario

    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # Registro dos blueprints (módulos do sistema)
    from .blueprints.auth import bp as auth_bp
    from .blueprints.main import bp as main_bp
    from .blueprints.clientes import bp as clientes_bp
    from .blueprints.ordens import bp as ordens_bp
    from .blueprints.estoque import bp as estoque_bp
    from .blueprints.vendas import bp as vendas_bp
    from .blueprints.financeiro import bp as financeiro_bp
    from .blueprints.agenda import bp as agenda_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(clientes_bp)
    app.register_blueprint(ordens_bp)
    app.register_blueprint(estoque_bp)
    app.register_blueprint(vendas_bp)
    app.register_blueprint(financeiro_bp)
    app.register_blueprint(agenda_bp)

    with app.app_context():
        db.create_all()
        _criar_admin_padrao()

    return app


def _criar_admin_padrao():
    """Cria um usuário administrador padrão na primeira execução."""
    from .models import Usuario

    if Usuario.query.count() == 0:
        admin = Usuario(
            nome="Administrador",
            email="admin@sistema.com",
            cargo="Administrador",
            is_admin=True,
        )
        admin.set_senha("admin123")
        db.session.add(admin)
        db.session.commit()
        print("=" * 60)
        print("Usuário administrador criado automaticamente:")
        print("  E-mail: admin@sistema.com")
        print("  Senha:  admin123")
        print("  >>> Troque essa senha assim que possível! <<<")
        print("=" * 60)

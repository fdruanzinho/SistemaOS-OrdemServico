from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from ..extensions import db
from ..models import Usuario

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        senha = request.form.get("senha", "")
        usuario = Usuario.query.filter_by(email=email).first()

        if usuario and usuario.ativo and usuario.check_senha(senha):
            login_user(usuario)
            flash(f"Bem-vindo(a), {usuario.nome}!", "success")
            proximo = request.args.get("next")
            return redirect(proximo or url_for("main.dashboard"))

        flash("E-mail ou senha inválidos.", "danger")

    return render_template("auth/login.html")


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/usuarios")
@login_required
def usuarios():
    lista = Usuario.query.order_by(Usuario.nome).all()
    return render_template("auth/usuarios.html", usuarios=lista)


@bp.route("/usuarios/novo", methods=["GET", "POST"])
@login_required
def novo_usuario():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if Usuario.query.filter_by(email=email).first():
            flash("Já existe um usuário com este e-mail.", "danger")
            return redirect(url_for("auth.novo_usuario"))

        usuario = Usuario(
            nome=request.form.get("nome"),
            email=email,
            cargo=request.form.get("cargo") or "Técnico",
            is_admin=bool(request.form.get("is_admin")),
        )
        usuario.set_senha(request.form.get("senha") or "123456")
        db.session.add(usuario)
        db.session.commit()
        flash("Usuário cadastrado com sucesso!", "success")
        return redirect(url_for("auth.usuarios"))

    return render_template("auth/usuario_form.html", usuario=None)


@bp.route("/usuarios/<int:id>/toggle", methods=["POST"])
@login_required
def toggle_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    usuario.ativo = not usuario.ativo
    db.session.commit()
    flash("Status do usuário atualizado.", "success")
    return redirect(url_for("auth.usuarios"))

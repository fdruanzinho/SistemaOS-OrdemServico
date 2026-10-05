from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import or_

from ..extensions import db
from ..models import Cliente, TIPOS_PESSOA
from ..utils import parse_data

bp = Blueprint("clientes", __name__, url_prefix="/clientes")


def _preencher_cliente(cliente, form):
    cliente.tipo_pessoa = form.get("tipo_pessoa") or "Pessoa Física"
    cliente.cpf_cnpj = form.get("cpf_cnpj", "").strip()
    cliente.rg_ie = form.get("rg_ie", "").strip() or None
    cliente.nome = form.get("nome", "").strip()
    cliente.nome_fantasia = form.get("nome_fantasia", "").strip() or None
    cliente.contato = form.get("contato", "").strip() or None
    cliente.telefone = form.get("telefone", "").strip()
    cliente.telefone2 = form.get("telefone2", "").strip() or None
    cliente.celular_whatsapp = form.get("celular_whatsapp", "").strip() or None
    cliente.radio = form.get("radio", "").strip() or None
    cliente.site = form.get("site", "").strip() or None
    cliente.email = form.get("email", "").strip() or None
    cliente.email_notas_fiscais = form.get("email_notas_fiscais", "").strip() or None
    cliente.cep = form.get("cep", "").strip() or None
    cliente.endereco = form.get("endereco", "").strip() or None
    cliente.numero = form.get("numero", "").strip() or None
    cliente.bairro = form.get("bairro", "").strip() or None
    cliente.complemento = form.get("complemento", "").strip() or None
    cliente.cidade = form.get("cidade", "").strip() or None
    cliente.estado = (form.get("estado") or "").strip().upper()[:2] or None
    cliente.pais = form.get("pais", "").strip() or "Brasil"
    cliente.grupo = form.get("grupo", "").strip() or None
    cliente.sexo = form.get("sexo", "").strip() or None
    cliente.aniversario = parse_data(form.get("aniversario"))
    cliente.observacoes = form.get("observacoes", "").strip() or None


@bp.route("/")
@login_required
def listar():
    busca = request.args.get("q", "").strip()
    query = Cliente.query.filter_by(ativo=True)
    if busca:
        termo = f"%{busca}%"
        query = query.filter(
            or_(
                Cliente.nome.ilike(termo),
                Cliente.nome_fantasia.ilike(termo),
                Cliente.cpf_cnpj.ilike(termo),
                Cliente.telefone.ilike(termo),
                Cliente.email.ilike(termo),
            )
        )
    clientes = query.order_by(Cliente.nome).all()
    return render_template("clientes/listar.html", clientes=clientes, busca=busca)


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    if request.method == "POST":
        cliente = Cliente()
        _preencher_cliente(cliente, request.form)
        db.session.add(cliente)
        db.session.commit()
        flash(f"Cliente '{cliente.nome_exibicao}' cadastrado com sucesso!", "success")

        # Se veio da abertura de OS, já redireciona para continuar o fluxo
        if request.form.get("continuar_para_os"):
            return redirect(url_for("ordens.nova", cliente_id=cliente.id))
        return redirect(url_for("clientes.detalhe", id=cliente.id))

    return render_template("clientes/form.html", cliente=None, tipos_pessoa=TIPOS_PESSOA)


@bp.route("/<int:id>")
@login_required
def detalhe(id):
    cliente = Cliente.query.get_or_404(id)
    return render_template("clientes/detalhe.html", cliente=cliente)


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == "POST":
        _preencher_cliente(cliente, request.form)
        db.session.commit()
        flash("Dados do cliente atualizados!", "success")
        return redirect(url_for("clientes.detalhe", id=cliente.id))

    return render_template("clientes/form.html", cliente=cliente, tipos_pessoa=TIPOS_PESSOA)


@bp.route("/<int:id>/inativar", methods=["POST"])
@login_required
def inativar(id):
    cliente = Cliente.query.get_or_404(id)
    cliente.ativo = False
    db.session.commit()
    flash("Cliente inativado.", "info")
    return redirect(url_for("clientes.listar"))

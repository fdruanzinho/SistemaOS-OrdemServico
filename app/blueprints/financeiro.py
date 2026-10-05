from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from ..extensions import db
from ..models import ContaReceber, ContaPagar, Cliente, STATUS_FINANCEIRO, FORMAS_PAGAMENTO
from ..utils import parse_float, parse_data

bp = Blueprint("financeiro", __name__, url_prefix="/financeiro")


# ---------------------------------------------------------------------------
# Contas a Receber
# ---------------------------------------------------------------------------

@bp.route("/receber")
@login_required
def receber():
    status_filtro = request.args.get("status", "")
    query = ContaReceber.query
    if status_filtro:
        query = query.filter_by(status=status_filtro)
    contas = query.order_by(ContaReceber.data_vencimento).all()

    hoje = date.today()
    for c in contas:
        if c.status == "Pendente" and c.data_vencimento and c.data_vencimento < hoje:
            c.status = "Atrasado"
    db.session.commit()

    total_pendente = sum(c.valor for c in contas if c.status in ("Pendente", "Atrasado"))
    return render_template(
        "financeiro/receber.html", contas=contas, status_lista=STATUS_FINANCEIRO,
        status_filtro=status_filtro, total_pendente=total_pendente,
    )


@bp.route("/receber/novo", methods=["GET", "POST"])
@login_required
def novo_receber():
    if request.method == "POST":
        conta = ContaReceber(
            descricao=request.form.get("descricao", "").strip(),
            cliente_id=request.form.get("cliente_id", type=int) or None,
            origem="Avulso",
            valor=parse_float(request.form.get("valor")),
            data_vencimento=parse_data(request.form.get("data_vencimento")),
            observacoes=request.form.get("observacoes", "").strip() or None,
        )
        db.session.add(conta)
        db.session.commit()
        flash("Conta a receber lançada!", "success")
        return redirect(url_for("financeiro.receber"))

    clientes = Cliente.query.filter_by(ativo=True).order_by(Cliente.nome).all()
    return render_template("financeiro/receber_form.html", clientes=clientes)


@bp.route("/receber/<int:id>/pagar", methods=["POST"])
@login_required
def baixar_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    conta.status = "Pago"
    conta.data_pagamento = datetime.now()
    conta.forma_pagamento = request.form.get("forma_pagamento", conta.forma_pagamento)
    db.session.commit()
    flash("Recebimento confirmado!", "success")
    return redirect(url_for("financeiro.receber"))


@bp.route("/receber/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    conta.status = "Cancelado"
    db.session.commit()
    flash("Conta a receber cancelada.", "info")
    return redirect(url_for("financeiro.receber"))


# ---------------------------------------------------------------------------
# Contas a Pagar
# ---------------------------------------------------------------------------

@bp.route("/pagar")
@login_required
def pagar():
    status_filtro = request.args.get("status", "")
    query = ContaPagar.query
    if status_filtro:
        query = query.filter_by(status=status_filtro)
    contas = query.order_by(ContaPagar.data_vencimento).all()

    hoje = date.today()
    for c in contas:
        if c.status == "Pendente" and c.data_vencimento and c.data_vencimento < hoje:
            c.status = "Atrasado"
    db.session.commit()

    total_pendente = sum(c.valor for c in contas if c.status in ("Pendente", "Atrasado"))
    return render_template(
        "financeiro/pagar.html", contas=contas, status_lista=STATUS_FINANCEIRO,
        status_filtro=status_filtro, total_pendente=total_pendente,
    )


@bp.route("/pagar/novo", methods=["GET", "POST"])
@login_required
def novo_pagar():
    if request.method == "POST":
        conta = ContaPagar(
            descricao=request.form.get("descricao", "").strip(),
            fornecedor_nome=request.form.get("fornecedor_nome", "").strip() or None,
            categoria=request.form.get("categoria", "").strip() or None,
            origem="Avulso",
            numero_documento=request.form.get("numero_documento", "").strip() or None,
            valor=parse_float(request.form.get("valor")),
            data_vencimento=parse_data(request.form.get("data_vencimento")),
            observacoes=request.form.get("observacoes", "").strip() or None,
        )
        db.session.add(conta)
        db.session.commit()
        flash("Conta a pagar lançada!", "success")
        return redirect(url_for("financeiro.pagar"))

    return render_template("financeiro/pagar_form.html")


@bp.route("/pagar/<int:id>/pagar", methods=["POST"])
@login_required
def baixar_pagar(id):
    conta = ContaPagar.query.get_or_404(id)
    conta.status = "Pago"
    conta.data_pagamento = datetime.now()
    conta.forma_pagamento = request.form.get("forma_pagamento", conta.forma_pagamento)
    db.session.commit()
    flash("Pagamento confirmado!", "success")
    return redirect(url_for("financeiro.pagar"))


@bp.route("/pagar/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar_pagar(id):
    conta = ContaPagar.query.get_or_404(id)
    conta.status = "Cancelado"
    db.session.commit()
    flash("Conta a pagar cancelada.", "info")
    return redirect(url_for("financeiro.pagar"))

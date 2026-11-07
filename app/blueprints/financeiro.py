from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from ..extensions import db
from ..models import ContaReceber, ContaPagar, Cliente, FORMAS_PAGAMENTO
from ..utils import parse_float, parse_data, somar_meses
from ..servicos import (
    baixar_conta_receber, estornar_conta_receber, cancelar_conta_receber, FIADO, ABERTAS,
)

bp = Blueprint("financeiro", __name__, url_prefix="/financeiro")

OPCOES_STATUS = [
    ("", "Todos"),
    ("aberto", "Em aberto (pendentes + atrasados)"),
    ("Pendente", "Pendentes"),
    ("Atrasado", "Atrasados"),
    ("Pago", "Pagos"),
    ("Cancelado", "Cancelados"),
]
FORMAS_BAIXA = [f for f in FORMAS_PAGAMENTO if f != FIADO]


# ---------------------------------------------------------------------------
# Funções auxiliares (usadas por Receber e Pagar)
# ---------------------------------------------------------------------------

def _atualizar_atrasos(modelo):
    """Pendente com vencimento passado vira Atrasado (e volta se o vencimento mudar)."""
    hoje = date.today()
    mudou = False
    for c in modelo.query.filter(modelo.status.in_(ABERTAS)).all():
        novo = "Atrasado" if c.data_vencimento and c.data_vencimento < hoje else "Pendente"
        if c.status != novo:
            c.status = novo
            mudou = True
    if mudou:
        db.session.commit()


def _filtrar(modelo, busca_cols=None):
    status = request.args.get("status", "")
    busca = request.args.get("q", "").strip()
    de = parse_data(request.args.get("de"))
    ate = parse_data(request.args.get("ate"))

    query = modelo.query
    if status == "aberto":
        query = query.filter(modelo.status.in_(ABERTAS))
    elif status:
        query = query.filter(modelo.status == status)
    if de:
        query = query.filter(modelo.data_vencimento >= de)
    if ate:
        query = query.filter(modelo.data_vencimento <= ate)
    if busca:
        termo = f"%{busca}%"
        condicoes = [modelo.descricao.ilike(termo)]
        for col in (busca_cols or []):
            condicoes.append(col.ilike(termo))
        from sqlalchemy import or_
        query = query.filter(or_(*condicoes))
    if status in ("aberto", "Pendente", "Atrasado"):
        ordem = [modelo.data_vencimento.asc(), modelo.id.asc()]     # o que vence primeiro aparece primeiro
    else:
        ordem = [modelo.data_vencimento.desc(), modelo.id.desc()]   # mais recentes primeiro
    return query.order_by(*ordem).all(), {"status": status, "q": busca, "de": request.args.get("de", ""), "ate": request.args.get("ate", "")}


def _resumo(modelo):
    hoje = date.today()
    todas = modelo.query.all()
    abertas = [c for c in todas if c.status in ABERTAS]
    return {
        "aberto": sum(c.valor for c in abertas),
        "qtd_aberto": len(abertas),
        "atrasado": sum(c.valor for c in abertas if c.data_vencimento < hoje),
        "qtd_atrasado": len([c for c in abertas if c.data_vencimento < hoje]),
        "hoje": sum(c.valor for c in abertas if c.data_vencimento == hoje),
        "mes": sum(
            c.valor for c in todas
            if c.status == "Pago" and c.data_pagamento
            and c.data_pagamento.year == hoje.year and c.data_pagamento.month == hoje.month
        ),
    }


def _parcelar(valor_total, parcelas):
    parcelas = max(1, min(parcelas, 60))
    base = round(valor_total / parcelas, 2)
    valores = [base] * parcelas
    valores[-1] = round(valor_total - base * (parcelas - 1), 2)
    return valores


def _data_pagamento_form():
    d = parse_data(request.form.get("data_pagamento"))
    return datetime.combine(d, datetime.now().time()) if d else datetime.now()


# ---------------------------------------------------------------------------
# Contas a Receber
# ---------------------------------------------------------------------------

@bp.route("/receber")
@login_required
def receber():
    _atualizar_atrasos(ContaReceber)
    contas, filtros = _filtrar(ContaReceber, [ContaReceber.origem, ContaReceber.forma_pagamento])
    return render_template(
        "financeiro/receber.html", contas=contas, filtros=filtros, opcoes_status=OPCOES_STATUS,
        resumo=_resumo(ContaReceber), formas_baixa=FORMAS_BAIXA,
        hoje=date.today().isoformat(),
        total_listado=sum(c.valor for c in contas if c.status != "Cancelado"),
    )


@bp.route("/receber/novo", methods=["GET", "POST"])
@login_required
def novo_receber():
    if request.method == "POST":
        valor = parse_float(request.form.get("valor"))
        vencimento = parse_data(request.form.get("data_vencimento"))
        descricao = request.form.get("descricao", "").strip()
        if valor <= 0 or not vencimento or not descricao:
            flash("Informe descrição, valor maior que zero e vencimento.", "danger")
            return redirect(url_for("financeiro.novo_receber"))
        parcelas = request.form.get("parcelas", type=int) or 1
        valores = _parcelar(valor, parcelas)
        for i, v in enumerate(valores):
            db.session.add(ContaReceber(
                descricao=descricao + (f" ({i + 1}/{len(valores)})" if len(valores) > 1 else ""),
                cliente_id=request.form.get("cliente_id", type=int) or None,
                origem="Avulso", valor=v, forma_pagamento=request.form.get("forma_pagamento") or None,
                data_vencimento=somar_meses(vencimento, i),
                observacoes=request.form.get("observacoes", "").strip() or None,
            ))
        db.session.commit()
        flash(f"{len(valores)} lançamento(s) a receber criado(s)!", "success")
        return redirect(url_for("financeiro.receber"))

    clientes = Cliente.query.filter_by(ativo=True).order_by(Cliente.nome).all()
    return render_template("financeiro/receber_form.html", clientes=clientes, conta=None, formas=FORMAS_PAGAMENTO)


@bp.route("/receber/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    if request.method == "POST":
        valor = parse_float(request.form.get("valor"))
        vencimento = parse_data(request.form.get("data_vencimento"))
        if valor <= 0 or not vencimento:
            flash("Informe um valor maior que zero e o vencimento.", "danger")
            return redirect(url_for("financeiro.editar_receber", id=id))
        conta.descricao = request.form.get("descricao", "").strip() or conta.descricao
        conta.cliente_id = request.form.get("cliente_id", type=int) or None
        conta.valor = valor
        conta.data_vencimento = vencimento
        conta.observacoes = request.form.get("observacoes", "").strip() or None
        db.session.commit()
        flash("Lançamento atualizado!", "success")
        return redirect(url_for("financeiro.receber", status=""))
    clientes = Cliente.query.filter_by(ativo=True).order_by(Cliente.nome).all()
    return render_template("financeiro/receber_form.html", clientes=clientes, conta=conta, formas=FORMAS_PAGAMENTO)


@bp.route("/receber/<int:id>/pagar", methods=["POST"])
@login_required
def baixar_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    if conta.status not in ABERTAS:
        flash("Esta conta não está em aberto.", "info")
        return redirect(request.referrer or url_for("financeiro.receber"))
    baixar_conta_receber(conta, request.form.get("forma_pagamento"), _data_pagamento_form())
    db.session.commit()
    flash("Recebimento confirmado! Baixa realizada.", "success")
    return redirect(request.referrer or url_for("financeiro.receber"))


@bp.route("/receber/<int:id>/estornar", methods=["POST"])
@login_required
def estornar_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    if conta.status == "Pago":
        estornar_conta_receber(conta)
        db.session.commit()
        flash("Baixa estornada: a conta voltou para pendente.", "info")
    return redirect(request.referrer or url_for("financeiro.receber"))


@bp.route("/receber/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    cancelar_conta_receber(conta)
    db.session.commit()
    flash("Conta a receber cancelada.", "info")
    return redirect(request.referrer or url_for("financeiro.receber"))


@bp.route("/receber/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_receber(id):
    conta = ContaReceber.query.get_or_404(id)
    if conta.origem != "Avulso":
        flash("Lançamentos de vendas e OS não podem ser excluídos; use Cancelar.", "warning")
    else:
        db.session.delete(conta)
        db.session.commit()
        flash("Lançamento excluído.", "info")
    return redirect(request.referrer or url_for("financeiro.receber"))


# ---------------------------------------------------------------------------
# Contas a Pagar
# ---------------------------------------------------------------------------

@bp.route("/pagar")
@login_required
def pagar():
    _atualizar_atrasos(ContaPagar)
    contas, filtros = _filtrar(ContaPagar, [ContaPagar.fornecedor_nome, ContaPagar.categoria, ContaPagar.numero_documento])
    return render_template(
        "financeiro/pagar.html", contas=contas, filtros=filtros, opcoes_status=OPCOES_STATUS,
        resumo=_resumo(ContaPagar), formas_baixa=FORMAS_BAIXA,
        hoje=date.today().isoformat(),
        total_listado=sum(c.valor for c in contas if c.status != "Cancelado"),
    )


@bp.route("/pagar/novo", methods=["GET", "POST"])
@login_required
def novo_pagar():
    if request.method == "POST":
        valor = parse_float(request.form.get("valor"))
        vencimento = parse_data(request.form.get("data_vencimento"))
        descricao = request.form.get("descricao", "").strip()
        if valor <= 0 or not vencimento or not descricao:
            flash("Informe descrição, valor maior que zero e vencimento.", "danger")
            return redirect(url_for("financeiro.novo_pagar"))
        parcelas = request.form.get("parcelas", type=int) or 1
        valores = _parcelar(valor, parcelas)
        for i, v in enumerate(valores):
            db.session.add(ContaPagar(
                descricao=descricao + (f" ({i + 1}/{len(valores)})" if len(valores) > 1 else ""),
                fornecedor_nome=request.form.get("fornecedor_nome", "").strip() or None,
                categoria=request.form.get("categoria", "").strip() or None,
                origem="Avulso",
                numero_documento=request.form.get("numero_documento", "").strip() or None,
                valor=v, data_vencimento=somar_meses(vencimento, i),
                observacoes=request.form.get("observacoes", "").strip() or None,
            ))
        db.session.commit()
        flash(f"{len(valores)} lançamento(s) a pagar criado(s)!", "success")
        return redirect(url_for("financeiro.pagar"))

    return render_template("financeiro/pagar_form.html", conta=None)


@bp.route("/pagar/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar_pagar(id):
    conta = ContaPagar.query.get_or_404(id)
    if request.method == "POST":
        valor = parse_float(request.form.get("valor"))
        vencimento = parse_data(request.form.get("data_vencimento"))
        if valor <= 0 or not vencimento:
            flash("Informe um valor maior que zero e o vencimento.", "danger")
            return redirect(url_for("financeiro.editar_pagar", id=id))
        conta.descricao = request.form.get("descricao", "").strip() or conta.descricao
        conta.fornecedor_nome = request.form.get("fornecedor_nome", "").strip() or None
        conta.categoria = request.form.get("categoria", "").strip() or None
        conta.numero_documento = request.form.get("numero_documento", "").strip() or None
        conta.valor = valor
        conta.data_vencimento = vencimento
        conta.observacoes = request.form.get("observacoes", "").strip() or None
        db.session.commit()
        flash("Lançamento atualizado!", "success")
        return redirect(url_for("financeiro.pagar", status=""))
    return render_template("financeiro/pagar_form.html", conta=conta)


@bp.route("/pagar/<int:id>/pagar", methods=["POST"])
@login_required
def baixar_pagar(id):
    conta = ContaPagar.query.get_or_404(id)
    if conta.status not in ABERTAS:
        flash("Esta conta não está em aberto.", "info")
        return redirect(request.referrer or url_for("financeiro.pagar"))
    conta.status = "Pago"
    conta.data_pagamento = _data_pagamento_form()
    forma = request.form.get("forma_pagamento")
    conta.forma_pagamento = forma if forma and forma != FIADO else (conta.forma_pagamento or "Dinheiro")
    db.session.commit()
    flash("Pagamento confirmado! Baixa realizada.", "success")
    return redirect(request.referrer or url_for("financeiro.pagar"))


@bp.route("/pagar/<int:id>/estornar", methods=["POST"])
@login_required
def estornar_pagar(id):
    conta = ContaPagar.query.get_or_404(id)
    if conta.status == "Pago":
        conta.status = "Pendente"
        conta.data_pagamento = None
        db.session.commit()
        flash("Baixa estornada: a conta voltou para pendente.", "info")
    return redirect(request.referrer or url_for("financeiro.pagar"))


@bp.route("/pagar/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar_pagar(id):
    conta = ContaPagar.query.get_or_404(id)
    conta.status = "Cancelado"
    db.session.commit()
    flash("Conta a pagar cancelada.", "info")
    return redirect(request.referrer or url_for("financeiro.pagar"))


@bp.route("/pagar/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_pagar(id):
    conta = ContaPagar.query.get_or_404(id)
    db.session.delete(conta)
    db.session.commit()
    flash("Lançamento excluído.", "info")
    return redirect(request.referrer or url_for("financeiro.pagar"))

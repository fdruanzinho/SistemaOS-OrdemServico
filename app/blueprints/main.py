from datetime import date, timedelta
from flask import Blueprint, render_template
from flask_login import login_required

from ..models import (
    Cliente, OrdemServico, STATUS_OS_FINALIZADOS, Produto,
    ContaReceber, ContaPagar, Venda,
)

bp = Blueprint("main", __name__)

_manutencao_feita = False


@bp.record_once
def _configurar(state):
    # Campo vazio (None) nunca aparece escrito "None" nas telas
    state.app.jinja_env.finalize = lambda valor: "" if valor is None else valor


@bp.before_app_request
def _manutencao_inicial():
    """Na primeira requisição após iniciar: limpa dados antigos e corrige o financeiro."""
    global _manutencao_feita
    if _manutencao_feita:
        return
    _manutencao_feita = True
    from ..servicos import manutencao_dados
    manutencao_dados()


@bp.route("/")
@login_required
def dashboard():
    hoje = date.today()
    proximos_7_dias = hoje + timedelta(days=7)

    total_clientes = Cliente.query.filter_by(ativo=True).count()

    ordens_abertas = OrdemServico.query.filter(
        ~OrdemServico.status.in_(STATUS_OS_FINALIZADOS)
    ).all()

    ordens_prontas = [o for o in ordens_abertas if o.status == "Equipamento pronto"]

    produtos_estoque_baixo = [p for p in Produto.query.filter_by(ativo=True).all() if p.estoque_baixo]

    contas_receber_pendentes = ContaReceber.query.filter(
        ContaReceber.status.in_(["Pendente", "Atrasado"])
    ).all()
    contas_pagar_pendentes = ContaPagar.query.filter(
        ContaPagar.status.in_(["Pendente", "Atrasado"])
    ).all()

    contas_receber_vencendo = [
        c for c in contas_receber_pendentes
        if c.data_vencimento and hoje <= c.data_vencimento <= proximos_7_dias
    ]
    contas_pagar_vencendo = [
        c for c in contas_pagar_pendentes
        if c.data_vencimento and hoje <= c.data_vencimento <= proximos_7_dias
    ]
    contas_receber_atrasadas = [c for c in contas_receber_pendentes if c.data_vencimento and c.data_vencimento < hoje]
    contas_pagar_atrasadas = [c for c in contas_pagar_pendentes if c.data_vencimento and c.data_vencimento < hoje]

    total_a_receber = sum(c.valor for c in contas_receber_pendentes)
    total_a_pagar = sum(c.valor for c in contas_pagar_pendentes)

    vendas_hoje = [v for v in Venda.query.filter_by(status="Concluída").all() if v.data_venda.date() == hoje]
    total_vendido_hoje = sum(v.valor_total for v in vendas_hoje)

    ultimas_ordens = OrdemServico.query.order_by(OrdemServico.data_cadastro.desc()).limit(8).all()

    return render_template(
        "dashboard.html",
        total_clientes=total_clientes,
        ordens_abertas=ordens_abertas,
        qtd_ordens_abertas=len(ordens_abertas),
        qtd_ordens_prontas=len(ordens_prontas),
        produtos_estoque_baixo=produtos_estoque_baixo,
        total_a_receber=total_a_receber,
        total_a_pagar=total_a_pagar,
        contas_receber_vencendo=contas_receber_vencendo,
        contas_pagar_vencendo=contas_pagar_vencendo,
        contas_receber_atrasadas=contas_receber_atrasadas,
        contas_pagar_atrasadas=contas_pagar_atrasadas,
        total_vendido_hoje=total_vendido_hoje,
        qtd_vendas_hoje=len(vendas_hoje),
        ultimas_ordens=ultimas_ordens,
    )

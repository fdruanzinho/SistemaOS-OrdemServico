import calendar
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Compromisso
from ..utils import parse_data

bp = Blueprint("agenda", __name__, url_prefix="/agenda")

MESES_PT = [
    "", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _semana_a_partir_de(base):
    """Retorna a lista dos 7 dias (segunda a domingo) da semana que contém 'base'."""
    inicio = base - timedelta(days=base.weekday())
    return [inicio + timedelta(days=i) for i in range(7)]


def _semanas_do_mes(ano, mes):
    """Retorna uma matriz de semanas (cada uma com 7 dias, None para dias fora do mês)."""
    cal = calendar.Calendar(firstweekday=0)  # segunda-feira
    semanas = []
    semana_atual = []
    for dia in cal.itermonthdates(ano, mes):
        semana_atual.append(dia)
        if len(semana_atual) == 7:
            semanas.append(semana_atual)
            semana_atual = []
    return semanas


@bp.route("/")
@login_required
def listar():
    dia_param = request.args.get("dia")
    try:
        base = parse_data(dia_param) if dia_param else date.today()
        base = base or date.today()
    except Exception:
        base = date.today()

    dias_semana = _semana_a_partir_de(base)
    compromissos = Compromisso.query.filter(
        Compromisso.dia.in_(dias_semana)
    ).order_by(Compromisso.dia, Compromisso.hora).all()

    por_dia = {d: [] for d in dias_semana}
    for c in compromissos:
        por_dia.setdefault(c.dia, []).append(c)

    semana_anterior = dias_semana[0] - timedelta(days=7)
    semana_seguinte = dias_semana[0] + timedelta(days=7)

    # Calendário mensal clicável (mês de referência = mês do dia selecionado)
    semanas_mes = _semanas_do_mes(base.year, base.month)
    primeiro_dia_mes_ant = (date(base.year, base.month, 1) - timedelta(days=1)).replace(day=1)
    ultimo_dia_mes = date(base.year, base.month, calendar.monthrange(base.year, base.month)[1])
    primeiro_dia_mes_seg = ultimo_dia_mes + timedelta(days=1)

    inicio_mes = date(base.year, base.month, 1)
    fim_mes = ultimo_dia_mes
    contagem_mes = {}
    for (dia,) in db.session.query(Compromisso.dia).filter(
        Compromisso.dia >= semanas_mes[0][0], Compromisso.dia <= semanas_mes[-1][-1]
    ).all():
        contagem_mes[dia] = contagem_mes.get(dia, 0) + 1

    return render_template(
        "agenda/listar.html",
        dias_semana=dias_semana, por_dia=por_dia,
        semana_anterior=semana_anterior, semana_seguinte=semana_seguinte,
        hoje=date.today(), dia_selecionado=base,
        semanas_mes=semanas_mes, mes_nome=MESES_PT[base.month], ano_mes=base.year,
        mes_anterior=primeiro_dia_mes_ant, mes_seguinte=primeiro_dia_mes_seg,
        contagem_mes=contagem_mes,
    )


@bp.route("/novo", methods=["POST"])
@login_required
def novo():
    compromisso = Compromisso(
        descricao=request.form.get("descricao", "").strip(),
        dia=parse_data(request.form.get("dia")) or date.today(),
        hora=request.form.get("hora") or "00:00",
        usuario_id=current_user.id,
        avisar=bool(request.form.get("avisar")),
    )
    db.session.add(compromisso)
    db.session.commit()
    flash("Compromisso agendado!", "success")
    return redirect(url_for("agenda.listar", dia=compromisso.dia.isoformat()))


@bp.route("/<int:id>/concluir", methods=["POST"])
@login_required
def concluir(id):
    compromisso = Compromisso.query.get_or_404(id)
    compromisso.concluido = not compromisso.concluido
    db.session.commit()
    return redirect(url_for("agenda.listar", dia=compromisso.dia.isoformat()))


@bp.route("/<int:id>/excluir", methods=["POST"])
@login_required
def excluir(id):
    compromisso = Compromisso.query.get_or_404(id)
    dia = compromisso.dia.isoformat()
    db.session.delete(compromisso)
    db.session.commit()
    flash("Compromisso excluído.", "info")
    return redirect(url_for("agenda.listar", dia=dia))

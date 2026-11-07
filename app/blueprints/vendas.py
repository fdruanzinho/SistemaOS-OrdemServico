import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Venda, VendaItem, Produto, Cliente, Pagamento, ContaReceber, MovimentoEstoque, FORMAS_PAGAMENTO
from ..utils import gerar_numero, parse_float, parse_data
from ..servicos import (
    lancar_conta_receber, dar_baixa_origem, cancelar_conta_receber, FIADO, ABERTAS,
)

bp = Blueprint("vendas", __name__, url_prefix="/vendas")


@bp.route("/")
@login_required
def listar():
    vendas = Venda.query.order_by(Venda.data_venda.desc()).limit(200).all()
    return render_template("vendas/listar.html", vendas=vendas)


@bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova():
    if request.method == "POST":
        itens_json = request.form.get("itens_json", "[]")
        try:
            itens = json.loads(itens_json)
        except (ValueError, TypeError):
            itens = []

        if not itens:
            flash("Adicione ao menos um produto à venda.", "danger")
            return redirect(url_for("vendas.nova"))

        cliente_id = request.form.get("cliente_id", type=int) or None
        forma_pagamento = request.form.get("forma_pagamento")

        venda = Venda(
            numero=gerar_numero(Venda, "numero", "V"),
            cliente_id=cliente_id,
            vendedor_id=current_user.id,
            valor_desconto=parse_float(request.form.get("valor_desconto")),
            observacoes=request.form.get("observacoes", "").strip() or None,
            status="Fiado (a receber)" if forma_pagamento == "Venda Futura (Fiado)" else "Concluída",
        )
        db.session.add(venda)
        db.session.flush()

        for item in itens:
            quantidade = float(item.get("quantidade") or 1)
            produto_id = item.get("produto_id")

            if produto_id:
                produto = Produto.query.get(int(produto_id))
                if not produto:
                    continue
                venda_item = VendaItem(
                    venda_id=venda.id, produto_id=produto.id,
                    quantidade=quantidade,
                    valor_unitario=float(item.get("valor_unitario") or produto.preco_venda),
                )
                db.session.add(venda_item)
                produto.quantidade_estoque = max((produto.quantidade_estoque or 0) - quantidade, 0)
                db.session.add(MovimentoEstoque(
                    produto_id=produto.id, tipo="Saída", quantidade=quantidade,
                    origem=f"Venda {venda.numero}",
                ))
            else:
                # Item avulso: não vem do estoque, apenas descrição + valor digitados na hora
                descricao = (item.get("descricao") or item.get("nome") or "").strip()
                if not descricao:
                    continue
                venda_item = VendaItem(
                    venda_id=venda.id, produto_id=None, descricao=descricao,
                    quantidade=quantidade,
                    valor_unitario=float(item.get("valor_unitario") or 0),
                )
                db.session.add(venda_item)

        db.session.flush()

        if forma_pagamento == FIADO:
            if not cliente_id:
                flash("Venda futura (fiado) exige um cliente identificado.", "danger")
                db.session.rollback()
                return redirect(url_for("vendas.nova"))
            lancar_conta_receber(
                f"Venda {venda.numero}", cliente_id, "Venda", venda.id, venda.valor_total,
                forma_pagamento, status="Pendente",
                vencimento=parse_data(request.form.get("data_vencimento")) or datetime.now().date(),
            )
            db.session.add(Pagamento(
                venda_id=venda.id, forma_pagamento=forma_pagamento,
                valor=venda.valor_total, status="Pendente",
            ))
        else:
            db.session.add(Pagamento(
                venda_id=venda.id, forma_pagamento=forma_pagamento,
                valor=venda.valor_total, status="Pago",
            ))
            # Venda paga também aparece em Contas a Receber (já como "Pago")
            lancar_conta_receber(
                f"Venda {venda.numero}", cliente_id, "Venda", venda.id, venda.valor_total,
                forma_pagamento, status="Pago",
            )

        db.session.commit()
        flash(f"Venda {venda.numero} finalizada com sucesso!", "success")
        return redirect(url_for("vendas.detalhe", id=venda.id))

    produtos = Produto.query.filter_by(ativo=True).order_by(Produto.nome).all()
    clientes = Cliente.query.filter_by(ativo=True).order_by(Cliente.nome).all()
    return render_template(
        "vendas/nova.html", produtos=produtos, clientes=clientes,
        formas_pagamento=FORMAS_PAGAMENTO,
    )


@bp.route("/<int:id>")
@login_required
def detalhe(id):
    venda = Venda.query.get_or_404(id)
    contas = ContaReceber.query.filter_by(origem="Venda", origem_id=venda.id).order_by(ContaReceber.id).all()
    formas_baixa = [f for f in FORMAS_PAGAMENTO if f != FIADO]
    pendente = sum(c.valor for c in contas if c.status in ABERTAS)
    return render_template("vendas/detalhe.html", venda=venda, contas=contas,
                           formas_baixa=formas_baixa, valor_pendente=pendente,
                           now_data=datetime.now().strftime("%Y-%m-%d"))


@bp.route("/<int:id>/baixa", methods=["POST"])
@login_required
def dar_baixa(id):
    venda = Venda.query.get_or_404(id)
    if venda.status == "Cancelada":
        flash("Venda cancelada não pode receber baixa.", "danger")
        return redirect(url_for("vendas.detalhe", id=venda.id))
    forma = request.form.get("forma_pagamento") or "Dinheiro"
    data_pg = parse_data(request.form.get("data_pagamento"))
    data_pg = datetime.combine(data_pg, datetime.now().time()) if data_pg else None
    qtd = dar_baixa_origem("Venda", venda.id, forma, data_pg)
    db.session.commit()
    if qtd:
        flash("Baixa realizada! O valor foi registrado como recebido em Contas a Receber.", "success")
    else:
        flash("Esta venda não tem valores pendentes.", "info")
    return redirect(url_for("vendas.detalhe", id=venda.id))


@bp.route("/<int:id>/cancelar", methods=["POST"])
@login_required
def cancelar(id):
    venda = Venda.query.get_or_404(id)
    if venda.status != "Cancelada":
        for item in venda.itens:
            if item.produto:
                item.produto.quantidade_estoque = (item.produto.quantidade_estoque or 0) + item.quantidade
                db.session.add(MovimentoEstoque(
                    produto_id=item.produto.id, tipo="Entrada", quantidade=item.quantidade,
                    origem=f"Cancelamento venda {venda.numero}",
                ))
        for conta in ContaReceber.query.filter_by(origem="Venda", origem_id=venda.id).all():
            if conta.status != "Cancelado":
                conta.status = "Cancelado"
        for pag in venda.pagamentos:
            pag.status = "Cancelado"
        venda.status = "Cancelada"
        db.session.commit()
        flash("Venda cancelada. Itens estornados ao estoque e contas a receber canceladas.", "info")
    return redirect(url_for("vendas.detalhe", id=venda.id))


@bp.route("/api/produto/<int:id>")
@login_required
def api_produto(id):
    produto = Produto.query.get_or_404(id)
    return jsonify({
        "id": produto.id, "nome": produto.nome, "codigo": produto.codigo,
        "preco_venda": produto.preco_venda, "estoque": produto.quantidade_estoque,
    })

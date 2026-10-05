import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Venda, VendaItem, Produto, Cliente, Pagamento, ContaReceber, MovimentoEstoque, FORMAS_PAGAMENTO
from ..utils import gerar_numero, parse_float, parse_data

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

        if forma_pagamento == "Venda Futura (Fiado)":
            if not cliente_id:
                flash("Venda futura (fiado) exige um cliente identificado.", "danger")
                db.session.rollback()
                return redirect(url_for("vendas.nova"))
            db.session.add(ContaReceber(
                descricao=f"Venda {venda.numero}",
                cliente_id=cliente_id, origem="Venda", origem_id=venda.id,
                valor=venda.valor_total,
                data_vencimento=parse_data(request.form.get("data_vencimento")) or datetime.now().date(),
                forma_pagamento=forma_pagamento,
            ))
            db.session.add(Pagamento(
                venda_id=venda.id, forma_pagamento=forma_pagamento,
                valor=venda.valor_total, status="Pendente",
            ))
        else:
            db.session.add(Pagamento(
                venda_id=venda.id, forma_pagamento=forma_pagamento,
                valor=venda.valor_total, status="Pago",
            ))

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
    return render_template("vendas/detalhe.html", venda=venda)


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
        venda.status = "Cancelada"
        db.session.commit()
        flash("Venda cancelada e itens estornados ao estoque.", "info")
    return redirect(url_for("vendas.detalhe", id=venda.id))


@bp.route("/api/produto/<int:id>")
@login_required
def api_produto(id):
    produto = Produto.query.get_or_404(id)
    return jsonify({
        "id": produto.id, "nome": produto.nome, "codigo": produto.codigo,
        "preco_venda": produto.preco_venda, "estoque": produto.quantidade_estoque,
    })

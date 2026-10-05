from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required
from sqlalchemy import or_

from ..extensions import db
from ..models import Produto, MovimentoEstoque
from ..utils import parse_float

bp = Blueprint("estoque", __name__, url_prefix="/estoque")


@bp.route("/")
@login_required
def listar():
    busca = request.args.get("q", "").strip()
    apenas_baixo = request.args.get("baixo")

    query = Produto.query.filter_by(ativo=True)
    if busca:
        termo = f"%{busca}%"
        query = query.filter(or_(Produto.nome.ilike(termo), Produto.codigo.ilike(termo), Produto.categoria.ilike(termo)))

    produtos = query.order_by(Produto.nome).all()
    if apenas_baixo:
        produtos = [p for p in produtos if p.estoque_baixo]

    return render_template("estoque/listar.html", produtos=produtos, busca=busca, apenas_baixo=apenas_baixo)


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    if request.method == "POST":
        produto = Produto(
            codigo=request.form.get("codigo", "").strip() or None,
            nome=request.form.get("nome", "").strip(),
            categoria=request.form.get("categoria", "").strip() or None,
            grupo=request.form.get("grupo", "").strip() or None,
            secao=request.form.get("secao", "").strip() or None,
            marca=request.form.get("marca", "").strip() or None,
            ncm=request.form.get("ncm", "").strip() or None,
            codigo_barras=request.form.get("codigo_barras", "").strip() or None,
            descricao=request.form.get("descricao", "").strip() or None,
            unidade=request.form.get("unidade") or "UN",
            quantidade_estoque=parse_float(request.form.get("quantidade_estoque")),
            estoque_minimo=parse_float(request.form.get("estoque_minimo")),
            estoque_maximo=parse_float(request.form.get("estoque_maximo")),
            preco_custo=parse_float(request.form.get("preco_custo")),
            preco_venda=parse_float(request.form.get("preco_venda")),
        )
        db.session.add(produto)
        db.session.flush()
        if produto.quantidade_estoque:
            db.session.add(MovimentoEstoque(
                produto_id=produto.id, tipo="Entrada",
                quantidade=produto.quantidade_estoque, origem="Cadastro inicial",
            ))
        db.session.commit()
        flash(f"Produto '{produto.nome}' cadastrado!", "success")
        return redirect(url_for("estoque.listar"))

    return render_template("estoque/form.html", produto=None)


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    produto = Produto.query.get_or_404(id)
    if request.method == "POST":
        produto.codigo = request.form.get("codigo", "").strip() or None
        produto.nome = request.form.get("nome", "").strip()
        produto.categoria = request.form.get("categoria", "").strip() or None
        produto.grupo = request.form.get("grupo", "").strip() or None
        produto.secao = request.form.get("secao", "").strip() or None
        produto.marca = request.form.get("marca", "").strip() or None
        produto.ncm = request.form.get("ncm", "").strip() or None
        produto.codigo_barras = request.form.get("codigo_barras", "").strip() or None
        produto.descricao = request.form.get("descricao", "").strip() or None
        produto.unidade = request.form.get("unidade") or "UN"
        produto.estoque_minimo = parse_float(request.form.get("estoque_minimo"))
        produto.estoque_maximo = parse_float(request.form.get("estoque_maximo"))
        produto.preco_custo = parse_float(request.form.get("preco_custo"))
        produto.preco_venda = parse_float(request.form.get("preco_venda"))
        db.session.commit()
        flash("Produto atualizado!", "success")
        return redirect(url_for("estoque.listar"))

    return render_template("estoque/form.html", produto=produto)


@bp.route("/<int:id>/ajuste", methods=["POST"])
@login_required
def ajuste_manual(id):
    produto = Produto.query.get_or_404(id)
    tipo = request.form.get("tipo")
    quantidade = parse_float(request.form.get("quantidade"))
    motivo = request.form.get("motivo", "").strip() or "Ajuste manual"

    if tipo == "Entrada":
        produto.quantidade_estoque = (produto.quantidade_estoque or 0) + quantidade
    else:
        produto.quantidade_estoque = max((produto.quantidade_estoque or 0) - quantidade, 0)

    db.session.add(MovimentoEstoque(produto_id=produto.id, tipo=tipo, quantidade=quantidade, origem=motivo))
    db.session.commit()
    flash("Estoque ajustado!", "success")
    return redirect(url_for("estoque.listar"))


@bp.route("/<int:id>/inativar", methods=["POST"])
@login_required
def inativar(id):
    produto = Produto.query.get_or_404(id)
    produto.ativo = False
    db.session.commit()
    flash("Produto inativado.", "info")
    return redirect(url_for("estoque.listar"))


@bp.route("/<int:id>/movimentos")
@login_required
def movimentos(id):
    produto = Produto.query.get_or_404(id)
    lista = MovimentoEstoque.query.filter_by(produto_id=id).order_by(MovimentoEstoque.data.desc()).all()
    return render_template("estoque/movimentos.html", produto=produto, movimentos=lista)

import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import (
    Cliente, Equipamento, OrdemServico, OrdemItem, OrdemHistorico, Pagamento,
    ContaReceber, Produto, MovimentoEstoque, OrdemFoto,
    TIPOS_EQUIPAMENTO, STATUS_OS, STATUS_OS_FINALIZADOS, TIPOS_ITEM_OS, FORMAS_PAGAMENTO,
)
from ..utils import gerar_numero, parse_float, parse_data
from ..servicos import lancar_conta_receber, dar_baixa_origem, FIADO

bp = Blueprint("ordens", __name__, url_prefix="/ordens")

EXTENSOES_PERMITIDAS = {"png", "jpg", "jpeg", "webp", "gif"}


def _extensao_permitida(nome_arquivo):
    return "." in nome_arquivo and nome_arquivo.rsplit(".", 1)[1].lower() in EXTENSOES_PERMITIDAS


# ---------------------------------------------------------------------------
# Listagem / painel de acompanhamento
# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
def listar():
    status_filtro = request.args.get("status", "")
    busca = request.args.get("q", "").strip()

    query = OrdemServico.query
    if status_filtro:
        query = query.filter_by(status=status_filtro)
    else:
        # Por padrão, mostra apenas as em andamento (esconde finalizadas antigas)
        if not request.args.get("todas"):
            query = query.filter(~OrdemServico.status.in_(STATUS_OS_FINALIZADOS))

    if busca:
        termo = f"%{busca}%"
        query = query.join(Cliente).filter(
            or_(
                OrdemServico.numero.ilike(termo),
                Cliente.nome.ilike(termo),
                Cliente.nome_fantasia.ilike(termo),
            )
        )

    ordens = query.order_by(OrdemServico.data_cadastro.desc()).all()
    return render_template(
        "ordens/listar.html", ordens=ordens, status_lista=STATUS_OS,
        status_filtro=status_filtro, busca=busca,
    )


# ---------------------------------------------------------------------------
# Abertura de nova OS (cliente novo -> cadastro -> equipamento -> OS)
# ---------------------------------------------------------------------------

@bp.route("/nova", methods=["GET", "POST"])
@login_required
def nova():
    cliente_id = request.args.get("cliente_id", type=int) or request.form.get("cliente_id", type=int)

    if request.method == "POST":
        cliente = Cliente.query.get_or_404(request.form.get("cliente_id"))

        equipamento = Equipamento(
            cliente_id=cliente.id,
            tipo=request.form.get("tipo"),
            marca=request.form.get("marca", "").strip() or None,
            modelo=request.form.get("modelo", "").strip() or None,
            numero_serie=request.form.get("numero_serie", "").strip() or None,
            cor=request.form.get("cor", "").strip() or None,
            senha_acesso=request.form.get("senha_acesso", "").strip() or None,
            acessorios=request.form.get("acessorios", "").strip() or None,
            condicao_entrada=request.form.get("condicao_entrada", "").strip() or None,
        )
        db.session.add(equipamento)
        db.session.flush()  # gera o id do equipamento sem commitar ainda

        ordem = OrdemServico(
            numero=gerar_numero(OrdemServico, "numero", "OS"),
            cliente_id=cliente.id,
            equipamento_id=equipamento.id,
            tecnico_id=current_user.id,
            defeito_relatado=request.form.get("defeito_relatado", "").strip(),
            observacoes=request.form.get("observacoes", "").strip() or None,
            data_previsao=parse_data(request.form.get("data_previsao")),
            valor_orcamento=parse_float(request.form.get("valor_orcamento")),
            valor_adiantamento=parse_float(request.form.get("valor_adiantamento")),
            garantia_dias=int(request.form.get("garantia_dias") or 90),
        )
        db.session.add(ordem)
        db.session.flush()

        historico = OrdemHistorico(
            ordem_id=ordem.id, usuario_id=current_user.id,
            status_anterior=None, status_novo=ordem.status,
            observacao="Ordem de serviço aberta.",
        )
        db.session.add(historico)
        db.session.commit()

        flash(f"Ordem de Serviço {ordem.numero} aberta com sucesso!", "success")
        return redirect(url_for("ordens.detalhe", id=ordem.id))

    cliente = Cliente.query.get(cliente_id) if cliente_id else None
    clientes = Cliente.query.filter_by(ativo=True).order_by(Cliente.nome).all()
    return render_template(
        "ordens/nova.html", cliente=cliente, clientes=clientes,
        tipos_equipamento=TIPOS_EQUIPAMENTO,
    )


# ---------------------------------------------------------------------------
# Detalhe / acompanhamento em tempo real da OS
# ---------------------------------------------------------------------------

@bp.route("/<int:id>")
@login_required
def detalhe(id):
    ordem = OrdemServico.query.get_or_404(id)
    return render_template(
        "ordens/detalhe.html", ordem=ordem,
        status_lista=STATUS_OS, tipos_item=TIPOS_ITEM_OS,
        formas_pagamento=FORMAS_PAGAMENTO,
        formas_baixa=[f for f in FORMAS_PAGAMENTO if f != FIADO],
        now_data=datetime.now().strftime("%Y-%m-%d"),
        produtos=Produto.query.filter_by(ativo=True).order_by(Produto.nome).all(),
    )


@bp.route("/<int:id>/status", methods=["POST"])
@login_required
def atualizar_status(id):
    ordem = OrdemServico.query.get_or_404(id)
    novo_status = request.form.get("status")
    observacao = request.form.get("observacao", "").strip()

    if novo_status and novo_status != ordem.status:
        historico = OrdemHistorico(
            ordem_id=ordem.id, usuario_id=current_user.id,
            status_anterior=ordem.status, status_novo=novo_status,
            observacao=observacao or None,
        )
        ordem.status = novo_status
        if novo_status == "Equipamento entregue":
            ordem.data_entrega = datetime.now()
        if novo_status in STATUS_OS_FINALIZADOS and not ordem.data_conclusao:
            ordem.data_conclusao = datetime.now()
        db.session.add(historico)
        db.session.commit()
        flash(f"Status atualizado para: {novo_status}", "success")
    elif observacao:
        historico = OrdemHistorico(
            ordem_id=ordem.id, usuario_id=current_user.id,
            status_anterior=ordem.status, status_novo=ordem.status,
            observacao=observacao,
        )
        db.session.add(historico)
        db.session.commit()
        flash("Observação registrada no histórico.", "success")

    return redirect(url_for("ordens.detalhe", id=ordem.id))


@bp.route("/<int:id>/laudo", methods=["POST"])
@login_required
def atualizar_laudo(id):
    ordem = OrdemServico.query.get_or_404(id)
    ordem.laudo_tecnico = request.form.get("laudo_tecnico", "").strip()
    db.session.commit()
    flash("Laudo técnico salvo!", "success")
    return redirect(url_for("ordens.detalhe", id=ordem.id))


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    ordem = OrdemServico.query.get_or_404(id)
    if request.method == "POST":
        ordem.defeito_relatado = request.form.get("defeito_relatado", "").strip()
        ordem.observacoes = request.form.get("observacoes", "").strip() or None
        ordem.data_previsao = parse_data(request.form.get("data_previsao"))
        ordem.valor_orcamento = parse_float(request.form.get("valor_orcamento"))
        ordem.valor_desconto = parse_float(request.form.get("valor_desconto"))
        ordem.valor_adiantamento = parse_float(request.form.get("valor_adiantamento"))
        ordem.garantia_dias = int(request.form.get("garantia_dias") or 90)

        equip = ordem.equipamento
        equip.tipo = request.form.get("tipo")
        equip.marca = request.form.get("marca", "").strip() or None
        equip.modelo = request.form.get("modelo", "").strip() or None
        equip.numero_serie = request.form.get("numero_serie", "").strip() or None
        equip.cor = request.form.get("cor", "").strip() or None
        equip.senha_acesso = request.form.get("senha_acesso", "").strip() or None
        equip.acessorios = request.form.get("acessorios", "").strip() or None
        equip.condicao_entrada = request.form.get("condicao_entrada", "").strip() or None

        db.session.commit()
        flash("Ordem de serviço atualizada!", "success")
        return redirect(url_for("ordens.detalhe", id=ordem.id))

    return render_template("ordens/editar.html", ordem=ordem, tipos_equipamento=TIPOS_EQUIPAMENTO)


# ---------------------------------------------------------------------------
# Itens (peças e serviços) lançados na OS
# ---------------------------------------------------------------------------

@bp.route("/<int:id>/itens/adicionar", methods=["POST"])
@login_required
def adicionar_item(id):
    ordem = OrdemServico.query.get_or_404(id)
    produto_id = request.form.get("produto_id", type=int)

    item = OrdemItem(
        ordem_id=ordem.id,
        tipo=request.form.get("tipo", "Peça"),
        quantidade=parse_float(request.form.get("quantidade"), 1),
        valor_unitario=parse_float(request.form.get("valor_unitario")),
    )

    if produto_id:
        produto = Produto.query.get(produto_id)
        item.produto_id = produto.id
        item.descricao = produto.nome
        if not request.form.get("valor_unitario"):
            item.valor_unitario = produto.preco_venda
    else:
        item.descricao = request.form.get("descricao", "").strip()

    db.session.add(item)
    db.session.flush()

    # Se veio do estoque, baixa a quantidade automaticamente
    if produto_id:
        produto = Produto.query.get(produto_id)
        produto.quantidade_estoque = max((produto.quantidade_estoque or 0) - item.quantidade, 0)
        db.session.add(MovimentoEstoque(
            produto_id=produto.id, tipo="Saída", quantidade=item.quantidade,
            origem=f"OS {ordem.numero}",
        ))

    db.session.commit()
    flash("Item adicionado à ordem de serviço!", "success")
    return redirect(url_for("ordens.detalhe", id=ordem.id))


@bp.route("/<int:ordem_id>/itens/<int:item_id>/remover", methods=["POST"])
@login_required
def remover_item(ordem_id, item_id):
    item = OrdemItem.query.get_or_404(item_id)
    # devolve ao estoque se o item veio de um produto
    if item.produto_id:
        produto = Produto.query.get(item.produto_id)
        if produto:
            produto.quantidade_estoque = (produto.quantidade_estoque or 0) + item.quantidade
            db.session.add(MovimentoEstoque(
                produto_id=produto.id, tipo="Entrada", quantidade=item.quantidade,
                origem=f"Estorno item OS #{ordem_id}",
            ))
    db.session.delete(item)
    db.session.commit()
    flash("Item removido.", "info")
    return redirect(url_for("ordens.detalhe", id=ordem_id))


# ---------------------------------------------------------------------------
# Pagamento da OS
# ---------------------------------------------------------------------------

@bp.route("/<int:id>/pagamento", methods=["POST"])
@login_required
def registrar_pagamento(id):
    ordem = OrdemServico.query.get_or_404(id)
    forma = request.form.get("forma_pagamento")
    valor = parse_float(request.form.get("valor"))
    parcelas = int(request.form.get("parcelas") or 1)

    if not forma or valor <= 0:
        flash("Informe a forma de pagamento e um valor maior que zero.", "danger")
        return redirect(url_for("ordens.detalhe", id=ordem.id))

    descricao = f"OS {ordem.numero} - {ordem.cliente.nome_exibicao}"
    if forma == FIADO:
        lancar_conta_receber(
            descricao, ordem.cliente_id, "Ordem de Serviço", ordem.id, valor, forma,
            status="Pendente",
            vencimento=parse_data(request.form.get("data_vencimento")) or datetime.now().date(),
        )
        pagamento = Pagamento(
            ordem_id=ordem.id, forma_pagamento=forma, valor=valor,
            parcelas=parcelas, status="Pendente",
        )
    else:
        pagamento = Pagamento(
            ordem_id=ordem.id, forma_pagamento=forma, valor=valor,
            parcelas=parcelas, status="Pago",
        )
        # Pagamento à vista também aparece em Contas a Receber (já como "Pago")
        lancar_conta_receber(
            descricao, ordem.cliente_id, "Ordem de Serviço", ordem.id, valor, forma,
            status="Pago",
        )

    db.session.add(pagamento)
    db.session.commit()
    flash("Pagamento registrado!", "success")
    return redirect(url_for("ordens.detalhe", id=ordem.id))


@bp.route("/<int:id>/baixa", methods=["POST"])
@login_required
def dar_baixa(id):
    ordem = OrdemServico.query.get_or_404(id)
    forma = request.form.get("forma_pagamento") or "Dinheiro"
    data_pg = parse_data(request.form.get("data_pagamento"))
    data_pg = datetime.combine(data_pg, datetime.now().time()) if data_pg else None
    qtd = dar_baixa_origem("Ordem de Serviço", ordem.id, forma, data_pg)
    db.session.commit()
    if qtd:
        flash("Baixa realizada! O valor foi registrado como recebido em Contas a Receber.", "success")
    else:
        flash("Esta OS não tem valores pendentes de baixa.", "info")
    return redirect(url_for("ordens.detalhe", id=ordem.id))


# ---------------------------------------------------------------------------
# Impressão da Ordem de Serviço (comprovante em PDF)
# ---------------------------------------------------------------------------

@bp.route("/<int:id>/imprimir")
@login_required
def imprimir(id):
    ordem = OrdemServico.query.get_or_404(id)
    return render_template("ordens/imprimir.html", ordem=ordem)


# ---------------------------------------------------------------------------
# Fotos do equipamento (tirar foto pelo celular ou anexar arquivo)
# ---------------------------------------------------------------------------

@bp.route("/<int:id>/fotos/upload", methods=["POST"])
@login_required
def upload_foto(id):
    ordem = OrdemServico.query.get_or_404(id)
    arquivos = request.files.getlist("fotos")

    if not arquivos or all(a.filename == "" for a in arquivos):
        flash("Selecione ao menos uma foto ou tire uma foto para enviar.", "danger")
        return redirect(url_for("ordens.detalhe", id=ordem.id))

    pasta = os.path.join(current_app.static_folder, "uploads", "ordens", str(ordem.id))
    os.makedirs(pasta, exist_ok=True)

    enviadas = 0
    for arquivo in arquivos:
        if arquivo and arquivo.filename and _extensao_permitida(arquivo.filename):
            extensao = arquivo.filename.rsplit(".", 1)[1].lower()
            nome_seguro = f"{uuid.uuid4().hex}.{extensao}"
            arquivo.save(os.path.join(pasta, nome_seguro))
            db.session.add(OrdemFoto(ordem_id=ordem.id, arquivo=nome_seguro))
            enviadas += 1

    if enviadas:
        db.session.commit()
        flash(f"{enviadas} foto(s) adicionada(s)!", "success")
    else:
        flash("Nenhum arquivo válido foi enviado (use JPG, PNG, WEBP ou GIF).", "danger")

    return redirect(url_for("ordens.detalhe", id=ordem.id))


@bp.route("/<int:ordem_id>/fotos/<int:foto_id>/excluir", methods=["POST"])
@login_required
def excluir_foto(ordem_id, foto_id):
    foto = OrdemFoto.query.get_or_404(foto_id)
    caminho = os.path.join(current_app.static_folder, "uploads", "ordens", str(ordem_id), foto.arquivo)
    if os.path.exists(caminho):
        os.remove(caminho)
    db.session.delete(foto)
    db.session.commit()
    flash("Foto removida.", "info")
    return redirect(url_for("ordens.detalhe", id=ordem_id))

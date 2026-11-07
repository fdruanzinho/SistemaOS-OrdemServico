import os
import re
import shutil
from types import SimpleNamespace

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_, func

from ..extensions import db
from ..models import Cliente, OrdemServico, ContaReceber, TIPOS_PESSOA
from ..utils import (
    parse_data, so_digitos, validar_cpf, validar_cnpj, formatar_cpf, formatar_cnpj,
    formatar_telefone, formatar_cep, texto_limpo,
)

bp = Blueprint("clientes", __name__, url_prefix="/clientes")

CAMPOS_TEXTO = [
    "rg_ie", "nome_fantasia", "contato", "email", "email_notas_fiscais", "endereco",
    "numero", "bairro", "complemento", "cidade", "grupo", "sexo", "observacoes",
]
CAMPOS_TELEFONE = ["telefone", "telefone2", "celular_whatsapp"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _extrair(form):
    """Lê o formulário já limpando vazios e o texto 'None'."""
    dados = {
        "tipo_pessoa": texto_limpo(form.get("tipo_pessoa")) or "Pessoa Física",
        "cpf_cnpj": texto_limpo(form.get("cpf_cnpj")) or "",
        "nome": texto_limpo(form.get("nome")) or "",
        "estado": (texto_limpo(form.get("estado")) or "").upper()[:2] or None,
        "pais": texto_limpo(form.get("pais")) or "Brasil",
        "cep": texto_limpo(form.get("cep")),
        "aniversario": parse_data(form.get("aniversario")),
    }
    for campo in CAMPOS_TEXTO:
        dados[campo] = texto_limpo(form.get(campo))
    for campo in CAMPOS_TELEFONE:
        dados[campo] = texto_limpo(form.get(campo))
    return dados


def _validar(dados, ignorar_id=None):
    erros = []
    if not dados["nome"]:
        erros.append("Informe o nome do cliente.")

    ehpj = dados["tipo_pessoa"] == "Pessoa Jurídica"
    digitos = so_digitos(dados["cpf_cnpj"])
    if ehpj:
        if not validar_cnpj(digitos):
            erros.append("CNPJ inválido. O CNPJ deve ter exatamente 14 números e dígitos verificadores corretos.")
        else:
            dados["cpf_cnpj"] = formatar_cnpj(digitos)
    else:
        if not validar_cpf(digitos):
            erros.append("CPF inválido. O CPF deve ter exatamente 11 números e dígitos verificadores corretos.")
        else:
            dados["cpf_cnpj"] = formatar_cpf(digitos)

    if not erros and dados["cpf_cnpj"]:
        existe = Cliente.query.filter(Cliente.cpf_cnpj == dados["cpf_cnpj"], Cliente.ativo.is_(True))
        if ignorar_id:
            existe = existe.filter(Cliente.id != ignorar_id)
        outro = existe.first()
        if outro:
            erros.append(f"Já existe um cliente cadastrado com este documento: {outro.nome_exibicao}.")

    if not dados["telefone"]:
        erros.append("Informe o telefone do cliente.")
    for campo, rotulo in (("telefone", "Telefone"), ("telefone2", "Comercial/FAX"), ("celular_whatsapp", "Celular/WhatsApp")):
        if dados[campo]:
            if len(so_digitos(dados[campo])) not in (10, 11):
                erros.append(f"{rotulo} inválido: use DDD + número (10 ou 11 dígitos).")
            else:
                dados[campo] = formatar_telefone(dados[campo])

    if dados["cep"]:
        if len(so_digitos(dados["cep"])) != 8:
            erros.append("CEP inválido: deve ter 8 números.")
        else:
            dados["cep"] = formatar_cep(dados["cep"])

    for campo, rotulo in (("email", "E-mail"), ("email_notas_fiscais", "E-mail para notas fiscais")):
        if dados[campo] and not EMAIL_RE.match(dados[campo]):
            erros.append(f"{rotulo} inválido.")
    return erros


def _aplicar(cliente, dados):
    for campo, valor in dados.items():
        setattr(cliente, campo, valor)


def _vinculos(cliente):
    return {
        "ordens": OrdemServico.query.filter_by(cliente_id=cliente.id).count(),
        "vendas": len(cliente.vendas),
        "contas": ContaReceber.query.filter_by(cliente_id=cliente.id).count(),
    }


@bp.route("/")
@login_required
def listar():
    busca = request.args.get("q", "").strip()
    query = Cliente.query.filter_by(ativo=True)
    if busca:
        termo = f"%{busca}%"
        filtros = [
            Cliente.nome.ilike(termo),
            Cliente.nome_fantasia.ilike(termo),
            Cliente.cpf_cnpj.ilike(termo),
            Cliente.telefone.ilike(termo),
            Cliente.email.ilike(termo),
        ]
        digitos = so_digitos(busca)
        if len(digitos) >= 3:
            limpo = func.replace(func.replace(func.replace(Cliente.cpf_cnpj, ".", ""), "-", ""), "/", "")
            fone = func.replace(func.replace(func.replace(func.replace(Cliente.telefone, "(", ""), ")", ""), "-", ""), " ", "")
            filtros += [limpo.ilike(f"%{digitos}%"), fone.ilike(f"%{digitos}%")]
        query = query.filter(or_(*filtros))
    clientes = query.order_by(Cliente.nome).all()
    return render_template("clientes/listar.html", clientes=clientes, busca=busca)


@bp.route("/novo", methods=["GET", "POST"])
@login_required
def novo():
    if request.method == "POST":
        dados = _extrair(request.form)
        erros = _validar(dados)
        if erros:
            for e in erros:
                flash(e, "danger")
            return render_template("clientes/form.html", c=SimpleNamespace(id=None, **dados),
                                   editando=False, tipos_pessoa=TIPOS_PESSOA)

        cliente = Cliente()
        _aplicar(cliente, dados)
        db.session.add(cliente)
        db.session.commit()
        flash(f"Cliente '{cliente.nome_exibicao}' cadastrado com sucesso!", "success")

        # Se veio da abertura de OS, já redireciona para continuar o fluxo
        if request.form.get("continuar_para_os"):
            return redirect(url_for("ordens.nova", cliente_id=cliente.id))
        return redirect(url_for("clientes.detalhe", id=cliente.id))

    return render_template("clientes/form.html", c=SimpleNamespace(id=None, pais="Brasil", tipo_pessoa="Pessoa Física"),
                           editando=False, tipos_pessoa=TIPOS_PESSOA)


@bp.route("/<int:id>")
@login_required
def detalhe(id):
    cliente = Cliente.query.get_or_404(id)
    return render_template("clientes/detalhe.html", cliente=cliente, vinculos=_vinculos(cliente))


@bp.route("/<int:id>/editar", methods=["GET", "POST"])
@login_required
def editar(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == "POST":
        dados = _extrair(request.form)
        erros = _validar(dados, ignorar_id=cliente.id)
        if erros:
            for e in erros:
                flash(e, "danger")
            return render_template("clientes/form.html", c=SimpleNamespace(id=cliente.id, **dados),
                                   editando=True, tipos_pessoa=TIPOS_PESSOA)
        _aplicar(cliente, dados)
        db.session.commit()
        flash("Dados do cliente atualizados!", "success")
        return redirect(url_for("clientes.detalhe", id=cliente.id))

    return render_template("clientes/form.html", c=cliente, editando=True, tipos_pessoa=TIPOS_PESSOA)


@bp.route("/<int:id>/inativar", methods=["POST"])
@login_required
def inativar(id):
    cliente = Cliente.query.get_or_404(id)
    cliente.ativo = False
    db.session.commit()
    flash("Cliente inativado. Ele não aparece mais na lista, mas o histórico foi mantido.", "info")
    return redirect(url_for("clientes.listar"))


@bp.route("/<int:id>/excluir", methods=["POST"])
@login_required
def excluir(id):
    cliente = Cliente.query.get_or_404(id)
    nome = cliente.nome_exibicao
    vinculos = _vinculos(cliente)
    tem_historico = any(vinculos.values())

    if tem_historico:
        if not current_user.is_admin:
            flash("Este cliente tem ordens de serviço, vendas ou contas. Só o administrador pode excluir "
                  "definitivamente. Você pode inativá-lo para tirá-lo da lista.", "warning")
            return redirect(url_for("clientes.detalhe", id=cliente.id))

        # Exclusão definitiva: apaga as OS (e fotos/contas delas); vendas ficam sem cliente identificado
        pasta_base = os.path.join(current_app.root_path, "static", "uploads", "ordens")
        for ordem in list(cliente.ordens):
            ContaReceber.query.filter_by(origem="Ordem de Serviço", origem_id=ordem.id).delete()
            shutil.rmtree(os.path.join(pasta_base, str(ordem.id)), ignore_errors=True)
        for venda in cliente.vendas:
            venda.cliente_id = None
        ContaReceber.query.filter(ContaReceber.cliente_id == cliente.id).update({"cliente_id": None})
        db.session.flush()

    db.session.delete(cliente)
    db.session.commit()
    flash(f"Cliente '{nome}' excluído.", "success")
    return redirect(url_for("clientes.listar"))

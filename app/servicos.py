"""Regras compartilhadas entre Vendas, Ordens de Serviço e Financeiro.

Tudo que entra de dinheiro (venda ou OS) vira uma linha em Contas a Receber:
  - pagamento à vista (Pix, dinheiro, cartão...)  -> conta com status "Pago"
  - venda futura (fiado)                          -> conta com status "Pendente"
Ao dar baixa em uma conta, o pagamento de origem (venda/OS) também é atualizado.
"""
from datetime import datetime

from .extensions import db
from .models import ContaReceber, Pagamento, Venda, OrdemServico

FIADO = "Venda Futura (Fiado)"
ABERTAS = ("Pendente", "Atrasado")


def lancar_conta_receber(descricao, cliente_id, origem, origem_id, valor, forma,
                         status="Pago", vencimento=None, data_pagamento=None):
    agora = data_pagamento or datetime.now()
    conta = ContaReceber(
        descricao=descricao, cliente_id=cliente_id, origem=origem, origem_id=origem_id,
        valor=valor, forma_pagamento=forma, status=status,
        data_vencimento=vencimento or agora.date(),
        data_pagamento=agora if status == "Pago" else None,
    )
    db.session.add(conta)
    return conta


def _pagamentos_da_origem(conta):
    if conta.origem == "Venda":
        return Pagamento.query.filter_by(venda_id=conta.origem_id).all()
    if conta.origem == "Ordem de Serviço":
        return Pagamento.query.filter_by(ordem_id=conta.origem_id).all()
    return []


def _escolher(pagamentos, status, valor):
    candidatos = [p for p in pagamentos if p.status == status]
    for p in candidatos:
        if abs((p.valor or 0) - (valor or 0)) < 0.01:
            return p
    return candidatos[0] if candidatos else None


def _atualizar_status_venda(venda_id):
    venda = Venda.query.get(venda_id)
    if not venda or venda.status == "Cancelada":
        return
    pendente = any(p.status == "Pendente" for p in venda.pagamentos)
    venda.status = "Fiado (a receber)" if pendente else "Concluída"


def baixar_conta_receber(conta, forma=None, data_pagamento=None):
    """Marca a conta como paga e acompanha o pagamento da venda/OS de origem."""
    if forma == FIADO:
        forma = None
    conta.status = "Pago"
    conta.data_pagamento = data_pagamento or datetime.now()
    if forma:
        conta.forma_pagamento = forma
    elif conta.forma_pagamento == FIADO or not conta.forma_pagamento:
        conta.forma_pagamento = "Dinheiro"

    alvo = _escolher(_pagamentos_da_origem(conta), "Pendente", conta.valor)
    if alvo:
        alvo.status = "Pago"
        alvo.forma_pagamento = conta.forma_pagamento
        alvo.data_pagamento = conta.data_pagamento
    if conta.origem == "Venda":
        _atualizar_status_venda(conta.origem_id)


def estornar_conta_receber(conta):
    """Desfaz a baixa: a conta volta para pendente."""
    alvo = _escolher(_pagamentos_da_origem(conta), "Pago", conta.valor)
    if alvo:
        alvo.status = "Pendente"
    conta.status = "Pendente"
    conta.data_pagamento = None
    if conta.origem == "Venda":
        _atualizar_status_venda(conta.origem_id)


def cancelar_conta_receber(conta):
    alvo = _escolher(_pagamentos_da_origem(conta), "Pendente", conta.valor)
    if alvo:
        alvo.status = "Cancelado"
    conta.status = "Cancelado"
    if conta.origem == "Venda":
        _atualizar_status_venda(conta.origem_id)


def dar_baixa_origem(origem, origem_id, forma, data_pagamento=None):
    """Dá baixa em todos os valores pendentes de uma venda ou OS. Retorna quantos foram baixados."""
    contas = ContaReceber.query.filter(
        ContaReceber.origem == origem, ContaReceber.origem_id == origem_id,
        ContaReceber.status.in_(ABERTAS),
    ).all()
    for conta in contas:
        baixar_conta_receber(conta, forma, data_pagamento)
    total = len(contas)

    # Pagamentos pendentes antigos que nunca geraram conta
    if origem == "Venda":
        venda = Venda.query.get(origem_id)
        pagamentos, cliente_id, rotulo = (venda.pagamentos, venda.cliente_id, f"Venda {venda.numero}") if venda else ([], None, "")
    else:
        ordem = OrdemServico.query.get(origem_id)
        pagamentos, cliente_id, rotulo = (
            (ordem.pagamentos, ordem.cliente_id, f"OS {ordem.numero} - {ordem.cliente.nome_exibicao}") if ordem else ([], None, "")
        )
    for p in pagamentos:
        if p.status == "Pendente":
            p.status = "Pago"
            p.forma_pagamento = forma if forma and forma != FIADO else "Dinheiro"
            p.data_pagamento = data_pagamento or datetime.now()
            lancar_conta_receber(rotulo, cliente_id, origem, origem_id, p.valor, p.forma_pagamento,
                                 "Pago", data_pagamento=p.data_pagamento)
            total += 1
    if origem == "Venda":
        _atualizar_status_venda(origem_id)
    return total


def sincronizar_contas_receber():
    """Corrige dados antigos: pagamentos já feitos que não apareciam em Contas a Receber."""
    novos = 0
    for p in Pagamento.query.filter_by(status="Pago").all():
        if p.venda_id and p.venda:
            origem, origem_id, cliente_id = "Venda", p.venda_id, p.venda.cliente_id
            rotulo = f"Venda {p.venda.numero}"
            if p.venda.status == "Cancelada":
                continue
        elif p.ordem_id and p.ordem:
            origem, origem_id, cliente_id = "Ordem de Serviço", p.ordem_id, p.ordem.cliente_id
            rotulo = f"OS {p.ordem.numero} - {p.ordem.cliente.nome_exibicao}"
        else:
            continue
        existentes = ContaReceber.query.filter_by(origem=origem, origem_id=origem_id).all()
        if any(abs((c.valor or 0) - (p.valor or 0)) < 0.01 and c.status in ("Pago", "Cancelado") for c in existentes):
            continue
        lancar_conta_receber(rotulo, cliente_id, origem, origem_id, p.valor, p.forma_pagamento,
                             "Pago", data_pagamento=p.data_pagamento)
        novos += 1

    # Conta já paga (baixa antiga) mas o pagamento de origem ficou pendente
    for conta in ContaReceber.query.filter_by(status="Pago").filter(
            ContaReceber.origem.in_(["Venda", "Ordem de Serviço"])).all():
        alvo = _escolher(_pagamentos_da_origem(conta), "Pendente", conta.valor)
        if alvo:
            alvo.status = "Pago"
            alvo.forma_pagamento = conta.forma_pagamento or alvo.forma_pagamento
            alvo.data_pagamento = conta.data_pagamento
        if conta.origem == "Venda":
            _atualizar_status_venda(conta.origem_id)
    db.session.commit()
    return novos


COLUNAS_TEXTO_CLIENTE = [
    "rg_ie", "nome_fantasia", "contato", "telefone2", "celular_whatsapp", "radio", "site",
    "email", "email_notas_fiscais", "cep", "endereco", "numero", "bairro", "complemento",
    "cidade", "grupo", "sexo", "observacoes",
]


def manutencao_dados():
    """Roda uma vez ao iniciar: limpa textos 'None' e inclui no financeiro o que ficou de fora."""
    from sqlalchemy import text
    try:
        if db.engine.dialect.name == "postgresql":
            # Evita que dois processos rodem a manutenção ao mesmo tempo
            if not db.session.execute(text("SELECT pg_try_advisory_xact_lock(918273645)")).scalar():
                db.session.rollback()
                return
        for coluna in COLUNAS_TEXTO_CLIENTE:
            db.session.execute(text(
                f"UPDATE cliente SET {coluna} = NULL WHERE {coluna} IN ('None', 'none', 'null', '')"
            ))
        novos = sincronizar_contas_receber()   # faz o commit
        if novos:
            print(f"{novos} recebimento(s) antigo(s) incluído(s) em Contas a Receber.")
    except Exception as erro:  # nunca derruba o sistema por causa da manutenção
        db.session.rollback()
        print("Aviso: manutenção de dados não executada:", erro)

from datetime import datetime


def gerar_numero(model, campo_numero, prefixo):
    """Gera o próximo número sequencial no formato PREFIXO-0001."""
    ultimo = model.query.order_by(model.id.desc()).first()
    proximo = (ultimo.id + 1) if ultimo else 1
    return f"{prefixo}-{proximo:04d}"


def formatar_moeda(valor):
    try:
        valor = float(valor or 0)
    except (TypeError, ValueError):
        valor = 0
    texto = f"{valor:,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"R$ {texto}"


def formatar_data(data, com_hora=False):
    if not data:
        return "-"
    fmt = "%d/%m/%Y %H:%M" if com_hora else "%d/%m/%Y"
    return data.strftime(fmt)


def parse_float(valor, padrao=0.0):
    if valor is None or valor == "":
        return padrao
    try:
        if isinstance(valor, str):
            valor = valor.replace(".", "").replace(",", ".") if "," in valor else valor
        return float(valor)
    except (TypeError, ValueError):
        return padrao


def parse_data(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None

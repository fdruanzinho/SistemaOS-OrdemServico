from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

# ---------------------------------------------------------------------------
# Listas de opções (choices) usadas em vários formulários
# ---------------------------------------------------------------------------

TIPOS_PESSOA = ["Pessoa Física", "Pessoa Jurídica"]

TIPOS_EQUIPAMENTO = [
    "Computador (Desktop)", "Notebook", "Impressora", "Monitor",
    "SSD/HD", "Placa-mãe", "Fonte", "Nobreak/Estabilizador",
    "Roteador/Rede", "Celular/Tablet", "Outro",
]

STATUS_OS = [
    "Aberta / Aguardando avaliação",
    "Na bancada",
    "Aguardando aprovação do orçamento",
    "Aguardando peça",
    "Em conserto",
    "Equipamento pronto",
    "Equipamento entregue",
    "Equipamento condenado",
    "Cancelada",
]

STATUS_OS_FINALIZADOS = ["Equipamento entregue", "Cancelada", "Equipamento condenado"]

FORMAS_PAGAMENTO = [
    "Pix", "Dinheiro", "Cartão de Crédito", "Cartão de Débito",
    "Boleto", "Transferência", "Venda Futura (Fiado)",
]

TIPOS_ITEM_OS = ["Peça", "Serviço"]

STATUS_FINANCEIRO = ["Pendente", "Pago", "Atrasado", "Cancelado"]

STATUS_NOTA_FISCAL = ["Pendente de conferência", "Conferida", "Divergente", "Cancelada"]

STATUS_VENDA = ["Concluída", "Cancelada", "Fiado (a receber)"]


# ---------------------------------------------------------------------------
# Usuários / Técnicos (login do sistema)
# ---------------------------------------------------------------------------

class Usuario(db.Model, UserMixin):
    __tablename__ = "usuario"
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    cargo = db.Column(db.String(60), default="Técnico")
    ativo = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)


# ---------------------------------------------------------------------------
# Cliente
# ---------------------------------------------------------------------------

class Cliente(db.Model):
    __tablename__ = "cliente"
    id = db.Column(db.Integer, primary_key=True)
    tipo_pessoa = db.Column(db.String(20), default="Pessoa Física", nullable=False)
    cpf_cnpj = db.Column(db.String(20), nullable=False, index=True)
    rg_ie = db.Column(db.String(30))                           # RG (PF) ou Inscrição Estadual (PJ)
    nome = db.Column(db.String(150), nullable=False)          # Nome / Razão Social
    nome_fantasia = db.Column(db.String(150))                  # Apelido / Nome Fantasia (PJ)
    contato = db.Column(db.String(120))                        # Pessoa de contato (PJ)
    telefone = db.Column(db.String(30), nullable=False)
    telefone2 = db.Column(db.String(30))                       # Comercial/FAX
    celular_whatsapp = db.Column(db.String(30))
    radio = db.Column(db.String(30))
    site = db.Column(db.String(150))
    email = db.Column(db.String(150))
    email_notas_fiscais = db.Column(db.String(150))
    cep = db.Column(db.String(12))
    endereco = db.Column(db.String(200))
    numero = db.Column(db.String(20))
    bairro = db.Column(db.String(100))
    complemento = db.Column(db.String(120))
    cidade = db.Column(db.String(100))
    estado = db.Column(db.String(2))
    pais = db.Column(db.String(60), default="Brasil")
    grupo = db.Column(db.String(60))
    sexo = db.Column(db.String(20))
    aniversario = db.Column(db.Date)
    observacoes = db.Column(db.Text)
    ativo = db.Column(db.Boolean, default=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)

    equipamentos = db.relationship("Equipamento", backref="cliente", cascade="all, delete-orphan")
    ordens = db.relationship("OrdemServico", backref="cliente", cascade="all, delete-orphan")
    vendas = db.relationship("Venda", backref="cliente")
    contas_receber = db.relationship("ContaReceber", backref="cliente")

    @property
    def endereco_completo(self):
        partes = [self.endereco, self.numero, self.bairro, self.complemento]
        linha1 = ", ".join([p for p in partes if p])
        partes2 = [self.cidade, self.estado]
        linha2 = " - ".join([p for p in partes2 if p])
        return " | ".join([p for p in [linha1, linha2, self.cep] if p])

    @property
    def nome_exibicao(self):
        return self.nome_fantasia or self.nome


# ---------------------------------------------------------------------------
# Equipamento (o item físico trazido pelo cliente)
# ---------------------------------------------------------------------------

class Equipamento(db.Model):
    __tablename__ = "equipamento"
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)

    tipo = db.Column(db.String(60), nullable=False)     # Computador, Impressora, SSD...
    marca = db.Column(db.String(80))
    modelo = db.Column(db.String(120))
    numero_serie = db.Column(db.String(120))
    cor = db.Column(db.String(60))
    senha_acesso = db.Column(db.String(120))            # senha do equipamento/BIOS informada pelo cliente
    acessorios = db.Column(db.String(250))              # o que acompanha: carregador, mouse, cabo, etc.
    condicao_entrada = db.Column(db.Text)               # estado físico ao dar entrada (riscos, avarias etc.)

    ordens = db.relationship("OrdemServico", backref="equipamento", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Ordem de Serviço
# ---------------------------------------------------------------------------

class OrdemServico(db.Model):
    __tablename__ = "ordem_servico"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)

    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"), nullable=False)
    equipamento_id = db.Column(db.Integer, db.ForeignKey("equipamento.id"), nullable=False)
    tecnico_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))

    data_entrada = db.Column(db.DateTime, default=datetime.now, nullable=False)
    data_previsao = db.Column(db.Date)
    data_conclusao = db.Column(db.DateTime)
    data_entrega = db.Column(db.DateTime)

    defeito_relatado = db.Column(db.Text, nullable=False)   # descrição do cliente
    laudo_tecnico = db.Column(db.Text)                       # diagnóstico / relatório técnico
    observacoes = db.Column(db.Text)                         # observações internas

    status = db.Column(db.String(60), default=STATUS_OS[0], nullable=False)

    valor_orcamento = db.Column(db.Float, default=0)
    valor_desconto = db.Column(db.Float, default=0)
    valor_adiantamento = db.Column(db.Float, default=0)
    garantia_dias = db.Column(db.Integer, default=90)

    data_cadastro = db.Column(db.DateTime, default=datetime.now)

    tecnico = db.relationship("Usuario", foreign_keys=[tecnico_id])
    itens = db.relationship("OrdemItem", backref="ordem", cascade="all, delete-orphan")
    fotos = db.relationship("OrdemFoto", backref="ordem", cascade="all, delete-orphan")
    historico = db.relationship(
        "OrdemHistorico", backref="ordem", cascade="all, delete-orphan",
        order_by="OrdemHistorico.data.desc()"
    )
    pagamentos = db.relationship("Pagamento", backref="ordem", cascade="all, delete-orphan")

    @property
    def valor_itens(self):
        return sum(i.valor_total for i in self.itens)

    @property
    def valor_total(self):
        return max((self.valor_itens or self.valor_orcamento or 0) - (self.valor_desconto or 0), 0)

    @property
    def valor_pago(self):
        return sum(p.valor for p in self.pagamentos if p.status == "Pago") + (self.valor_adiantamento or 0)

    @property
    def valor_pendente(self):
        return max(self.valor_total - self.valor_pago, 0)

    @property
    def finalizada(self):
        return self.status in STATUS_OS_FINALIZADOS


class OrdemItem(db.Model):
    """Peças e serviços lançados numa Ordem de Serviço."""
    __tablename__ = "ordem_item"
    id = db.Column(db.Integer, primary_key=True)
    ordem_id = db.Column(db.Integer, db.ForeignKey("ordem_servico.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"))  # opcional, se veio do estoque

    tipo = db.Column(db.String(20), default="Peça", nullable=False)   # Peça ou Serviço
    descricao = db.Column(db.String(200), nullable=False)
    quantidade = db.Column(db.Float, default=1)
    valor_unitario = db.Column(db.Float, default=0)

    produto = db.relationship("Produto")

    @property
    def valor_total(self):
        return (self.quantidade or 0) * (self.valor_unitario or 0)


class OrdemHistorico(db.Model):
    """Log de mudanças de status da OS - atualização em tempo real pelos técnicos."""
    __tablename__ = "ordem_historico"
    id = db.Column(db.Integer, primary_key=True)
    ordem_id = db.Column(db.Integer, db.ForeignKey("ordem_servico.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    data = db.Column(db.DateTime, default=datetime.now)
    status_anterior = db.Column(db.String(60))
    status_novo = db.Column(db.String(60))
    observacao = db.Column(db.Text)

    usuario = db.relationship("Usuario")


# ---------------------------------------------------------------------------
# Pagamentos (usados por OS e por Vendas)
# ---------------------------------------------------------------------------

class Pagamento(db.Model):
    __tablename__ = "pagamento"
    id = db.Column(db.Integer, primary_key=True)
    ordem_id = db.Column(db.Integer, db.ForeignKey("ordem_servico.id"))
    venda_id = db.Column(db.Integer, db.ForeignKey("venda.id"))

    forma_pagamento = db.Column(db.String(40), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    parcelas = db.Column(db.Integer, default=1)
    data_pagamento = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(20), default="Pago")
    observacao = db.Column(db.String(200))


# ---------------------------------------------------------------------------
# Estoque
# ---------------------------------------------------------------------------

class Produto(db.Model):
    __tablename__ = "produto"
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(40), unique=True)
    nome = db.Column(db.String(150), nullable=False)
    categoria = db.Column(db.String(80))
    grupo = db.Column(db.String(80))
    secao = db.Column(db.String(80))
    marca = db.Column(db.String(80))
    ncm = db.Column(db.String(20))
    codigo_barras = db.Column(db.String(60))
    descricao = db.Column(db.Text)
    unidade = db.Column(db.String(10), default="UN")
    quantidade_estoque = db.Column(db.Float, default=0)
    estoque_minimo = db.Column(db.Float, default=0)
    estoque_maximo = db.Column(db.Float, default=0)
    preco_custo = db.Column(db.Float, default=0)
    preco_venda = db.Column(db.Float, default=0)
    ativo = db.Column(db.Boolean, default=True)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)

    @property
    def estoque_baixo(self):
        return self.quantidade_estoque <= (self.estoque_minimo or 0)


class MovimentoEstoque(db.Model):
    """Histórico de entradas/saídas de estoque, para rastreabilidade."""
    __tablename__ = "movimento_estoque"
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)   # Entrada / Saída
    quantidade = db.Column(db.Float, nullable=False)
    origem = db.Column(db.String(120))                # ex: "Venda #12", "OS #34", "Ajuste manual"
    data = db.Column(db.DateTime, default=datetime.now)

    produto = db.relationship("Produto")


# ---------------------------------------------------------------------------
# Vendas
# ---------------------------------------------------------------------------

class Venda(db.Model):
    __tablename__ = "venda"
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))
    vendedor_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))

    data_venda = db.Column(db.DateTime, default=datetime.now)
    valor_desconto = db.Column(db.Float, default=0)
    status = db.Column(db.String(30), default="Concluída")
    observacoes = db.Column(db.String(250))

    vendedor = db.relationship("Usuario")
    itens = db.relationship("VendaItem", backref="venda", cascade="all, delete-orphan")
    pagamentos = db.relationship("Pagamento", backref="venda", cascade="all, delete-orphan")

    @property
    def valor_itens(self):
        return sum(i.valor_total for i in self.itens)

    @property
    def valor_total(self):
        return max(self.valor_itens - (self.valor_desconto or 0), 0)


class VendaItem(db.Model):
    __tablename__ = "venda_item"
    id = db.Column(db.Integer, primary_key=True)
    venda_id = db.Column(db.Integer, db.ForeignKey("venda.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produto.id"))  # opcional - pode ser item avulso
    descricao = db.Column(db.String(200))              # usado quando não vem do estoque (item avulso)
    quantidade = db.Column(db.Float, default=1)
    valor_unitario = db.Column(db.Float, default=0)

    produto = db.relationship("Produto")

    @property
    def nome_exibicao(self):
        return self.produto.nome if self.produto else (self.descricao or "Item avulso")

    @property
    def valor_total(self):
        return (self.quantidade or 0) * (self.valor_unitario or 0)


# ---------------------------------------------------------------------------
# Financeiro: Contas a Receber e Contas a Pagar
# ---------------------------------------------------------------------------

class ContaReceber(db.Model):
    __tablename__ = "conta_receber"
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("cliente.id"))
    origem = db.Column(db.String(40))          # "Ordem de Serviço", "Venda", "Avulso"
    origem_id = db.Column(db.Integer)          # id da OS ou Venda relacionada
    valor = db.Column(db.Float, nullable=False)
    data_lancamento = db.Column(db.DateTime, default=datetime.now)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="Pendente")
    forma_pagamento = db.Column(db.String(40))
    observacoes = db.Column(db.String(250))


class ContaPagar(db.Model):
    __tablename__ = "conta_pagar"
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    fornecedor_nome = db.Column(db.String(150))     # nome digitado livremente
    categoria = db.Column(db.String(80))       # Fornecedor, Aluguel, Energia, Salário, etc.
    origem = db.Column(db.String(40))          # "Avulso"
    origem_id = db.Column(db.Integer)
    numero_documento = db.Column(db.String(60))
    valor = db.Column(db.Float, nullable=False)
    data_lancamento = db.Column(db.DateTime, default=datetime.now)
    data_vencimento = db.Column(db.Date, nullable=False)
    data_pagamento = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="Pendente")
    forma_pagamento = db.Column(db.String(40))
    observacoes = db.Column(db.String(250))


# ---------------------------------------------------------------------------
# Agenda de Compromissos
# ---------------------------------------------------------------------------

class Compromisso(db.Model):
    __tablename__ = "compromisso"
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.Text, nullable=False)
    dia = db.Column(db.Date, nullable=False, index=True)
    hora = db.Column(db.String(5), default="00:00")   # HH:MM
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuario.id"))
    avisar = db.Column(db.Boolean, default=False)
    concluido = db.Column(db.Boolean, default=False)
    data_cadastro = db.Column(db.DateTime, default=datetime.now)

    usuario = db.relationship("Usuario")


class OrdemFoto(db.Model):
    """Fotos do equipamento anexadas à Ordem de Serviço."""
    __tablename__ = "ordem_foto"
    id = db.Column(db.Integer, primary_key=True)
    ordem_id = db.Column(db.Integer, db.ForeignKey("ordem_servico.id"), nullable=False)
    arquivo = db.Column(db.String(255), nullable=False)   # nome do arquivo salvo em disco
    legenda = db.Column(db.String(150))
    data_upload = db.Column(db.DateTime, default=datetime.now)

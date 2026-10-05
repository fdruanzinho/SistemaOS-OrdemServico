# Sistema de Ordem de Serviço — Gestão Completa

Sistema completo de gestão para assistência técnica de informática, contemplando:

- **Clientes** (Pessoa Física / Pessoa Jurídica) com cadastro completo
- **Ordens de Serviço** com abertura detalhada do equipamento, acompanhamento em
  tempo real pelos técnicos (status, laudo técnico, histórico), peças e serviços,
  fotos do equipamento, pagamento (Pix com QR Code, cartão, boleto etc.) e
  impressão de comprovante
- **Agenda de Compromissos** com calendário mensal clicável e visão semanal
- **Estoque** de peças e produtos, com movimentações e alerta de estoque mínimo
- **Vendas** (PDV simples de balcão): itens do estoque com baixa automática, ou
  itens avulsos digitados na hora (quando o item vendido não está no estoque)
- **Financeiro**: Contas a Receber e Contas a Pagar, integrado automaticamente
  com Ordens de Serviço (venda futura/fiado) e Vendas
- **Login de usuários/técnicos**, para saber quem atualizou cada ordem de serviço

Feito em **Flask + PostgreSQL**, pensado para rodar em um computador "servidor"
da empresa e ser acessado pelos demais computadores da rede local pelo navegador.

---

## 1. Pré-requisitos

- **Python 3.11 ou superior** — https://www.python.org/downloads/ (marque a
  opção "Add Python to PATH" na instalação, no Windows)
- **PostgreSQL** — https://www.postgresql.org/download/ (anote a senha do
  usuário `postgres` que você definir na instalação)

## 2. Instalação (no computador que será o "servidor")

Abra o terminal (PowerShell/CMD no Windows, ou Terminal no Linux/Mac) dentro
da pasta do sistema e rode:

```bash
# 1. Criar um ambiente virtual (recomendado)
python -m venv venv

# 2. Ativar o ambiente virtual
venv\Scripts\activate        # Windows
source venv/bin/activate     # Linux/Mac

# 3. Instalar as dependências
pip install -r requirements.txt
```

### Criar o banco de dados

Com o PostgreSQL instalado, crie um banco de dados vazio chamado, por exemplo,
`ordem_servico`. Você pode fazer isso pelo **pgAdmin** (interface gráfica que
já vem com o PostgreSQL) ou pelo terminal:

```bash
createdb -U postgres ordem_servico
```

### Configurar as variáveis de ambiente

Copie o arquivo `.env.example` e renomeie a cópia para `.env`. Abra o `.env`
e ajuste:

```
SECRET_KEY=alguma-string-aleatoria-bem-grande
DATABASE_URL=postgresql://postgres:SUA_SENHA@localhost:5432/ordem_servico
EMPRESA_NOME=Nome da sua empresa
EMPRESA_CNPJ=00.000.000/0000-00
EMPRESA_ENDERECO=Endereço completo
EMPRESA_TELEFONE=(00) 0000-0000
```

Para o **QR Code de pagamento Pix** funcionar nas telas de Vendas e Ordem de Serviço,
adicione também no `.env`:

```
EMPRESA_PIX_CHAVE=sua-chave-pix-aqui
EMPRESA_PIX_NOME=NOME DA EMPRESA
EMPRESA_PIX_CIDADE=SUA CIDADE
```

## 3. Rodando o sistema

```bash
python run.py
```

Na primeira execução, o sistema cria automaticamente as tabelas do banco de
dados e um usuário administrador padrão:

```
E-mail: admin@sistema.com
Senha:  admin123
```

**Troque essa senha assim que possível**, cadastrando um novo usuário
administrador em *Administração > Usuários / Técnicos* e inativando o padrão,
ou simplesmente alterando a senha diretamente (peça ajuda se precisar de uma
tela de "alterar senha" — é uma extensão simples de adicionar).

## 4. Acessando de outros computadores da rede

O sistema já sobe configurado para aceitar conexões de qualquer computador da
rede local (`host="0.0.0.0"` no `run.py`). Para acessar de outro PC:

1. Descubra o IP do computador servidor na rede local:
   - Windows: abra o CMD e digite `ipconfig`, veja o "Endereço IPv4"
     (algo como `192.168.0.10`)
2. Nos outros computadores, abra o navegador e acesse:
   `http://192.168.0.10:5000` (troque pelo IP real do servidor)

**Importante:** o computador servidor precisa ficar ligado com o sistema
rodando (`python run.py`) para os outros acessarem. Se o Firewall do Windows
bloquear, será necessário liberar a porta 5000 nas configurações do Firewall
("Permitir um aplicativo pelo Firewall do Windows").

Para o sistema iniciar automaticamente com o Windows e não precisar abrir o
terminal manualmente todos os dias, o ideal é configurá-lo como um serviço
(ex: usando o NSSM) ou colocar um atalho do `run.py` na pasta de Inicialização
do Windows — posso te ajudar a montar isso também, se quiser.

## 5. Estrutura do projeto

```
SistemaOS/
├── run.py                     # ponto de entrada
├── requirements.txt
├── .env.example                # copie para .env e configure
├── app/
│   ├── __init__.py             # criação da aplicação Flask
│   ├── extensions.py           # instâncias do banco e do login
│   ├── models.py               # todas as tabelas do sistema
│   ├── utils.py                 # funções auxiliares
│   ├── blueprints/              # as rotas, separadas por módulo
│   │   ├── auth.py
│   │   ├── main.py               # dashboard
│   │   ├── clientes.py
│   │   ├── ordens.py
│   │   ├── estoque.py
│   │   ├── vendas.py
│   │   ├── financeiro.py
│   │   └── notas_fiscais.py
│   ├── templates/                # as telas (HTML)
│   └── static/css/style.css      # visual do sistema
```

## 6. Fluxo de uso resumido

1. **Cliente novo chega:** Clientes > Novo Cliente (ou direto pelo botão
   "Cliente Novo" na tela de Nova OS) → preenche CPF/CNPJ, nome, contato,
   endereço, telefone, e-mail etc.
2. **Abrir a OS:** logo depois de cadastrar o cliente, o sistema já leva para
   a abertura da Ordem de Serviço, onde se descreve o equipamento (tipo, marca,
   modelo, número de série, acessórios, condição de entrada) e o defeito
   relatado.
3. **Acompanhamento:** na tela da OS, os técnicos atualizam o status (Na
   bancada, Aguardando peça, Pronto, Entregue, Condenado etc.), preenchem o
   laudo técnico, lançam peças (inclusive puxando direto do estoque, com baixa
   automática) e serviços realizados. Tudo fica registrado no histórico com
   data/hora e quem fez a alteração.
4. **Pagamento:** ao finalizar, registra-se o pagamento (Pix, dinheiro,
   cartão, boleto ou "Venda Futura/Fiado" — que gera automaticamente uma conta
   a receber).
5. **Vendas de balcão:** módulo separado de PDV para vender produtos do
   estoque, com ou sem cliente identificado.
6. **Chegada de mercadoria:** cadastre a Nota Fiscal do fornecedor com os
   itens esperados e depois faça a conferência física — o sistema aponta
   divergências, atualiza o estoque e já gera a conta a pagar.
7. **Financeiro:** acompanhe tudo isso (mais lançamentos avulsos) nas telas de
   Contas a Receber e Contas a Pagar, com alerta de vencimento no Dashboard.

---

## Observações importantes

- Este sistema foi construído e revisado neste ambiente, incluindo checagem de
  sintaxe de todo o código Python e de todos os templates, e conferência
  cruzada de que toda rota/link do sistema aponta para uma página que
  realmente existe. Ainda assim, **como aqui não havia acesso a um banco
  PostgreSQL real para rodar um teste de ponta a ponta**, é importante que,
  ao rodar pela primeira vez na sua máquina, você navegue por todas as telas
  testando o fluxo completo antes de colocar em uso na empresa. Qualquer erro
  encontrado, me mostre a mensagem que eu corrijo rapidamente.
- O sistema usa Bootstrap via internet (CDN) para o visual — é necessário que
  o computador que acessa o sistema tenha internet para os ícones e estilos
  carregarem corretamente (mas o sistema em si roda 100% localmente, sem
  depender de internet para funcionar).
- Sugestões de próximos passos, se fizerem sentido para o seu negócio: tela de
  "alterar minha senha", relatório/exportação de vendas e OS em PDF/Excel,
  gráficos financeiros no dashboard, backup automático do banco de dados.

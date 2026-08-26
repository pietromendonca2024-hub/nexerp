from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from functools import wraps

app = Flask(__name__)
app.secret_key = "nexerp-chave-secreta"


def conectar():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    return conn


def criar_banco():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS produtos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            preco REAL NOT NULL,
            estoque INTEGER NOT NULL DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            produto_id INTEGER NOT NULL,
            quantidade INTEGER NOT NULL,
            valor_total REAL NOT NULL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cliente_id INTEGER,
            forma_pagamento TEXT,
            FOREIGN KEY (produto_id) REFERENCES produtos(id),
            FOREIGN KEY (cliente_id) REFERENCES clientes(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT,
            telefone TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    try:
        cursor.execute("ALTER TABLE vendas ADD COLUMN cliente_id INTEGER")
    except sqlite3.OperationalError:
        pass

    try:
        cursor.execute("ALTER TABLE vendas ADD COLUMN forma_pagamento TEXT")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def login_obrigatorio(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "usuario" not in session:
            return redirect(url_for("login"))

        return func(*args, **kwargs)

    return wrapper


@app.route("/")
def inicio():
    if "usuario" in session:
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    erro = None

    if request.method == "POST":
        usuario = request.form.get("usuario")
        senha = request.form.get("senha")

        if usuario == "admin" and senha == "1234":
            session["usuario"] = usuario
            return redirect(url_for("dashboard"))

        erro = "Usuário ou senha incorretos."

    return render_template("login.html", erro=erro)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_obrigatorio
def dashboard():
    from datetime import datetime, timedelta

    conn = conectar()

    # Produtos cadastrados
    total_produtos = conn.execute(
        "SELECT COUNT(*) FROM produtos"
    ).fetchone()[0]

    # Quantidade total em estoque
    estoque_total = conn.execute(
        "SELECT COALESCE(SUM(estoque), 0) FROM produtos"
    ).fetchone()[0]

    # Total de vendas
    total_vendas = conn.execute(
        "SELECT COUNT(*) FROM vendas"
    ).fetchone()[0]

    # Faturamento total
    faturamento = conn.execute(
        "SELECT COALESCE(SUM(valor_total), 0) FROM vendas"
    ).fetchone()[0]

    # Clientes cadastrados
    total_clientes = conn.execute(
        "SELECT COUNT(*) FROM clientes"
    ).fetchone()[0]

    # Faturamento de hoje
    faturamento_hoje = conn.execute(
        """
        SELECT COALESCE(SUM(valor_total), 0)
        FROM vendas
        WHERE DATE(data) = DATE('now', 'localtime')
        """
    ).fetchone()[0]

    # Vendas de hoje
    vendas_hoje = conn.execute(
        """
        SELECT COUNT(*)
        FROM vendas
        WHERE DATE(data) = DATE('now', 'localtime')
        """
    ).fetchone()[0]

    # Produtos com estoque baixo
    estoque_baixo = conn.execute(
        """
        SELECT *
        FROM produtos
        WHERE estoque <= 5
        ORDER BY estoque ASC
        LIMIT 5
        """
    ).fetchall()

    # Últimas vendas
    vendas_recentes = conn.execute(
        """
        SELECT
            vendas.id,
            produtos.nome AS produto_nome,
            clientes.nome AS cliente_nome,
            vendas.quantidade,
            vendas.valor_total,
            vendas.forma_pagamento,
            vendas.data
        FROM vendas

        JOIN produtos
        ON produtos.id = vendas.produto_id

        LEFT JOIN clientes
        ON clientes.id = vendas.cliente_id

        ORDER BY vendas.id DESC
        LIMIT 5
        """
    ).fetchall()

    # Produtos mais vendidos
    produtos_mais_vendidos = conn.execute(
        """
        SELECT
            produtos.nome,
            SUM(vendas.quantidade) AS quantidade_vendida
        FROM vendas

        JOIN produtos
        ON produtos.id = vendas.produto_id

        GROUP BY produtos.id, produtos.nome
        ORDER BY quantidade_vendida DESC
        LIMIT 5
        """
    ).fetchall()

    # Faturamento dos últimos 7 dias
    faturamento_7_dias = conn.execute(
        """
        SELECT
            DATE(data) AS dia,
            COALESCE(SUM(valor_total), 0) AS total
        FROM vendas
        WHERE DATE(data) >= DATE('now', 'localtime', '-6 days')
        GROUP BY DATE(data)
        ORDER BY DATE(data)
        """
    ).fetchall()

    faturamento_por_dia = {
        linha["dia"]: linha["total"]
        for linha in faturamento_7_dias
    }

    grafico_labels = []
    grafico_valores = []

    hoje = datetime.now()

    for i in range(6, -1, -1):
        dia = hoje - timedelta(days=i)

        data_banco = dia.strftime("%Y-%m-%d")
        data_exibicao = dia.strftime("%d/%m")

        grafico_labels.append(data_exibicao)

        grafico_valores.append(
            faturamento_por_dia.get(data_banco, 0)
        )

    conn.close()

    return render_template(
        "dashboard.html",
        total_produtos=total_produtos,
        estoque_total=estoque_total,
        total_vendas=total_vendas,
        faturamento=faturamento,
        total_clientes=total_clientes,
        faturamento_hoje=faturamento_hoje,
        vendas_hoje=vendas_hoje,
        estoque_baixo=estoque_baixo,
        vendas_recentes=vendas_recentes,
        produtos_mais_vendidos=produtos_mais_vendidos,
        grafico_labels=grafico_labels,
        grafico_valores=grafico_valores
    )# Total de vendas
 

@app.route("/produtos")
@login_obrigatorio
def produtos():
    conn = conectar()

    produtos = conn.execute(
        "SELECT * FROM produtos ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "produtos.html",
        produtos=produtos
    )


@app.route("/produtos/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo_produto():
    if request.method == "POST":
        nome = request.form.get("nome")
        preco = request.form.get("preco")
        estoque = request.form.get("estoque")

        conn = conectar()

        conn.execute(
            """
            INSERT INTO produtos (nome, preco, estoque)
            VALUES (?, ?, ?)
            """,
            (nome, preco, estoque)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("produtos"))

    return render_template("produto_form.html")


@app.route("/produtos/excluir/<int:id>")
@login_obrigatorio
def excluir_produto(id):
    conn = conectar()

    conn.execute(
        "DELETE FROM produtos WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("produtos"))



def vendas():
    conn = conectar()

    if request.method == "POST":
        produto_id = int(request.form.get("produto_id"))
        quantidade = int(request.form.get("quantidade"))

        produto = conn.execute(
            "SELECT * FROM produtos WHERE id = ?",
            (produto_id,)
        ).fetchone()

        if produto and produto["estoque"] >= quantidade:
            total = produto["preco"] * quantidade

            conn.execute(
                """
                INSERT INTO vendas
                (produto_id, quantidade, valor_total)
                VALUES (?, ?, ?)
                """,
                (produto_id, quantidade, total)
            )

            conn.execute(
                """
                UPDATE produtos
                SET estoque = estoque - ?
                WHERE id = ?
                """,
                (quantidade, produto_id)
            )

            conn.commit()

        return redirect(url_for("vendas"))

    produtos = conn.execute(
        """
        SELECT *
        FROM produtos
        WHERE estoque > 0
        ORDER BY nome
        """
    ).fetchall()

    conn.close()

    return render_template(
        "vendas.html",
        produtos=produtos
    )


@app.route("/historico")
@login_obrigatorio
def historico():
    conn = conectar()

    vendas = conn.execute(
        """
        SELECT
            vendas.id,
            produtos.nome,
            vendas.quantidade,
            vendas.valor_total,
            vendas.data
        FROM vendas
        JOIN produtos
        ON produtos.id = vendas.produto_id
        ORDER BY vendas.id DESC
        """
    ).fetchall()

    conn.close()

    return render_template(
        "historico.html",
        vendas=vendas
    )
@app.route("/produtos/editar/<int:id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_produto(id):
    conn = conectar()

    produto = conn.execute(
        "SELECT * FROM produtos WHERE id = ?",
        (id,)
    ).fetchone()

    if not produto:
        conn.close()
        return redirect(url_for("produtos"))

    if request.method == "POST":
        nome = request.form.get("nome")
        preco = request.form.get("preco")
        estoque = request.form.get("estoque")

        conn.execute(
            """
            UPDATE produtos
            SET nome = ?, preco = ?, estoque = ?
            WHERE id = ?
            """,
            (nome, preco, estoque, id)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("produtos"))

    conn.close()

    return render_template(
        "produto_editar.html",
        produto=produto
    )

@app.route("/clientes")
@login_obrigatorio
def clientes():
    conn = conectar()

    clientes = conn.execute(
        "SELECT * FROM clientes ORDER BY id DESC"
    ).fetchall()

    conn.close()

    return render_template(
        "clientes.html",
        clientes=clientes
    )


@app.route("/clientes/novo", methods=["GET", "POST"])
@login_obrigatorio
def novo_cliente():
    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        telefone = request.form.get("telefone")

        conn = conectar()

        conn.execute(
            """
            INSERT INTO clientes (nome, email, telefone)
            VALUES (?, ?, ?)
            """,
            (nome, email, telefone)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("clientes"))

    return render_template("cliente_form.html")


@app.route("/clientes/editar/<int:id>", methods=["GET", "POST"])
@login_obrigatorio
def editar_cliente(id):
    conn = conectar()

    cliente = conn.execute(
        "SELECT * FROM clientes WHERE id = ?",
        (id,)
    ).fetchone()

    if not cliente:
        conn.close()
        return redirect(url_for("clientes"))

    if request.method == "POST":
        nome = request.form.get("nome")
        email = request.form.get("email")
        telefone = request.form.get("telefone")

        conn.execute(
            """
            UPDATE clientes
            SET nome = ?, email = ?, telefone = ?
            WHERE id = ?
            """,
            (nome, email, telefone, id)
        )

        conn.commit()
        conn.close()

        return redirect(url_for("clientes"))

    conn.close()

    return render_template(
        "cliente_editar.html",
        cliente=cliente
    )


@app.route("/clientes/excluir/<int:id>")
@login_obrigatorio
def excluir_cliente(id):
    conn = conectar()

    conn.execute(
        "DELETE FROM clientes WHERE id = ?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("clientes"))


@app.route("/vendas", methods=["GET", "POST"])
@login_obrigatorio
def vendas():
    conn = conectar()

    if request.method == "POST":
        produto_id = int(request.form.get("produto_id"))
        quantidade = int(request.form.get("quantidade"))

        cliente_id = request.form.get("cliente_id")
        forma_pagamento = request.form.get("forma_pagamento")

        if cliente_id:
            cliente_id = int(cliente_id)
        else:
            cliente_id = None

        produto = conn.execute(
            "SELECT * FROM produtos WHERE id = ?",
            (produto_id,)
        ).fetchone()

        if produto and quantidade > 0 and produto["estoque"] >= quantidade:
            total = produto["preco"] * quantidade

            conn.execute(
                """
                INSERT INTO vendas
                (
                    produto_id,
                    cliente_id,
                    quantidade,
                    valor_total,
                    forma_pagamento
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    produto_id,
                    cliente_id,
                    quantidade,
                    total,
                    forma_pagamento
                )
            )

            conn.execute(
                """
                UPDATE produtos
                SET estoque = estoque - ?
                WHERE id = ?
                """,
                (quantidade, produto_id)
            )

            conn.commit()

        produtos = conn.execute(
            """
            SELECT *
            FROM produtos
            WHERE estoque > 0
            ORDER BY nome
            """
        ).fetchall()

        clientes = conn.execute(
            """
            SELECT *
            FROM clientes
            ORDER BY nome
            """
        ).fetchall()

        conn.close()

        return redirect(url_for("vendas"))

    produtos = conn.execute(
        """
        SELECT *
        FROM produtos
        WHERE estoque > 0
        ORDER BY nome
        """
    ).fetchall()

    clientes = conn.execute(
        """
        SELECT *
        FROM clientes
        ORDER BY nome
        """
    ).fetchall()

    conn.close()

    return render_template(
        "vendas.html",
        produtos=produtos,
        clientes=clientes
    )

    return redirect(url_for("clientes"))
if __name__ == "__main__":
    criar_banco()
    app.run(debug=True)
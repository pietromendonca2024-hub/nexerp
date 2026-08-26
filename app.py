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
            FOREIGN KEY (produto_id) REFERENCES produtos(id)
        )
    """)

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
    conn = conectar()

    total_produtos = conn.execute(
        "SELECT COUNT(*) FROM produtos"
    ).fetchone()[0]

    estoque_total = conn.execute(
        "SELECT COALESCE(SUM(estoque), 0) FROM produtos"
    ).fetchone()[0]

    total_vendas = conn.execute(
        "SELECT COUNT(*) FROM vendas"
    ).fetchone()[0]

    faturamento = conn.execute(
        "SELECT COALESCE(SUM(valor_total), 0) FROM vendas"
    ).fetchone()[0]

    conn.close()

    return render_template(
        "dashboard.html",
        total_produtos=total_produtos,
        estoque_total=estoque_total,
        total_vendas=total_vendas,
        faturamento=faturamento
    )


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


@app.route("/vendas", methods=["GET", "POST"])
@login_obrigatorio
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


if __name__ == "__main__":
    criar_banco()
    app.run(debug=True)
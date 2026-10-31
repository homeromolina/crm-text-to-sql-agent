"""Cria data/crm.db: um banco SQLite fictício de CRM (clientes, produtos, pedidos, interações).

Os dados são gerados com semente fixa e datas relativas a hoje, então perguntas como
"clientes ativos nos últimos 90 dias" sempre têm resposta.
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB = Path(__file__).parent / "crm.db"

CIDADES = ["Madrid", "Barcelona", "Valencia", "Sevilla", "Bilbao", "Málaga"]
NOMES = ["Ana", "Bruno", "Carla", "Diego", "Elena", "Felipe", "Gabriela", "Hugo", "Inés", "João",
         "Lucía", "Marcos", "Nuria", "Pablo", "Rafael", "Sofía", "Tiago", "Valeria"]
SOBRENOMES = ["García", "Silva", "Martínez", "Souza", "López", "Pereira", "Sánchez", "Costa"]
SEGMENTOS = ["varejo", "pme", "enterprise"]
CATEGORIAS = {"software": [("Plano Básico", 29.0), ("Plano Pro", 79.0), ("Plano Enterprise", 299.0)],
              "servicos": [("Onboarding", 450.0), ("Consultoria (hora)", 120.0)],
              "hardware": [("Leitor de cartão", 59.0), ("Impressora fiscal", 239.0)]}
CANAIS = ["email", "telefone", "whatsapp", "reuniao"]
STATUS = ["pago", "pago", "pago", "pago", "pendente", "cancelado"]


def main(db: Path = DB) -> None:
    rnd = random.Random(42)
    hoje = date.today()
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT,
            city TEXT NOT NULL,
            segment TEXT NOT NULL,
            created_at DATE NOT NULL
        );
        CREATE TABLE products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL
        );
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            product_id INTEGER NOT NULL REFERENCES products(id),
            quantity INTEGER NOT NULL,
            amount REAL NOT NULL,
            status TEXT NOT NULL,
            created_at DATE NOT NULL
        );
        CREATE TABLE interactions (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            channel TEXT NOT NULL,
            nps INTEGER,
            created_at DATE NOT NULL
        );
        """
    )

    produtos = []
    for cat, itens in CATEGORIAS.items():
        for nome, preco in itens:
            produtos.append((len(produtos) + 1, nome, cat, preco))
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", produtos)

    clientes = []
    for i in range(1, 801):
        nome = f"{rnd.choice(NOMES)} {rnd.choice(SOBRENOMES)}"
        email = f"cliente{i}@exemplo.com"
        fone = f"+34 6{rnd.randint(10, 99)} {rnd.randint(100, 999)} {rnd.randint(100, 999)}"
        cidade = rnd.choices(CIDADES, weights=[30, 25, 15, 12, 9, 9])[0]
        criado = hoje - timedelta(days=rnd.randint(30, 900))
        clientes.append((i, nome, email, fone, cidade, rnd.choice(SEGMENTOS), criado.isoformat()))
    con.executemany("INSERT INTO customers VALUES (?,?,?,?,?,?,?)", clientes)

    pedidos, interacoes = [], []
    for cid, *_rest in clientes:
        criado = date.fromisoformat(_rest[-1])
        for _ in range(rnd.choices([0, 1, 2, 3, 4, 6, 9], weights=[10, 20, 20, 18, 14, 10, 8])[0]):
            pid, _n, _c, preco = rnd.choice(produtos)
            qtd = rnd.randint(1, 3)
            dia = criado + timedelta(days=rnd.randint(0, (hoje - criado).days))
            pedidos.append((len(pedidos) + 1, cid, pid, qtd, round(preco * qtd, 2), rnd.choice(STATUS), dia.isoformat()))
        for _ in range(rnd.randint(0, 4)):
            dia = hoje - timedelta(days=rnd.randint(0, 365))
            nps = rnd.choice([None, rnd.randint(0, 10)])
            interacoes.append((len(interacoes) + 1, cid, rnd.choice(CANAIS), nps, dia.isoformat()))
    con.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?,?)", pedidos)
    con.executemany("INSERT INTO interactions VALUES (?,?,?,?,?)", interacoes)
    con.commit()
    con.close()
    print(f"OK: {db} ({len(clientes)} clientes, {len(pedidos)} pedidos, {len(interacoes)} interações)")


if __name__ == "__main__":
    main()

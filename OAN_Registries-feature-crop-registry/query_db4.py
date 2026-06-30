import psycopg2

try:
    conn = psycopg2.connect(
        dbname="odoo17a",
        user="odoo",
        password="123",
        host="localhost",
        port="5432"
    )
    cur = conn.cursor()
    cur.execute("SELECT id, name, mode, arch_db FROM ir_ui_view WHERE name='g2p.crop.registry.form';")
    rows = cur.fetchall()
    for row in rows:
        arch = row[3]
        count_sowing = arch.count('<page string="Sowing"')
        print(f"View {row[0]} ({row[1]}): {count_sowing} Sowing tabs")
        
    cur.execute("SELECT id, name FROM ir_ui_view WHERE inherit_id=%s;", (rows[0][0],))
    inherits = cur.fetchall()
    print("Inheriting views:", inherits)
    
except Exception as e:
    print(e)

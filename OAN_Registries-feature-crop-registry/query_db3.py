import xmlrpc.client
url = 'http://localhost:8023'
db = 'odoo17a'
username = 'admin'
password = '123'
common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(url))
uid = common.authenticate(db, username, password, {})
models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(url))
views = models.execute_kw(db, uid, password, 'ir.ui.view', 'search_read', [[['name', '=', 'g2p.crop.registry.form']]], {'fields': ['arch_db']})
for v in views:
    arch = v['arch_db']
    count_sowing = arch.count('<page string="Sowing"')
    print(f"View ID: {v['id']}, Sowing count: {count_sowing}")

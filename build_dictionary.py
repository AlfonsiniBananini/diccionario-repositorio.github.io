"""Build the static data dictionary JSON from the accompanying MySQL dump."""
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]
SQL = ROOT / "backups" / "db_test_7b_20-10-26.sql"
OUT = Path(__file__).with_name("dictionary-data.js")

TABLE_HELP = {
 "tb_buyer_orders":"Pedidos realizados a vendedores, con importes y estado de entrega.",
 "tb_carts":"Carritos de compra asociados a cada usuario.",
 "tb_logs":"Historial de operaciones registradas por el sistema.",
 "tb_products":"Catálogo de productos, precios y existencias.",
 "tb_users":"Personas registradas que usan o venden en la plataforma.",
 "tbc_categories":"Categorías para organizar productos; admite categorías superiores.",
 "tbc_payment_methods_types":"Tipos de medios de pago aceptados por la plataforma.",
 "tbd_carts_items":"Productos y cantidades agregados a cada carrito.",
 "tbd_order_items":"Detalle de productos incluidos en cada pedido.",
 "tbd_products_categories":"Relación entre productos y categorías.",
 "tbd_products_users_providers":"Relación entre productos y sus propietarios o proveedores.",
 "tbd_user_payment_methods":"Medios de pago guardados para cada usuario.",
 "tbd_users_wishlist_products":"Productos guardados por usuarios en su lista de deseos.",
}
FIELD_HELP = {
 "id":"Identificador único del registro.","ID":"Identificador único del registro.","user_ID":"Usuario al que corresponde este registro.",
 "seller_ID":"Usuario que vende o recibe este pedido.","product_ID":"Producto relacionado con este registro.","provider_ID":"Usuario que provee el producto.","cart_ID":"Carrito al que pertenece este artículo.",
 "category_ID":"Categoría asignada al producto.","sup_id_category":"Categoría superior, si forma parte de una jerarquía.",
 "payment_method_type_ID":"Tipo de medio de pago utilizado.","seller_order_ID":"Pedido al que pertenece este artículo.",
 "name":"Nombre que identifica el producto, categoría o elemento.","product_name":"Nombre del producto tal como se guardó al hacer el pedido.",
 "description":"Descripción o información adicional.","SKU":"Código utilizado para identificar el producto en el catálogo.",
 "current_price":"Precio vigente del producto.","unit_price":"Precio de una unidad al momento de la compra.","subtotal":"Importe de los artículos antes de cargos adicionales.","shipping_cost":"Costo del envío asociado al pedido.",
 "current_stock":"Cantidad disponible actualmente.","quantity":"Número de unidades incluidas.","status":"Indica si el registro está activo.","creation_date":"Fecha y hora en que se creó el registro.","last_update":"Fecha y hora de la última modificación.","last_login":"Fecha y hora del último acceso.",
 "email":"Correo electrónico de contacto o acceso.","nickname":"Nombre visible de la persona en la plataforma.","password":"Credencial de acceso almacenada por el sistema.",
 "fulfillment_status":"Etapa actual de preparación y entrega del pedido.","table_name":"Tabla afectada por la operación.","table_operation":"Tipo de acción registrada (alta, consulta, cambio o baja).","db_user":"Cuenta que realizó la operación.","operation_date":"Fecha y hora en que ocurrió la operación.","table_description":"Detalle legible de lo que ocurrió.","operation_status":"Indica si la operación se registró correctamente.","product_id":"Identificador de producto extraído del detalle del evento.",
 "code":"Código corto del tipo de medio de pago.","type_ownership":"Papel del usuario respecto al producto (propietario, revendedor o distribuidor).","avalaible_date":"Fecha y hora desde la que el producto está disponible.",
 "provider":"Proveedor del servicio de pago.","provider_method_ref":"Referencia del medio de pago en el proveedor externo.","label":"Nombre amigable para reconocer el medio de pago.","last_four":"Últimos cuatro dígitos del medio de pago.","is_default":"Indica si es el medio de pago preferido.","creation_date":"Fecha y hora en que se creó el registro.",
}

def count_rows(text, start):
    i = start; n = 0; depth = 0; quote = None; escaped = False
    while i < len(text):
        c = text[i]
        if quote:
            if escaped: escaped = False
            elif c == "\\": escaped = True
            elif c == quote:
                if i + 1 < len(text) and text[i+1] == quote: i += 1
                else: quote = None
        elif c in "'\"`": quote = c
        elif c == "(":
            if depth == 0: n += 1
            depth += 1
        elif c == ")": depth -= 1
        elif c == ";" and depth == 0: break
        i += 1
    return n

def main():
    sql = SQL.read_text(encoding="utf-8", errors="replace")
    tables = {}
    for m in re.finditer(r"CREATE TABLE `([^`]+)`\s*\((.*?)\)\s*ENGINE", sql, re.S | re.I):
        name, body = m.group(1), m.group(2)
        cols=[]
        for line in body.splitlines():
            line=line.strip().rstrip(",")
            cm=re.match(r"`([^`]+)`\s+(.+)",line)
            if not cm: continue
            field, rest=cm.groups()
            typ=rest.split(" NOT NULL",1)[0].split(" NULL",1)[0].split(" DEFAULT",1)[0].split(" AUTO_INCREMENT",1)[0].split(" GENERATED",1)[0].strip()
            # Keep complete enum/set declarations, including their exact SQL values.
            em=re.match(r"(enum|set)\(.*?\)",rest,re.I)
            if em: typ=em.group(0)
            cols.append({"name":field,"type":typ,"nullable":"NOT NULL" not in rest.upper(),"auto":"AUTO_INCREMENT" in rest.upper(),"generated":"GENERATED ALWAYS" in rest.upper(),"pk":False,"fks":[],"description":FIELD_HELP.get(field,"Dato asociado a " + field.replace("_"," ") + ".")})
        pk=re.search(r"PRIMARY KEY\s*\(([^)]+)\)",body,re.I)
        if pk:
            for c in cols:
                c["pk"]=re.search(r"`"+re.escape(c["name"])+r"`",pk.group(1)) is not None
        fks=[]
        for fm in re.finditer(r"CONSTRAINT `([^`]+)` FOREIGN KEY \(([^)]+)\) REFERENCES `([^`]+)` \(([^)]+)\)",body,re.I):
            cname, local, target, remote=fm.groups()
            local_cols=re.findall(r"`([^`]+)`",local); remote_cols=re.findall(r"`([^`]+)`",remote)
            fks.append({"name":cname,"columns":local_cols,"table":target,"references":remote_cols})
            for c in cols:
                if c["name"] in local_cols: c["fks"].append({"table":target,"column":remote_cols[local_cols.index(c["name"]) ]})
        tables[name]={"name":name,"description":TABLE_HELP.get(name,"Registros de " + name.replace("_"," ") + "."),"rows":0,"columns":cols,"relations":fks}
    for m in re.finditer(r"INSERT\s+INTO\s+`([^`]+)`.*?\bVALUES\s*",sql,re.I|re.S):
        name=m.group(1)
        if name in tables: tables[name]["rows"] += count_rows(sql,m.end())
    data={"database":"db_test_7b","source":SQL.name,"generatedFrom":"CREATE TABLE y sentencias INSERT del respaldo","tables":list(tables.values())}
    OUT.write_text("window.DICTIONARY_DATA = " + json.dumps(data,ensure_ascii=False,separators=(",",":")) + ";\n",encoding="utf-8")
    print(f"Generado {OUT.name}: {len(tables)} tablas, {sum(t['rows'] for t in tables.values()):,} registros.")

if __name__ == "__main__": main()

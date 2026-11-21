"""Datos sintéticos de RetailNova S.A. (retail de productos electrónicos en Lima, Perú).
El caso no detalla productos, tiendas ni clientes: todo lo de aquí es inventado para la demo."""
import httpx

# Precios de venta al público CON IGV (como se exhiben en Perú). El ERP guarda el precio SIN IGV.
PRODUCTOS = [
    # sku,        nombre,                                                categoría,    precio con IGV, stock, popularidad
    ("LAP-0101", "Laptop 14\" Ryzen 5, 8 GB RAM, 512 GB SSD",            "Laptops",     2299.90, 18, 6),
    ("LAP-0102", "Laptop 15.6\" Core i7, 16 GB RAM, 1 TB SSD",           "Laptops",     3899.90,  9, 3),
    ("LAP-0103", "Laptop gamer 15.6\" RTX 4060, 16 GB RAM",              "Laptops",     5499.90,  4, 2),
    ("CEL-0201", "Smartphone 6.5\" 128 GB, cámara 50 MP",                "Smartphones",  899.90, 45, 12),
    ("CEL-0202", "Smartphone 6.7\" 256 GB 5G",                           "Smartphones", 1899.90, 22, 6),
    ("TV-0301",  "Smart TV 50\" 4K UHD",                                 "Televisores", 1699.90, 14, 5),
    ("TV-0302",  "Smart TV 65\" QLED 4K",                                "Televisores", 3299.90,  3, 2),
    ("AUD-0401", "Audífonos inalámbricos con cancelación de ruido",     "Audio",        499.90, 35, 9),
    ("AUD-0402", "Parlante Bluetooth portátil resistente al agua",      "Audio",        249.90, 60, 10),
    ("TAB-0501", "Tablet 10.5\" 128 GB",                                 "Tablets",     1099.90, 16, 4),
    ("WEA-0601", "Smartwatch deportivo con GPS",                         "Wearables",    599.90, 25, 6),
    ("MON-0701", "Monitor 27\" IPS QHD",                                 "Monitores",   1199.90, 11, 3),
    ("ACC-0801", "Mouse inalámbrico ergonómico",                         "Accesorios",    59.90, 120, 16),
    ("ACC-0802", "Cargador rápido USB-C 65 W",                           "Accesorios",   119.90,  2, 11),
    ("ACC-0803", "Teclado mecánico retroiluminado",                      "Accesorios",   229.90, 40, 7),
]

TIENDAS = {"LIM-01": ("Miraflores", 40), "LIM-02": ("San Miguel", 35), "LIM-03": ("Los Olivos", 25)}

CLIENTES = [  # nombre completo, DNI, celular
    ("María Quispe Huamán", "45678912", "987654321"), ("José Mamani Condori", "41234567", "912345678"),
    ("Rosa Flores Chávez", "72345618", "923456789"), ("Luis Rojas Vargas", "43567812", "934567812"),
    ("Carmen Torres Ramírez", "70456123", "945678123"), ("Jorge Castillo Paredes", "44890321", "956781234"),
    ("Ana Gutiérrez Salazar", "71234098", "967812345"), ("Carlos Mendoza Ríos", "42987654", "978123456"),
    ("Lucía Espinoza Cárdenas", "73456210", "981234567"), ("Miguel Sánchez Aguilar", "45120987", "992345678"),
    ("Patricia Vega Medina", "70987123", "913456780"), ("Fernando Huamán Ccori", "46012398", "924567801"),
    ("Sofía Ramos Delgado", "74321098", "935678012"), ("Ricardo Díaz Palomino", "43098712", "946780123"),
    ("Gabriela Ortiz Cruz", "72109876", "957801234"), ("Diego Herrera Lozano", "47654321", "968012345"),
    ("Valeria Campos Arias", "75678901", "979123450"), ("Andrés Silva Benites", "44567123", "980234561"),
    ("Daniela Ruiz Poma", "71890234", "991345672"), ("Renzo Paredes Tello", "48901234", "902456783"),
    ("Milagros Chávez Ynga", "70123987", "913567894"), ("Kevin Alvarado Soto", "76234519", "924678905"),
    ("Fiorella Cáceres Luna", "73012456", "935789016"), ("Bruno Morales Zapata", "45987012", "946890127"),
]


def sin_igv(con_igv: float) -> str:
    return f"{con_igv / 1.18:.4f}"  # 4 decimales para que el precio con IGV cuadre al céntimo


def email(nombre: str) -> str:
    import unicodedata
    n = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode().lower().split()
    return f"{n[0]}.{n[1]}@example.com"


def asegurar_productos(erp: str, headers: dict) -> int:
    creados = 0
    for sku, nombre, cat, precio, stock, _ in PRODUCTOS:
        r = httpx.post(f"{erp}/products", headers=headers,
                       json={"sku": sku, "name": nombre, "category": cat, "price": sin_igv(precio), "stock": stock})
        creados += r.status_code == 201
    return creados

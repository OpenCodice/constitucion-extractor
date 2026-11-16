"""Perfil de Sinaloa: encabezados "Art. N", nota al pie del título y notas partidas."""
from extractor.estados import sinaloa
from extractor.parse import parse_text

P = sinaloa.PERFIL


def test_encabezados_abreviados_y_citas():
    for linea, num, suf in [("Art. 1º El Estado", 1, None), ("Art. 4º Bis A. Las personas", 4, "Bis A"),
                            ("Art. 77 Ter. El Estado", 77, "Ter"), ("Art. 121.Los municipios", 121, None)]:
        m = P.article_re.match(linea)
        assert m and int(m.group(1)) == num and m.group(2) == suf
    assert not P.article_re.match("Artículo 123 de la Constitución")


def test_preprocess_quita_nota_del_titulo_y_seccion_ter():
    texto = ("Art. 4º El territorio del Estado.\n"
             "* Constitución Política del Estado de Sinaloa. Expedida el 22 de junio de 1922. El texto\n"
             "íntegro ... 20 de julio de 1922.\n"
             "Art. 77 Bis. Para conocer de las quejas.\n"
             "SECCION II TER\nDEL CONSEJO ESTATAL\n(Adic. Según Decreto No. 437).\n"
             "Art. 77 Ter. El Estado contará con un Consejo.\n")
    arts = parse_text(texto, perfil=P)
    assert [a.key for a in arts] == ["004", "077-bis", "077-ter"]
    assert "1922" not in arts[0].body
    assert "SECCION" not in arts[1].body


def test_preprocess_une_abreviaturas_y_anios():
    t = sinaloa._preprocess("texto. (Ref.\nSegún Decreto No.\n088, de fecha 24 de julio de\n2026.)\nSigue")
    assert t == "texto. (Ref. Según Decreto No. 088, de fecha 24 de julio de 2026.)\n\nSigue"

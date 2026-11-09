def html(resp):
    return resp.get_data(as_text=True)


# ---- Dashboard --------------------------------------------------------------- #
def test_dashboard_lists_houses(make_house, client):
    make_house("Villa A", colors=[{"color_name": "Warm White"}])
    r = client.get("/")
    assert r.status_code == 200
    body = html(r)
    assert "Villa A" in body and "Warm White" in body and "RGB(" in body


def test_dashboard_search_filters(make_house, client):
    make_house("Villa A", colors=[{"color_name": "Sand", "manufacturing": "TOA"}])
    make_house("Villa B", colors=[{"color_name": "Navy", "manufacturing": "DELUX"}])
    body = html(client.get("/?q=Villa B"))
    assert "Villa B" in body and "Villa A" not in body


def test_dashboard_manufacturer_filter(make_house, client):
    make_house("Villa A", colors=[{"color_name": "Sand", "manufacturing": "TOA"}])
    make_house("Villa B", colors=[{"color_name": "Navy", "manufacturing": "DELUX"}])
    body = html(client.get("/?manufacturer=DELUX"))
    assert "Villa B" in body and "Villa A" not in body


def test_dashboard_escapes_house_name(make_house, client):
    make_house("<script>alert(1)</script>")
    body = html(client.get("/"))
    assert "&lt;script&gt;" in body
    assert "<script>alert(1)" not in body


def test_unknown_page_404_html(client):
    r = client.get("/nope")
    assert r.status_code == 404
    assert r.mimetype == "text/html"


def test_unknown_api_404_json(client):
    r = client.get("/api/nope")
    assert r.status_code == 404
    assert r.mimetype == "application/json"


# ---- All Colors / Manufacturers --------------------------------------------- #
def test_colors_page_paginates(make_house, client):
    make_house("Villa A", colors=[{"color_name": f"C{i}"} for i in range(12)])
    body = html(client.get("/colors?per_page=10&page=2"))
    assert body.count("data-color-id=") == 2


def test_colors_page_sort_by_name(make_house, client):
    make_house("Villa A", colors=[{"color_name": "Bbb"}, {"color_name": "Aaa"}])
    body = html(client.get("/colors?sort=color_name&order=asc"))
    assert body.index("Aaa") < body.index("Bbb")


def test_colors_page_bad_params(make_house, client):
    make_house("Villa A", colors=[{"color_name": "Sand"}])
    for qs in ("?page=abc", "?page=-5", "?page=9999", "?sort=DROP&order=sideways", "?per_page=100000"):
        r = client.get("/colors" + qs)
        assert r.status_code == 200, qs
        assert "Sand" in html(r), qs


def test_manufacturers_page_lists_defaults(client):
    body = html(client.get("/manufacturers"))
    assert "TOA" in body and "DELUX" in body


# ---- House detail / Add house --------------------------------------------- #
def test_house_page_renders(make_house, client):
    house = make_house("Villa A", colors=[{"color_name": "Warm White"}], image=True)
    body = html(client.get(f"/houses/{house['id']}"))
    assert "Villa A" in body
    assert f"/uploads/{house['images'][0]['image_path']}" in body
    assert "Warm White" in body


def test_house_page_404(client):
    r = client.get("/houses/999999")
    assert r.status_code == 404
    assert r.mimetype == "text/html"


def test_house_page_embeds_json_escaped(make_house, client):
    house = make_house("</script><b>x")
    body = html(client.get(f"/houses/{house['id']}"))
    start = body.index('id="house-data"')
    block = body[start:body.index("</script>", start)]
    assert "<b>" not in block
    assert "</script><b>" not in body


def test_house_page_sorts_colors(make_house, client):
    house = make_house("Villa A", colors=[{"color_name": "Bbb"}, {"color_name": "Aaa"}])
    body = html(client.get(f"/houses/{house['id']}?sort=color_name&order=asc"))
    table = body[body.index("js-color-table"):]
    assert table.index("Aaa") < table.index("Bbb")


def test_add_house_page_renders(client):
    body = html(client.get("/houses/new"))
    assert 'name="house_name"' in body

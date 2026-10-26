"""Browser hash routes must never swallow proxied Tdarr resource paths."""
import httpx
import pytest
from sqlalchemy import select
from app import main,tools_proxy
from app.db import SessionLocal
from app.models import User
from test_portal import setup,post


@pytest.mark.parametrize('suffix',['/#','/#/','/#/home'])
def test_existing_tdarr_hash_address_loads_assets_from_the_server_path(client,monkeypatch,suffix):
    setup(client)
    with SessionLocal() as db:
        main.set_config(db,'tdarr_enabled','true');main.set_config(db,'tdarr_url','http://tdarr.private:8265'+suffix)
        db.scalar(select(User).where(User.admin.is_(True))).tool_access='["tdarr"]';db.commit()
    native=httpx.AsyncClient;seen=[]
    async def upstream(request):
        seen.append(request.url)
        if request.url.path=='/static/css/main.css':return httpx.Response(200,text='body{color:white}',headers={'content-type':'text/css'})
        return httpx.Response(200,text='<!doctype html><html><head></head><body>SPA fallback</body></html>',headers={'content-type':'text/html'})
    monkeypatch.setattr(tools_proxy.httpx,'AsyncClient',lambda **kw:native(transport=httpx.MockTransport(upstream),**kw))
    result=client.get('/tools/tdarr/app/tdarr/static/css/main.css')
    assert result.headers['content-type'].startswith('text/css')
    assert seen[0].path=='/static/css/main.css' and not seen[0].fragment


def test_tdarr_save_removes_browser_hash_route(client):
    setup(client)
    response=post(client,'/admin/connections/tdarr/save',{'enabled':'on','interface_enabled':'on','url':'http://tdarr.private:8265/#'},'/admin/integrations')
    assert response.status_code==303
    with SessionLocal() as db:assert main.config(db,'tdarr_url')=='http://tdarr.private:8265'

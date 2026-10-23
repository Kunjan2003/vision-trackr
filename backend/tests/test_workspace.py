"""Regressions for range boundaries, analytics and invoice accounting."""
from backend.tests.test_api import client, HEADERS
from backend.tests.test_v2_features import login_headers as authenticate
from functools import lru_cache

@lru_cache
def login_headers():
    return authenticate()

def test_v3_auth_range_and_manual_totals():
    assert client.get('/v3/summary?start=2024-02-01&end=2024-02-01',headers=HEADERS).status_code==401
    h=login_headers()
    assert client.get('/v3/summary?start=2024-02-02&end=2024-02-01',headers=h).status_code==422
    assert client.get('/v3/summary?start=2024-01-01&end=2025-01-01',headers=h).status_code==422
    # Local midnight, with an adjacent next-day entry that must never be billed.
    p=client.post('/v2/projects',headers=h,json={'name':'Boundary regression','client':'Boundary client','hourly_rate':120}).json()
    for stamp in ['2024-02-01','2024-02-02']:
        r=client.post('/v2/manual',headers=h,json={'started_at':stamp+'T00:00:00+05:30','ended_at':stamp+'T01:00:00+05:30','note':'Boundary test','project_id':p['id']})
        assert r.status_code==201,r.text
    q='?start=2024-02-01&end=2024-02-01&tz=-330'
    summary=client.get('/v3/summary'+q,headers=h).json()
    assert summary['totals']['work']==3600
    assert summary['days'][0]['active']==3600
    assert sum(x['productive'] for x in summary['selected_day']['hourly'])==3600
    for endpoint in ['/v2/projects/analytics','/v2/tasks/analytics']:
        r=client.get(endpoint+q,headers=h)
        assert r.status_code==200
        if endpoint.endswith('projects/analytics'):
            row=next(x for x in r.json() if x['id']==p['id'])
            assert row['hours']==1 and row['billable']==120
    # Snapshot stays unchanged after the project's rate changes.
    form={'number':'INV-BOUNDARY','client':'Boundary client','project_ids':[p['id']], 'currency':'INR',
          'start':'2024-02-01','end':'2024-02-01','issued_on':'2024-02-03','due_on':'2024-03-01'}
    created=client.post('/v3/invoices?tz=-330',headers=h,json=form)
    assert created.status_code==201,created.text
    invoice=created.json();assert invoice['total']==120
    assert client.post('/v3/invoices?tz=-330',headers=h,json=form).status_code==409
    assert client.post('/v3/invoices?tz=-330',headers=h,json={**form,'number':'OTHER','client':'Wrong client'}).status_code==422
    assert client.post('/v3/invoices?tz=-330',headers=h,json={**form,'number':'   '}).status_code==422
    client.patch('/v2/projects/'+str(p['id']),headers=h,json={'name':'Boundary regression','client':'Boundary client','hourly_rate':999})
    saved=next(x for x in client.get('/v3/invoices',headers=h).json() if x['id']==invoice['id'])
    assert saved['total']==120 and saved['details']['lines'][0]['hourly_rate']==120
    path='/v3/invoices/'+str(invoice['id'])
    assert client.get(path+'/export',headers=h).content.startswith(b'%PDF')
    assert client.patch(path,headers=h,json={'status':'paid'}).status_code==409
    assert client.patch(path,headers=h,json={'status':'sent'}).status_code==200
    assert client.patch(path,headers=h,json={'status':'paid'}).status_code==200
    assert client.patch(path,headers=h,json={'status':'draft'}).status_code==409

def test_daily_csv_includes_manual_and_escapes_formula():
    h=login_headers()
    r=client.post('/v2/manual',headers=h,json={'started_at':'2024-04-01T10:00:00Z','ended_at':'2024-04-01T11:00:00Z','note':'=SUM(A1)'} )
    assert r.status_code==201
    out=client.get('/export?day=2024-04-01&format=csv',headers=h)
    assert "Manual entry" in out.text and "'=SUM(A1)" in out.text

def test_invoice_routes_are_scoped_and_unknown_ids_fail():
    h=login_headers()
    assert client.get('/v3/invoices',headers=HEADERS).status_code==401
    assert client.get('/v3/invoices/99999/export',headers=h).status_code==404
    assert client.patch('/v3/invoices/99999',headers=h,json={'status':'paid'}).status_code==404
    assert client.get('/v3/summary?start=2024-02-01&end=2024-02-01&tz=9999',headers=h).status_code==422


def test_other_user_cannot_read_invoice_or_analytics():
    from workpulse.db import SessionLocal
    from workpulse.models import User,Invoice
    from workpulse.security import issue_token
    from sqlalchemy import select
    with SessionLocal() as db:
        stranger=User(full_name="Other user",email="other@example.com",department="",password_hash="not-used")
        db.add(stranger);db.commit()
        token=issue_token(stranger)
        invoice=db.scalar(select(Invoice))
        invoice_id=invoice.id
    auth={**HEADERS,"Authorization":"Bearer "+token}
    assert client.get('/v3/invoices',headers=auth).json()==[]
    assert client.get('/v3/invoices/'+str(invoice_id)+'/export',headers=auth).status_code==404
    assert client.patch('/v3/invoices/'+str(invoice_id),headers=auth,json={'status':'sent'}).status_code==404
    result=client.get('/v3/summary?start=2024-02-01&end=2024-02-01',headers=auth).json()
    assert result['totals']['work']==0 and result['apps']==[]
